"""Compare declared tables with the notebook's schema, through what SQLite says about each."""

import sqlite3
from contextlib import closing
from functools import cache
from pathlib import Path
from typing import Final

from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable
lazy from sqlalchemy import MetaData

from steam_manager.db.schema import SteamBase

NOTEBOOK_SCHEMA: Final = (
    Path(__file__).parents[3] / "fixtures" / "notebook" / "steam_database_schema.sql"
)
"""The notebook's DDL, verbatim."""

_COLUMNS: Final = 'SELECT cid, name, type, "notnull" OR pk > 0, pk FROM pragma_table_xinfo(?)'
_FOREIGN_KEYS: Final = """
    SELECT "table", group_concat("from", ', ' ORDER BY seq), group_concat("to", ', ' ORDER BY seq)
    FROM pragma_foreign_key_list(?) GROUP BY id
"""
_UNIQUE_INDEXES: Final = """
    SELECT group_concat(info.name, ', ' ORDER BY info.seqno), list.partial
    FROM pragma_index_list(?1) AS list, pragma_index_info(list.name) AS info
    WHERE list."unique" AND list.origin != 'pk' GROUP BY list.name
"""
_OPTIONS: Final = "SELECT strict, wr FROM pragma_table_list(?)"


@cache
def _notebook() -> sqlite3.Connection:
    """
    Build the notebook's schema in memory, once.

    :return: A connection holding it.
    """
    connection = sqlite3.connect(":memory:")
    connection.executescript(NOTEBOOK_SCHEMA.read_text(encoding="utf-8"))
    return connection


def build(metadata: MetaData) -> sqlite3.Connection:
    """
    Build declared tables in memory, from the DDL SQLAlchemy compiles for SQLite.

    :param metadata: The tables.
    :return: A connection holding them.
    """
    connection = sqlite3.connect(":memory:")
    dialect = sqlite.dialect()
    for table in metadata.sorted_tables:
        connection.execute(str(CreateTable(table).compile(dialect=dialect)))
        for index in table.indexes:
            connection.execute(str(CreateIndex(index).compile(dialect=dialect)))
    return connection


@cache
def _declared() -> sqlite3.Connection:
    """
    Build the declared Steam tables in memory, once.

    :return: A connection holding them.
    """
    return build(SteamBase.metadata)


def describe(connection: sqlite3.Connection, table: str) -> set[str]:
    """
    Say what SQLite knows about *table*: one line per column, key, foreign key and index.

    A primary key column counts as NOT NULL either way: SQLite never stores one as NULL, though
    ``INTEGER PRIMARY KEY`` reports it nullable and SQLAlchemy declares it NOT NULL.

    :param connection: The database holding the table.
    :param table: The table's name.
    :return: The lines; none when the table doesn't exist.
    """
    columns = connection.execute(_COLUMNS, (table,))
    keys = connection.execute(_FOREIGN_KEYS, (table,))
    uniques = connection.execute(_UNIQUE_INDEXES, (table,))
    options = connection.execute(_OPTIONS, (table,))
    return {
        *(
            f"{table}.{name} #{cid}: {type_} notnull={nn} pk={pk}"
            for cid, name, type_, nn, pk in columns
        ),
        *(f"{table} foreign key ({ours}) -> {parent} ({theirs})" for parent, ours, theirs in keys),
        *(
            f"{table} unique ({names}){' partial' if partial else ''}"
            for names, partial in uniques
        ),
        *(
            f"{table}: strict={strict} without_rowid={without_rowid}"
            for strict, without_rowid in options
        ),
    }


def differences(table: str, *, metadata: MetaData | None = None) -> list[str]:
    """
    List how a declared table differs from the notebook's.

    :param table: The table's name.
    :param metadata: The tables to compare, when not the declared Steam tables.
    :return: One line per difference, such as ``"only declared: app.x #3: TEXT notnull=0 pk=0"``.
    :raise LookupError: When the notebook has no such table.
    """
    notebook = describe(_notebook(), table)
    if not notebook:
        message = f"the notebook has no table {table}"
        raise LookupError(message)
    if metadata is None:
        ours = describe(_declared(), table)
    else:
        with closing(build(metadata)) as declared:
            ours = describe(declared, table)
    return [f"only in the notebook: {line}" for line in sorted(notebook - ours)] + [
        f"only declared: {line}" for line in sorted(ours - notebook)
    ]
