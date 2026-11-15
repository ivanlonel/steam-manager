"""Tests for the base of the Steam tables: the flag type, STRICT tables, the notebook check."""

from contextlib import closing
from typing import Final

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    insert,
    select,
)

from steam_manager.db.schema import Flag, SteamBase
from tests.steam_manager.db.schema._notebook import build, differences
from tests.steam_manager.db.schema.test_apps import APP_TABLES
from tests.steam_manager.db.schema.test_classification import CLASSIFICATION_TABLES
from tests.steam_manager.db.schema.test_creators import CREDIT_TABLES
from tests.steam_manager.db.schema.test_lookups import LOOKUPS
from tests.steam_manager.db.schema.test_media import MEDIA_TABLES
from tests.steam_manager.db.schema.test_offers import OFFER_TABLES
from tests.steam_manager.db.schema.test_relations import RELATION_TABLES
from tests.steam_manager.db.schema.test_requirements import REQUIREMENT_TABLES
from tests.steam_manager.db.schema.test_reviews import REVIEW_TABLES
from tests.steam_manager.db.schema.test_store_lists import STORE_LIST_TABLES

STEAM_TABLES: Final = frozenset(
    {
        *LOOKUPS,
        *APP_TABLES,
        *CLASSIFICATION_TABLES,
        *CREDIT_TABLES,
        *RELATION_TABLES,
        *OFFER_TABLES,
        *MEDIA_TABLES,
        *STORE_LIST_TABLES,
        *REQUIREMENT_TABLES,
        *REVIEW_TABLES,
        "app_compatibility_test",  # the notebook has no such table, so nothing compares it
    }
)
"""Every Steam table this release declares: the notebook's, each compared with it, and more."""


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
        "only in the notebook: tag.tagid #0: INTEGER notnull=1 pk=1 default=None hidden=0",
        "only declared: tag.tag_id #0: INTEGER notnull=1 pk=1 default=None hidden=0",
    ]


def test_a_changed_check_is_caught() -> None:
    """A CHECK whose values drift from the notebook's fails the comparison, quoting both."""
    metadata = MetaData()
    Table(
        "app_credit",
        metadata,
        Column("appid", Integer, primary_key=True),
        Column("role", Text, primary_key=True),
        Column("position", Integer, primary_key=True),
        Column("credit_id", Integer, nullable=False),
        CheckConstraint("role IN ('developer', 'publisher', 'franchize')"),
        sqlite_strict=True,
        sqlite_with_rowid=False,
    )

    found = differences("app_credit", metadata=metadata)

    assert (
        "only in the notebook: app_credit check (role IN ('developer', 'publisher', 'franchise'))"
        in found
    )
    assert (
        "only declared: app_credit check (role IN ('developer', 'publisher', 'franchize'))"
        in found
    )


def test_a_plain_column_for_a_generated_one_is_caught() -> None:
    """A column the notebook computes, declared as one that is stored, fails the comparison."""
    metadata = MetaData()
    Table(
        "offer",
        metadata,
        Column("kind", Text, primary_key=True),
        Column("id", Integer, primary_key=True),
    )
    Table(
        "offer_price",
        metadata,
        Column("kind", Text, primary_key=True),
        Column("id", Integer, primary_key=True),
        Column("country", Text, primary_key=True),
        *(
            Column(name, Integer)
            for name in (
                "included_game_count",
                "final_price_in_cents",
                "original_price_in_cents",
                "discount_pct",
                "price_before_bundle_discount",
                "bundle_discount_pct",
                "combined_discount_pct",
                "renewal_price_in_cents",
                "user_can_purchase_as_gift",
                "hide_discount_pct_for_compliance",
                "price_cannot_be_displayed_as_discount",
            )
        ),
        CheckConstraint("country IN ('BR', 'US')"),
        ForeignKeyConstraint(["kind", "id"], ["offer.kind", "offer.id"]),
        sqlite_strict=True,
        sqlite_with_rowid=False,
    )

    discount = "offer_price.discount_pct #6: INTEGER notnull=0 pk=0 default=None"
    assert differences("offer_price", metadata=metadata) == [
        (
            "only in the notebook: offer_price generated (CAST(ROUND(100.0 *"
            " (original_price_in_cents - final_price_in_cents) / original_price_in_cents)"
            " AS INTEGER))"
        ),
        f"only in the notebook: {discount} hidden=2",
        f"only declared: {discount} hidden=0",
    ]


def test_a_table_the_notebook_lacks_is_refused() -> None:
    """Comparing a table the notebook doesn't have is a mistake in the test, not a match."""
    with pytest.raises(LookupError, match="app_compatibility_test"):
        differences("app_compatibility_test")


def test_every_table_the_notebook_has_is_compared_with_it() -> None:
    """A table declared later can't skip the comparison by being left out of every list."""
    assert set(SteamBase.metadata.tables) == STEAM_TABLES


def test_every_table_is_strict() -> None:
    """Every Steam table refuses values of the wrong type, the new ones included."""
    with closing(build(SteamBase.metadata)) as connection:
        loose = connection.execute(
            "SELECT name FROM pragma_table_list"
            " WHERE schema = 'main' AND type = 'table' AND name NOT LIKE 'sqlite_%' AND NOT strict"
        ).fetchall()

    assert SteamBase.metadata.tables
    assert loose == []
