"""Open the profile database, with the settings every connection to it needs."""

import sqlite3
from typing import TYPE_CHECKING, Final

from sqlalchemy import URL, Engine, create_engine, event

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

MINIMUM_SQLITE: Final = (3, 44)
"""The oldest SQLite the database works with: the reports order rows inside aggregates."""


def _configure(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """
    Set up a new connection: foreign keys enforced, and write-ahead logging.

    SQLite enforces foreign keys per connection, and only when asked to. WAL lets the web
    interface read while a sync writes.

    :param connection: The SQLite connection.
    :param _record: Its pool entry, unused.
    """
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()


def open_database(path: Path) -> Engine:
    """
    Open a profile's database, creating the file when missing.

    :param path: The database file. Its folder must exist.
    :return: An engine whose every connection enforces foreign keys and uses WAL.
    :raise RuntimeError: When Python's SQLite is older than :data:`MINIMUM_SQLITE`.
    """
    if sqlite3.sqlite_version_info < MINIMUM_SQLITE:
        needed = ".".join(map(str, MINIMUM_SQLITE))
        message = f"SQLite {sqlite3.sqlite_version} is too old: steam-manager needs {needed}"
        raise RuntimeError(message)
    engine = create_engine(URL.create("sqlite", database=str(path)))
    event.listen(engine, "connect", _configure)
    return engine
