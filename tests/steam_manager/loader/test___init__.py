"""Tests for loading the archive into the database: choosing answers and replacing apps."""

from collections import Counter
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event, func, select

from steam_manager import loader
from steam_manager.answers import Kind
from steam_manager.archive import Archive
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppTag
from steam_manager.db.schema.offers import OfferPrice
from steam_manager.db.schema.progress import LoadedAnswer
from steam_manager.loader import ForeignKeyViolationError, Malformed, load, rebuild
from steam_manager.loader import write as writing
from tests.steam_manager.loader._archive import AT, changed, damage, put, recorded

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from sqlalchemy import Engine
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.orm import InstrumentedAttribute
    from sqlalchemy.pool import ConnectionPoolEntry

    from steam_manager.loader.store_item import Described
    from steam_manager.steam.models.store_item import StoreItem

COUNTRIES = ("BR", "US")
"""A profile in Brazil with the US as its fallback."""


def named(engine: Engine) -> dict[int, tuple[str | None, str | None, int | None]]:
    """
    Read the apps that have a name.

    :param engine: The profile database.
    :return: Each named app's name, describing store and Steam's result code.
    """
    with engine.connect() as connection:
        rows = connection.execute(
            select(App.appid, App.name, App.store_country, App.success).where(
                App.name.is_not(None)
            )
        )
        return {row.appid: (row.name, row.store_country, row.success) for row in rows}


def count(engine: Engine, column: InstrumentedAttribute[object]) -> int:
    """
    Count a table's rows.

    :param engine: The profile database.
    :param column: A column of the table.
    :return: How many rows it has.
    """
    with engine.connect() as connection:
        return int(connection.scalar(select(func.count(column))) or 0)


def test_a_load_fills_the_tables(archive: Archive, engine: Engine) -> None:
    """Full and light entries become rows, and a healthy load reports nothing."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    put(archive, Kind.STORE_ITEM, "570", "BR", recorded("store_item/570-BR.json"))
    put(archive, Kind.STORE_ITEM_LIGHT, "10", "BR", recorded("store_item_light/10-BR.json"))

    report = load(archive, engine, countries=COUNTRIES)

    apps = named(engine)
    assert apps[620] == ("Portal 2", "BR", 1)
    assert apps[570] == ("Dota 2", "BR", 1)
    assert apps[10] == ("Counter-Strike", "BR", 1)
    assert report.unknown == Counter()
    assert not +report.mismatches
    assert not report.malformed
    assert report.loaded["app"] >= 3
    assert report.blank_parents["tag"] > 0
    assert count(engine, LoadedAnswer.key) == 3


def test_countries_are_needed(archive: Archive, engine: Engine) -> None:
    """A load without a home country can't rank answers."""
    with pytest.raises(ValueError, match="home country"):
        load(archive, engine, countries=())


