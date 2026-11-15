"""Tests for dropping and recreating the Steam tables when their schema changes."""

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, event, exc, insert, inspect, select

from steam_manager.db.engine import open_database
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppTag
from steam_manager.db.steam_schema import ensure_steam_schema, fingerprint
from tests.steam_manager.db.schema.test_base import STEAM_TABLES

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Connection, Engine
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry


@pytest.fixture(name="engine")
def engine_fixture(tmp_path: Path) -> Iterator[Engine]:
    """
    Open an empty profile database.

    :param tmp_path: Where the file goes.
    :yield: Its engine, disposed of afterwards.
    """
    database = open_database(tmp_path / "steam.sqlite")
    yield database
    database.dispose()


def _tables(engine: Engine) -> set[str]:
    """
    List the tables in a database.

    :param engine: The database.
    :return: Their names.
    """
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def _age(connection: Connection) -> None:
    """
    Make the Steam tables look built by an older release, whose schema was different.

    :param connection: The database.
    """
    connection.exec_driver_sql("UPDATE steam_schema SET fingerprint = 'older'")


def _open_a_transaction(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """
    Leave a new connection inside a transaction, where SQLite ignores ``PRAGMA foreign_keys``.

    :param connection: The SQLite connection.
    :param _record: Its pool entry, unused.
    """
    cursor = connection.cursor()
    cursor.execute("UPDATE steam_schema SET name = name")
    cursor.close()


def test_importing_the_schema_declares_every_table() -> None:
    """What the application imports declares every table, not only what the tests import."""
    script = "import steam_manager.db.steam_schema as s; print(*s.SteamBase.metadata.tables)"
    declared = subprocess.run(  # noqa: S603  # this interpreter, on a script written here
        [sys.executable, "-c", script], capture_output=True, check=True, text=True
    ).stdout.split()

    assert set(declared) == STEAM_TABLES


def test_a_new_database_gets_every_table(engine: Engine) -> None:
    """A database just created gets every Steam table, and the caller learns it is empty."""
    assert ensure_steam_schema(engine) is True
    assert _tables(engine) == STEAM_TABLES | {"steam_schema"}


def test_a_current_database_is_left_alone(engine: Engine) -> None:
    """Opening a database this release built keeps its rows."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.execute(insert(App), [{"appid": 620, "name": "Portal 2"}])

    assert ensure_steam_schema(engine) is False
    with engine.connect() as connection:
        assert connection.scalar(select(App.name)) == "Portal 2"


def test_a_changed_schema_drops_and_recreates(engine: Engine) -> None:
    """A database an older release built is recreated empty, and the caller learns it must be."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        _age(connection)

    assert ensure_steam_schema(engine) is True
    with engine.connect() as connection:
        assert connection.scalar(select(App.appid)) is None
    assert _tables(engine) == STEAM_TABLES | {"steam_schema"}
    assert ensure_steam_schema(engine) is False


def test_a_table_an_older_release_declared_is_dropped(engine: Engine) -> None:
    """A Steam table this release no longer declares goes too, even with rows pointing at apps."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE app_old (appid INTEGER REFERENCES app (appid)) STRICT"
        )
        connection.execute(insert(App), [{"appid": 620}])
        connection.exec_driver_sql("INSERT INTO app_old VALUES (620)")
        connection.exec_driver_sql("INSERT INTO steam_schema VALUES ('app_old', 'older')")
        _age(connection)

    assert ensure_steam_schema(engine) is True
    assert "app_old" not in _tables(engine)


def test_a_table_that_isnt_steams_is_never_dropped(engine: Engine) -> None:
    """The user's own data is never dropped with the Steam tables."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE note (appid INTEGER, text TEXT) STRICT")
        connection.exec_driver_sql("INSERT INTO note VALUES (620, 'finish the co-op')")
        _age(connection)

    ensure_steam_schema(engine)

    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT text FROM note").scalar() == "finish the co-op"


def test_foreign_keys_are_on_after_recreating(engine: Engine) -> None:
    """Foreign keys are off to drop tables in any order, and back on after."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        _age(connection)
    ensure_steam_schema(engine)

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(insert(AppTag), [{"appid": 620, "tagid": 1}])


def test_nothing_is_dropped_while_foreign_keys_stay_on(engine: Engine) -> None:
    """
    Inside an open transaction SQLite ignores the PRAGMA that turns foreign keys off.

    Dropping ``app`` then would run the user's ``ON DELETE CASCADE`` and empty their tables, so
    the call fails before dropping anything.
    """
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE note (appid INTEGER REFERENCES app (appid) ON DELETE CASCADE,"
            " text TEXT) STRICT"
        )
        connection.execute(insert(App), [{"appid": 620}])
        connection.exec_driver_sql("INSERT INTO note VALUES (620, 'finish the co-op')")
        _age(connection)
    engine.dispose()
    event.listen(engine, "connect", _open_a_transaction)

    with pytest.raises(RuntimeError, match="foreign keys are still on"):
        ensure_steam_schema(engine)

    event.remove(engine, "connect", _open_a_transaction)
    engine.dispose()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT text FROM note").scalar() == "finish the co-op"
        assert connection.scalar(select(App.appid)) == 620


def test_the_fingerprint_follows_the_ddl() -> None:
    """The same tables give the same fingerprint; one more column gives another."""
    one, other = MetaData(), MetaData()
    Table("app", one, Column("appid", Integer, primary_key=True))
    Table("app", other, Column("appid", Integer, primary_key=True), Column("type", Integer))

    assert fingerprint() == fingerprint()
    assert fingerprint(one) == fingerprint(one)
    assert fingerprint(one) != fingerprint(other)
