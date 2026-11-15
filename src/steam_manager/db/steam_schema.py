"""Rebuild the Steam tables when this release declares them differently from the file's."""

from hashlib import sha256
from typing import TYPE_CHECKING, Final

from sqlalchemy import Column, MetaData, Table, Text, delete, insert, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable, DropTable

from steam_manager.db.schema import SteamBase

if TYPE_CHECKING:
    from sqlalchemy import Engine

__all__ = ["STEAM_SCHEMA", "ensure_steam_schema", "fingerprint"]

STEAM_SCHEMA: Final = Table(
    "steam_schema",
    MetaData(),
    Column("name", Text, primary_key=True),
    Column("fingerprint", Text, nullable=False),
    sqlite_strict=True,
    sqlite_with_rowid=False,
)
"""The Steam tables a file holds, each with the fingerprint of the schema that built it."""


def fingerprint(metadata: MetaData = SteamBase.metadata) -> str:
    """
    Hash the DDL of a set of tables: any change to a table, a column or an index changes it.

    A SQLAlchemy release that words its DDL differently changes it too, which costs one
    rebuild and nothing else.

    :param metadata: The tables, by default every Steam table.
    :return: The SHA-256 of their ``CREATE TABLE`` and ``CREATE INDEX`` statements, in hex.
    """
    dialect = sqlite.dialect()
    tables = metadata.tables.values()
    statements = [str(CreateTable(table).compile(dialect=dialect)) for table in tables]
    statements += [
        str(CreateIndex(index).compile(dialect=dialect))
        for table in tables
        for index in table.indexes
    ]
    return sha256("\n".join(sorted(statements)).encode()).hexdigest()


def ensure_steam_schema(engine: Engine) -> bool:
    """
    Make the Steam tables match this release, dropping and recreating them when they don't.

    Only the tables this release declares, and the ones the file records as Steam's, are
    dropped: a table holding the user's own data never is. Steam tables are never migrated;
    the caller replays the raw archive into the new, empty ones.

    :param engine: The profile database.
    :return: ``True`` when the tables were created and are empty, ``False`` when they were
        already current.
    """
    current = fingerprint()
    with engine.begin() as connection:
        STEAM_SCHEMA.create(connection, checkfirst=True)
        recorded = connection.execute(select(STEAM_SCHEMA.c.name, STEAM_SCHEMA.c.fingerprint))
        names = set(SteamBase.metadata.tables)
        fingerprints: set[str] = set()
        for name, stored in recorded:
            names.add(name)
            fingerprints.add(stored)
        if fingerprints == {current}:
            return False
        # ponytail: pysqlite runs DDL outside a transaction, so an interrupted rebuild isn't
        # undone; the fingerprints are written last, and the next open redoes it.
        # Off so the tables drop in any order, even with rows pointing at each other.
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        try:
            for name in sorted(names):
                connection.execute(DropTable(Table(name, MetaData()), if_exists=True))
            SteamBase.metadata.create_all(connection)
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.execute(delete(STEAM_SCHEMA))
        connection.execute(
            insert(STEAM_SCHEMA),
            [{"name": name, "fingerprint": current} for name in SteamBase.metadata.tables],
        )
    return True
