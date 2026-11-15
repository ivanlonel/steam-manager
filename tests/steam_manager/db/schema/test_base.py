"""Tests for the base of the Steam tables: the flag type, STRICT tables, the notebook check."""

from contextlib import closing

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, Text, create_engine, insert, select

from steam_manager.db.schema import Flag, SteamBase
from tests.steam_manager.db.schema._notebook import build, differences


def test_a_flag_is_stored_as_an_integer() -> None:
    """Flags are 1, 0 or NULL in the file, as the notebook has them, and booleans in Python."""
    table = Table(
        "flags",
        MetaData(),
        Column("position", Integer, primary_key=True),
        Column("flag", Flag),
        sqlite_strict=True,
    )
    engine = create_engine("sqlite://")
    table.create(engine)

    with engine.begin() as connection:
        connection.execute(insert(table), [{"flag": True}, {"flag": False}, {"flag": None}])
        stored = connection.exec_driver_sql(
            "SELECT flag, typeof(flag) FROM flags ORDER BY position"
        ).all()
        read = connection.scalars(select(table.c.flag).order_by(table.c.position)).all()
    engine.dispose()

    assert [tuple(row) for row in stored] == [(1, "integer"), (0, "integer"), (None, "null")]
    assert read == [True, False, None]


def test_a_renamed_column_is_caught() -> None:
    """A column whose name drifts from the notebook's fails the comparison, naming both."""
    metadata = MetaData()
    Table(
        "tag",
        metadata,
        Column("tag_id", Integer, primary_key=True),
        Column("name", Text),
        sqlite_strict=True,
    )

    assert differences("tag", metadata=metadata) == [
        "only in the notebook: tag.tagid #0: INTEGER notnull=1 pk=1",
        "only declared: tag.tag_id #0: INTEGER notnull=1 pk=1",
    ]


def test_a_table_the_notebook_lacks_is_refused() -> None:
    """Comparing a table the notebook doesn't have is a mistake in the test, not a match."""
    with pytest.raises(LookupError, match="app_compatibility_test"):
        differences("app_compatibility_test")


def test_every_table_is_strict() -> None:
    """Every Steam table refuses values of the wrong type, the new ones included."""
    with closing(build(SteamBase.metadata)) as connection:
        loose = connection.execute(
            "SELECT name FROM pragma_table_list"
            " WHERE schema = 'main' AND type = 'table' AND name NOT LIKE 'sqlite_%' AND NOT strict"
        ).fetchall()

    assert SteamBase.metadata.tables
    assert loose == []