def test_a_second_load_parses_nothing(
    archive: Archive, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With nothing new in the archive, a load leaves every app as it is."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    load(archive, engine, countries=COUNTRIES)
    calls: list[int] = []
    describe = loader.describe

    def counted(
        item: StoreItem, *, country: str, category_types: Mapping[int, int], path: str = ""
    ) -> Described:
        calls.append(1)
        return describe(item, country=country, category_types=category_types, path=path)

    monkeypatch.setattr(loader, "describe", counted)

    load(archive, engine, countries=COUNTRIES)

    assert not calls


def test_full_beats_light_and_home_beats_fallback(archive: Archive, engine: Engine) -> None:
    """A fallback store's full entry beats the home store's light one, and home beats both."""
    light = '{"id":620,"item_type":0,"success":1,"visible":true,"name":"Light Portal","type":0}'
    put(archive, Kind.STORE_ITEM_LIGHT, "620", "BR", light)
    put(archive, Kind.STORE_ITEM, "620", "US", recorded("store_item/620-US.json"))
    load(archive, engine, countries=COUNTRIES)
    assert named(engine)[620] == ("Portal 2", "US", 1)

    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    load(archive, engine, countries=COUNTRIES)

    assert named(engine)[620] == ("Portal 2", "BR", 1)


def test_a_newer_answer_from_another_source_wins(archive: Archive, engine: Engine) -> None:
    """Within one rank and country, the latest answer wins, whichever source sent it."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    renamed = changed("store_item/620-BR.json", lambda answer: answer.update(name="Portal Two"))
    later = AT + timedelta(hours=1)
    put(archive, Kind.STORE_ITEM, "620", "BR", renamed, at=later, source="kaggle")

    load(archive, engine, countries=COUNTRIES)

    assert named(engine)[620] == ("Portal Two", "BR", 1)


def test_an_app_the_home_store_doesnt_sell_comes_from_the_fallback(
    archive: Archive, engine: Engine
) -> None:
    """The home store's empty answer ranks below a fallback store's full entry."""

    def as_12170(answer: dict[str, object]) -> None:
        answer.update(id=12170, appid=12170)

    put(archive, Kind.STORE_ITEM, "12170", "BR", recorded("store_item/12170-BR.json"))
    put(archive, Kind.STORE_ITEM, "12170", "US", changed("store_item/620-US.json", as_12170))

    load(archive, engine, countries=COUNTRIES)

    assert named(engine)[12170] == ("Portal 2", "US", 1)


def test_an_app_only_failed_answers_describe_keeps_its_bare_row(
    archive: Archive, engine: Engine
) -> None:
    """With nothing better, the home store's empty answer is the app's row."""
    put(archive, Kind.STORE_ITEM, "12170", "BR", recorded("store_item/12170-BR.json"))

    load(archive, engine, countries=COUNTRIES)

    with engine.connect() as connection:
        row = connection.execute(
            select(App.success, App.store_country).where(App.appid == 12170)
        ).one()
    assert tuple(row) == (15, "BR")


def test_a_removed_tag_disappears_and_shared_prices_stay(archive: Archive, engine: Engine) -> None:
    """Loading an app again replaces its own rows, and leaves what other apps share."""

    def as_621(answer: dict[str, object]) -> None:
        answer.update(id=621, appid=621)

    def without_first_tag(answer: dict[str, object]) -> None:
        tags, tagids = answer["tags"], answer["tagids"]
        assert isinstance(tags, list)
        assert isinstance(tagids, list)
        answer.update(tags=tags[1:], tagids=tagids[1:])

    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    put(archive, Kind.STORE_ITEM, "621", "BR", changed("store_item/620-BR.json", as_621))
    load(archive, engine, countries=COUNTRIES)
    first = count(engine, AppTag.tagid)
    newer = changed("store_item/620-BR.json", without_first_tag)
    put(archive, Kind.STORE_ITEM, "620", "BR", newer, at=AT + timedelta(days=1))

    load(archive, engine, countries=COUNTRIES)

    with engine.connect() as connection:
        tagged = connection.scalars(select(AppTag.appid).where(AppTag.tagid == 4182)).all()
        bundle = connection.scalar(
            select(func.count()).where(
                OfferPrice.kind == "bundle", OfferPrice.id == 234, OfferPrice.country == "BR"
            )
        )
    assert tagged == [621]
    assert count(engine, AppTag.tagid) == first - 1
    assert bundle == 1


def test_an_interrupted_load_commits_nothing(
    archive: Archive, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load that stops halfway leaves nothing behind, and the next one does it all."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    put(archive, Kind.STORE_ITEM, "570", "BR", recorded("store_item/570-BR.json"))
    calls: list[int] = []
    describe = loader.describe

    def failing(
        item: StoreItem, *, country: str, category_types: Mapping[int, int], path: str = ""
    ) -> Described:
        calls.append(1)
        if len(calls) == 2:
            message = "a simulated crash"
            raise RuntimeError(message)
        return describe(item, country=country, category_types=category_types, path=path)

    monkeypatch.setattr(loader, "LOAD_BATCH", 1)
    monkeypatch.setattr(loader, "describe", failing)
    with pytest.raises(RuntimeError, match="a simulated crash"):
        load(archive, engine, countries=COUNTRIES)
    assert count(engine, App.appid) == 0
    assert count(engine, LoadedAnswer.key) == 0
    monkeypatch.setattr(loader, "describe", describe)

    load(archive, engine, countries=COUNTRIES)

    assert {620, 570} <= named(engine).keys()


def test_malformed_answers_are_reported_and_skipped(
    archive: Archive, engine: Engine, tmp_path: Path
) -> None:
    """A truncated answer and a damaged row are named, never shown; the next candidate loads."""
    put(archive, Kind.STORE_ITEM, "620", "BR", '{"id": 620, "name": "Secret Por')
    put(archive, Kind.STORE_ITEM, "620", "US", recorded("store_item/620-US.json"))
    put(archive, Kind.STORE_ITEM_LIGHT, "10", "BR", recorded("store_item_light/10-BR.json"))
    damage(tmp_path / "archive.sqlite", "10")

    report = load(archive, engine, countries=COUNTRIES)

    assert named(engine)[620] == ("Portal 2", "US", 1)
    by_key = {(problem.kind, problem.key): problem for problem in report.malformed}
    assert by_key["store_item", "620"].country == "BR"
    assert "json_invalid" in by_key["store_item", "620"].reason
    assert by_key["store_item_light", "10"] == Malformed(
        "steam", "store_item_light", "10", "BR", "damaged"
    )
    assert all("Secret" not in problem.reason for problem in report.malformed)


def test_a_nested_record_fills_a_gap(archive: Archive, engine: Engine) -> None:
    """An app only a short record describes gets that record, until its own entry arrives."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    load(archive, engine, countries=COUNTRIES)
    assert named(engine)[104600] == ("Portal 2 - The Final Hours", "BR", 1)

    own = '{"id":104600,"item_type":0,"success":1,"visible":true,"name":"Own Name","type":0}'
    put(archive, Kind.STORE_ITEM_LIGHT, "104600", "BR", own)
    load(archive, engine, countries=COUNTRIES)

    assert named(engine)[104600] == ("Own Name", "BR", 1)


def test_a_foreign_key_violation_rolls_back(
    archive: Archive, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load that would leave a reference dangling fails before its commit, writing nothing."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    monkeypatch.setattr(writing, "FILLED_PARENTS", writing.FILLED_PARENTS - {"tag"})

    with pytest.raises(ForeignKeyViolationError, match="app_tag"):
        load(archive, engine, countries=COUNTRIES)

    assert count(engine, App.appid) == 0


def test_foreign_keys_are_on_again_after_a_load(archive: Archive, engine: Engine) -> None:
    """Every other use of the database keeps its foreign keys enforced."""
    load(archive, engine, countries=COUNTRIES)

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_rebuild_forgets_what_the_archive_lost(
    archive: Archive, engine: Engine, tmp_path: Path
) -> None:
    """Replaying an emptied archive leaves the Steam tables empty."""
    put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))
    load(archive, engine, countries=COUNTRIES)

    with Archive(tmp_path / "empty.sqlite") as empty:
        rebuild(empty, engine, countries=COUNTRIES)

    assert count(engine, App.appid) == 0
    assert count(engine, LoadedAnswer.key) == 0


