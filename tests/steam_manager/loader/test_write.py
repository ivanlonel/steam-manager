"""Tests for writing a load's rows, each table by its rule."""

from collections import Counter
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import insert, select

from steam_manager.db.engine import open_database
from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppTag
from steam_manager.db.schema.creators import AppCredit, Credit
from steam_manager.db.schema.lookups import ReviewScore, Tag
from steam_manager.db.schema.offers import Offer
from steam_manager.loader.rows import Rows
from steam_manager.loader.store_item import CreditRef, Described
from steam_manager.loader.write import ForeignKeyViolationError, Writer, check_foreign_keys
from steam_manager.steam.models.store_item import StoreItem

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Connection


@pytest.fixture(name="connection")
def connection_fixture(tmp_path: Path) -> Iterator[Connection]:
    """
    Open a profile database with every Steam table, foreign keys off, in a transaction.

    :param tmp_path: Where the file goes.
    :yield: The connection, as a load holds it.
    """
    engine = open_database(tmp_path / "steam.sqlite")
    SteamBase.metadata.create_all(engine)
    with engine.connect() as connection, connection.begin():
        # First in the transaction: SQLite ignores the pragma once a write has begun one.
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        yield connection
    engine.dispose()


def app(appid: int, *tags: tuple[int, int], credited: list[CreditRef] | None = None) -> Described:
    r"""
    Describe an app with a few tags.

    :param appid: The app.
    :param \*tags: Its tags, as id and weight.
    :param credited: Its credits.
    :return: What the loader makes of it.
    """
    described = Described(StoreItem(id=appid), credits=credited or [])
    described.rows.add(App, appid=appid, name=f"App {appid}")
    for tagid, weight in tags:
        described.rows.add(AppTag, appid=appid, tagid=tagid, weight=weight)
    return described


def test_references_get_blank_parents(connection: Connection) -> None:
    """A reference to an app or tag nothing describes gets a blank row to point at."""
    rows = Rows()
    rows.add(AppTag, appid=999, tagid=5, weight=1)
    writer = Writer(connection, home="BR")

    writer.write(rows, home=True)

    assert connection.scalars(select(App.appid)).all() == [999]
    assert connection.scalars(select(Tag.tagid)).all() == [5]
    assert writer.blank_parents == Counter({"app": 1, "tag": 1})
    assert writer.loaded == Counter({"app_tag": 1})


def test_a_repeat_within_an_answer_keeps_the_first(connection: Connection) -> None:
    """A row Steam repeats in one answer is stored once, as the notebook stored it."""
    writer = Writer(connection, home="BR")

    writer.apps([(app(1, (5, 10), (5, 20)), "BR")])

    assert connection.scalars(select(AppTag.weight)).all() == [10]


def test_an_app_is_replaced_in_place(connection: Connection) -> None:
    """A tag Steam removed disappears when the app is loaded again."""
    writer = Writer(connection, home="BR")
    writer.apps([(app(1, (5, 10), (6, 10)), "BR"), (app(2, (6, 10)), "BR")])

    writer.apps([(app(1, (5, 10)), "BR")])

    stored = connection.execute(select(AppTag.appid, AppTag.tagid).order_by(AppTag.appid))
    assert [tuple(row) for row in stored] == [(1, 5), (2, 6)]


def test_an_app_another_in_its_batch_points_at_keeps_its_row(connection: Connection) -> None:
    """A reference from an answer abroad never leaves a blank row where the app's own goes."""
    writer = Writer(connection, home="BR")
    abroad = app(2)
    abroad.rows.tables["app"][0]["parent_appid"] = 1

    writer.apps([(abroad, "US"), (app(1), "BR")])

    assert connection.scalar(select(App.name).where(App.appid == 1)) == "App 1"


def test_home_offer_fields_overwrite_and_others_fill_blanks(connection: Connection) -> None:
    """The home store's word on an offer's country-dependent fields stands; others fill gaps."""
    writer = Writer(connection, home="BR")

    def offer(*, home: bool, **values: object) -> None:
        rows = Rows()
        rows.add(Offer, kind="package", id=7, **values)
        writer.write(rows, home=home)

    def stored() -> tuple[object, ...]:
        return tuple(connection.execute(select(Offer.success, Offer.name)).one())

    offer(home=False, success=15)
    assert stored() == (15, None)
    offer(home=True, success=1, name="Home")
    assert stored() == (1, "Home")
    offer(home=False, success=15, name="Abroad")
    assert stored() == (1, "Abroad")


def test_a_lookup_conflict_is_a_mismatch(connection: Connection) -> None:
    """Two labels for one review score are reported, and the newer one is kept."""
    writer = Writer(connection, home="BR")
    for label in ("Positive", "Positive", "Very Positive"):
        rows = Rows()
        rows.add(ReviewScore, review_score=6, label=label)
        writer.write(rows, home=True)

    assert writer.findings.mismatches == Counter({"review_score.label": 1})
    assert connection.scalar(select(ReviewScore.label)) == "Very Positive"


def test_a_stored_lookup_is_compared_too(connection: Connection) -> None:
    """A label already in the database counts as known when a load begins."""
    connection.execute(insert(ReviewScore), [{"review_score": 6, "label": "Positive"}])
    writer = Writer(connection, home="BR")
    rows = Rows()
    rows.add(ReviewScore, review_score=6, label="Mostly Positive")

    writer.write(rows, home=True)

    assert writer.findings.mismatches == Counter({"review_score.label": 1})


def test_credits_get_ids_once(connection: Connection) -> None:
    """A credit is numbered the first time it appears, and every app after shares it."""
    valve = CreditRef("developer", 0, "Valve", None)
    writer = Writer(connection, home="BR")

    writer.apps([(app(1, credited=[valve]), "BR")])
    writer.apps([(app(2, credited=[valve, CreditRef("publisher", 0, "Valve", 4)]), "BR")])

    names = connection.execute(select(Credit.name, Credit.creator_id).order_by(Credit.credit_id))
    assert [tuple(row) for row in names] == [("Valve", None), ("Valve", 4)]
    ids = connection.execute(select(AppCredit.appid, AppCredit.role, AppCredit.credit_id))
    assert sorted(tuple(row) for row in ids) == [
        (1, "developer", 1),
        (2, "developer", 1),
        (2, "publisher", 2),
    ]
    assert writer.blank_parents["creator"] == 1


def test_a_broken_reference_is_refused(connection: Connection) -> None:
    """A load that would leave a reference dangling fails, naming the table, before its commit."""
    connection.execute(insert(AppTag), [{"appid": 999, "tagid": 5}])

    with pytest.raises(ForeignKeyViolationError, match=r"app_tag \(2\)") as raised:
        check_foreign_keys(connection)

    assert raised.value.violations == {"app_tag": 2}


def test_intact_references_pass(connection: Connection) -> None:
    """A load whose every reference resolves passes the check."""
    rows = Rows()
    rows.add(AppTag, appid=1, tagid=5)
    Writer(connection, home="BR").write(rows, home=True)

    check_foreign_keys(connection)
