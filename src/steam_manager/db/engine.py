"""Open the profile database, with the settings every connection to it needs."""

from typing import TYPE_CHECKING

from sqlalchemy import URL, Engine, create_engine, event

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry


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
    """
    engine = create_engine(URL.create("sqlite", database=str(path)))
    event.listen(engine, "connect", _configure)
    return engine
