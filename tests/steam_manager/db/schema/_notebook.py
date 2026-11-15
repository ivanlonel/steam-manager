"""Compare declared tables with the notebook's schema, through what SQLite says about each."""

import re
import sqlite3
from contextlib import closing
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable
lazy from sqlalchemy import MetaData

from steam_manager.db.schema import SteamBase

if TYPE_CHECKING:
    from collections.abc import Iterator

NOTEBOOK_SCHEMA: Final = (
    Path(__file__).parents[3] / "fixtures" / "notebook" / "steam_database_schema.sql"
)
"""The notebook's DDL, verbatim."""

_COLUMNS: Final = """
    SELECT cid, name, type, "notnull" OR pk > 0, pk, dflt_value, hidden FROM pragma_table_xinfo(?)
"""
_FOREIGN_KEYS: Final = """
    SELECT "table", group_concat("from", ', ' ORDER BY seq), group_concat("to", ', ' ORDER BY seq)
    FROM pragma_foreign_key_list(?) GROUP BY id
"""
_UNIQUE_INDEXES: Final = """
    SELECT group_concat(info.name, ', ' ORDER BY info.seqno),
        (SELECT sql FROM sqlite_schema WHERE type = 'index' AND name = list.name)
    FROM pragma_index_list(?1) AS list, pragma_index_info(list.name) AS info
    WHERE list."unique" AND list.origin != 'pk' GROUP BY list.name
"""
_OPTIONS: Final = "SELECT strict, wr FROM pragma_table_list(?)"
_TABLE_SQL: Final = "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?"

_CLAUSE: Final = re.compile(r"\b(CHECK|GENERATED\s+ALWAYS\s+AS)\s*\(", re.IGNORECASE)
"""Where a CHECK or a generated column's expression starts, up to its opening parenthesis."""
_WHERE: Final = re.compile(r"\sWHERE\s", re.IGNORECASE)
"""What precedes a partial index's condition."""


def _normal(sql: str) -> str:
    """
    Write an SQL expression one way: single spaces, none inside parentheses.

    :param sql: The expression, as a statement holds it.
    :return: It, normalized.
    """
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", " ".join(sql.split())))


def _closing(sql: str, start: int) -> int:
    """
    Find the parenthesis that closes the one just before *start*.

    :param sql: A statement.
    :param start: Where the text inside the parentheses begins.
    :return: Where the closing parenthesis is.
    :raise ValueError: When it never closes.
    """
    depth = 1
    for position in range(start, len(sql)):
        depth += {"(": 1, ")": -1}.get(sql[position], 0)
        if depth == 0:
            return position
    message = "unbalanced parentheses"
    raise ValueError(message)


def _clauses(sql: str) -> Iterator[str]:
    """
    Yield each CHECK and generated expression of a ``CREATE TABLE`` statement.

    :param sql: The statement, as ``sqlite_schema`` keeps it, comments included.
    :yield: Lines such as ``"check (role IN ('developer'))"`` or ``"generated (a + b)"``.
    """
    sql = re.sub(r"--[^\n]*", "", sql)
    for match in _CLAUSE.finditer(sql):
        kind = "check" if match[1].upper() == "CHECK" else "generated"
        yield f"{kind} ({_normal(sql[match.end() : _closing(sql, match.end())])})"


def _condition(sql: str | None) -> str:
    """
    Say what a partial index covers.

    :param sql: The index's ``CREATE INDEX`` statement, or ``None`` for one SQLite made.
    :return: ``" where <condition>"``, or nothing for an index on every row.
    """
    parts = _WHERE.split(sql or "", maxsplit=1)
    return f" where {_normal(parts[1])}" if len(parts) == 2 else ""


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
    statements = connection.execute(_TABLE_SQL, (table,))
    return {
        *(
            f"{table}.{name} #{cid}: {type_} notnull={nn} pk={pk} default={dflt} hidden={hidden}"
            for cid, name, type_, nn, pk, dflt, hidden in columns
        ),
        *(f"{table} foreign key ({ours}) -> {parent} ({theirs})" for parent, ours, theirs in keys),
        *(f"{table} unique ({names}){_condition(sql)}" for names, sql in uniques),
        *(
            f"{table}: strict={strict} without_rowid={without_rowid}"
            for strict, without_rowid in options
        ),
        *(f"{table} {clause}" for (sql,) in statements for clause in _clauses(sql)),
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
