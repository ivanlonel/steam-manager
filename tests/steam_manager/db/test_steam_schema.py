"""Tests for rebuilding the Steam tables when their schema changes."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, exc, insert, inspect, select

from steam_manager.db.engine import open_database
from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppTag
from steam_manager.db.steam_schema import ensure_steam_schema, fingerprint

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Connection, Engine


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


def test_a_new_database_gets_every_table(engine: Engine) -> None:
    """A database just created gets every Steam table, and the caller learns it is empty."""
    assert ensure_steam_schema(engine) is True
    assert set(SteamBase.metadata.tables) <= _tables(engine)


def test_a_current_database_is_left_alone(engine: Engine) -> None:
    """Opening a database this release built keeps its rows."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.execute(insert(App), [{"appid": 620, "name": "Portal 2"}])

    assert ensure_steam_schema(engine) is False
    with engine.connect() as connection:
        assert connection.scalar(select(App.name)) == "Portal 2"


def test_a_changed_schema_drops_and_recreates(engine: Engine) -> None:
    """A database an older release built is rebuilt, and the caller learns it must replay."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        _age(connection)

    assert ensure_steam_schema(engine) is True
    with engine.connect() as connection:
        assert connection.scalar(select(App.appid)) is None
    assert set(SteamBase.metadata.tables) <= _tables(engine)
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


def test_a_table_that_isnt_steams_survives_a_rebuild(engine: Engine) -> None:
    """The user's own data is never dropped with the Steam tables."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE note (appid INTEGER, text TEXT) STRICT")
        connection.exec_driver_sql("INSERT INTO note VALUES (620, 'finish the co-op')")
        _age(connection)

    ensure_steam_schema(engine)

    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT text FROM note").scalar() == "finish the co-op"


def test_foreign_keys_are_on_after_a_rebuild(engine: Engine) -> None:
    """The rebuild turns foreign keys off to drop tables in any order, and back on after."""
    ensure_steam_schema(engine)
    with engine.begin() as connection:
        _age(connection)
    ensure_steam_schema(engine)

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(insert(AppTag), [{"appid": 620, "tagid": 1}])


def test_the_fingerprint_follows_the_ddl() -> None:
    """The same tables give the same fingerprint; one more column gives another."""
    one, other = MetaData(), MetaData()
    Table("app", one, Column("appid", Integer, primary_key=True))
    Table("app", other, Column("appid", Integer, primary_key=True), Column("type", Integer))

    assert fingerprint() == fingerprint()
    assert fingerprint(one) == fingerprint(one)
    assert fingerprint(one) != fingerprint(other)