def test_an_answer_whose_id_isnt_its_key_is_malformed(archive: Archive, engine: Engine) -> None:
    """An answer archived under one appid but describing another is skipped, not misfiled."""
    put(archive, Kind.STORE_ITEM, "621", "BR", recorded("store_item/620-BR.json"))

    report = load(archive, engine, countries=COUNTRIES)

    assert report.malformed == [
        Malformed("steam", "store_item", "621", "BR", "its id isn't its key")
    ]
    assert 621 not in named(engine)


def test_an_answer_describe_refuses_is_malformed(archive: Archive, engine: Engine) -> None:
    """An answer missing a value a row needs is skipped, and the next candidate loads."""

    def nameless_developer(answer: dict[str, object]) -> None:
        basic = answer["basic_info"]
        assert isinstance(basic, dict)
        basic["developers"] = [{"creator_clan_account_id": 4}]

    put(
        archive,
        Kind.STORE_ITEM,
        "620",
        "BR",
        changed("store_item/620-BR.json", nameless_developer),
    )
    put(archive, Kind.STORE_ITEM, "620", "US", recorded("store_item/620-US.json"))

    report = load(archive, engine, countries=COUNTRIES)

    assert [problem.reason for problem in report.malformed] == [
        "basic_info.developers[] has no name"
    ]
    assert named(engine)[620] == ("Portal 2", "US", 1)


def _open_a_transaction(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """
    Leave a new connection inside a transaction, where SQLite ignores ``PRAGMA foreign_keys``.

    :param connection: The SQLite connection.
    :param _record: Its pool entry, unused.
    """
    cursor = connection.cursor()
    cursor.execute("UPDATE loaded_answer SET key = key")
    cursor.close()


def test_a_load_refuses_to_run_with_foreign_keys_on(archive: Archive, engine: Engine) -> None:
    """With foreign keys on, rows couldn't load in any order: the load stops before writing."""
    engine.dispose()
    event.listen(engine, "connect", _open_a_transaction)

    with pytest.raises(RuntimeError, match="foreign keys are still on"):
        load(archive, engine, countries=COUNTRIES)
