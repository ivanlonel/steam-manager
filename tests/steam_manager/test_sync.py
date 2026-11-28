"""Tests for the sync: what it asks Steam, what it archives, and what it loads."""

import asyncio
import json
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import func, select

from steam_manager.answers import Kind
from steam_manager.archive import Archive
from steam_manager.db.schema.account import WishlistItem
from steam_manager.db.schema.apps import App
from steam_manager.profiles import Settings, create_profile, open_profile
from steam_manager.steam.community import INDIVIDUAL_BASE
from steam_manager.steam.webapi import STEAM
from steam_manager.sync import Step, stale, sync
from tests.steam_manager._steam import FakeSteam, fake_transport, sold
from tests.steam_manager.loader._archive import put

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from pathlib import Path

    import httpx

    from steam_manager.profiles import OpenProfile
    from steam_manager.sync import SyncReport

STEAMID: Final = INDIVIDUAL_BASE + 1234
"""The profile's SteamID64."""
ACCOUNT_LISTS: Final = frozenset({Step.LOOKUPS, Step.WISHLIST, Step.FOLLOWED})
"""The steps that ask one request each."""


@contextmanager
def opened(tmp_path: Path, countries: Sequence[str] = ("BR", "US")) -> Generator[OpenProfile]:
    """
    Create a profile and open it.

    :param tmp_path: The data folder.
    :param countries: Its home country, then its fallback countries.
    :yield: The open profile.
    """
    home, *fallbacks = countries
    settings = Settings(steamid=STEAMID, home_country=home, fallback_countries=tuple(fallbacks))
    with open_profile(create_profile(tmp_path, settings)) as profile:
        yield profile


@pytest.fixture(name="profile")
def profile_fixture(tmp_path: Path) -> Generator[OpenProfile]:
    """
    Open a new profile in Brazil, with the US as its fallback.

    :param tmp_path: The data folder.
    :yield: The open profile.
    """
    with opened(tmp_path) as profile:
        yield profile


def run(profile: OpenProfile, steam: FakeSteam, **options: object) -> SyncReport:
    r"""
    Sync a profile against a fake Steam.

    :param profile: The profile.
    :param steam: The fake Steam.
    :param \*\*options: The sync's keyword arguments.
    :return: The sync's report.
    """
    return asyncio.run(sync(profile, fake_transport(steam), **options))  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # each test passes the options it means


def wishlist_apps(profile: OpenProfile) -> list[int]:
    """
    Read the wishlist's apps.

    :param profile: The profile.
    :return: The appids, in the wishlist's order.
    """
    with profile.engine.connect() as connection:
        query = select(WishlistItem.appid).order_by(WishlistItem.position)
        return list(connection.scalars(query))


def archived(profile: OpenProfile, kind: Kind, country: str = "") -> set[str]:
    """
    List the keys of one kind the archive holds in one country.

    :param profile: The profile.
    :param kind: The kind.
    :param country: The country, or ``""``.
    :return: The keys.
    """
    return set(profile.archive.fetched_at(STEAM, kind, country=country))


def test_stale_keys(tmp_path: Path) -> None:
    """A key is stale when missing, or as old as the maximum age or older, in its country."""
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    hour = timedelta(hours=1)
    with Archive(tmp_path / "archive.sqlite") as archive:
        put(archive, Kind.CURRENT_PLAYERS, "1", "", "{}", at=now - 2 * hour)
        put(archive, Kind.CURRENT_PLAYERS, "2", "", "{}", at=now - hour)
        put(archive, Kind.CURRENT_PLAYERS, "3", "", "{}", at=now - hour + timedelta(seconds=1))
        put(archive, Kind.CURRENT_PLAYERS, "4", "BR", "{}", at=now)

        found = stale(
            archive,
            Kind.CURRENT_PLAYERS,
            ["1", "2", "3", "4", "5"],
            country="",
            max_age=hour,
            now=now,
        )

    assert found == ["1", "2", "4", "5"]


def test_a_first_sync_of_the_account_lists(profile: OpenProfile) -> None:
    """The lookups and the account's lists are asked once each, archived and loaded."""
    steam = FakeSteam()

    report = run(profile, steam, steps=ACCOUNT_LISTS)

    assert report.fetched == Counter(
        {"store_categories": 1, "tags": 1, "wishlist": 1, "followed_apps": 1}
    )
    assert (report.failed, report.stopped) == ([], None)
    assert wishlist_apps(profile) == [620, 400, 70]
    assert report.load.loaded["wishlist_item"] == 3
    assert steam.asked[0] == ("/IStoreBrowseService/GetStoreCategories/v1/", {"elanguage": "0"})


def test_a_second_sync_asks_nothing(profile: OpenProfile) -> None:
    """What a sync fetched is fresh for the next one."""
    steam = FakeSteam()
    run(profile, steam, steps=ACCOUNT_LISTS)

    report = run(profile, steam, steps=ACCOUNT_LISTS)

    assert len(steam.asked) == 4
    assert report.fetched == Counter()


def test_force_asks_again(profile: OpenProfile) -> None:
    """A forced sync asks what is fresh too."""
    steam = FakeSteam()
    run(profile, steam, steps=ACCOUNT_LISTS)

    report = run(profile, steam, steps=ACCOUNT_LISTS, force=True)

    assert len(steam.asked) == 8
    assert report.fetched.total() == 4


def test_steps_run_in_their_own_order(profile: OpenProfile) -> None:
    """Steps run in the sync's order, whatever order they are given in."""
    steam = FakeSteam()

    run(profile, steam, steps=[Step.FOLLOWED, Step.LOOKUPS])

    assert steam.methods() == ["GetStoreCategories", "GetTagList", "GetGamesFollowed"]


def test_a_failed_request_is_reported_and_the_sync_goes_on(profile: OpenProfile) -> None:
    """A request that fails is reported by its endpoint alone, and the rest of the sync lands."""

    def fail(request: httpx.Request) -> int | None:
        return 400 if request.url.path.endswith("/GetTagList/v1/") else None

    report = run(profile, FakeSteam(fail=fail), steps=ACCOUNT_LISTS)

    assert len(report.failed) == 1
    assert "GetTagList" in report.failed[0]
    assert "?" not in report.failed[0]
    assert wishlist_apps(profile) == [620, 400, 70]


def test_the_catalog_lists_every_country(profile: OpenProfile) -> None:
    """A fallback's light entries are archived only for the apps the home store doesn't list."""
    steam = FakeSteam(listings={"BR": [10, 20], "US": [20, 30]})

    report = run(profile, steam, steps={Step.CATALOG})

    assert archived(profile, Kind.STORE_ITEM_LIGHT, "BR") == {"10", "20"}
    assert archived(profile, Kind.STORE_ITEM_LIGHT, "US") == {"30"}
    assert archived(profile, Kind.LISTING, "BR") == archived(profile, Kind.LISTING, "US") == {""}
    assert report.fetched == Counter({"store_item_light": 3, "listing": 2})
    with profile.engine.connect() as connection:
        listed = {row.appid: row.is_listed for row in connection.execute(select(App))}
    assert listed == {10: True, 20: True, 30: True}


def test_a_fresh_listing_isnt_asked_again(profile: OpenProfile) -> None:
    """A country listed within its maximum age is not listed again."""
    steam = FakeSteam(listings={"BR": [10], "US": [30]})
    run(profile, steam, steps={Step.CATALOG})

    run(profile, steam, steps={Step.CATALOG})

    assert steam.methods() == ["Query", "Query"]


def test_a_listing_that_misses_its_total_is_skipped(profile: OpenProfile) -> None:
    """A listing far from Steam's total is reported and not archived; other countries list."""
    steam = FakeSteam(listings={"BR": [10, 20], "US": [20, 30]}, totals={"BR": 5000})

    report = run(profile, steam, steps={Step.CATALOG})

    assert len(report.failed) == 1
    assert "BR" in report.failed[0]
    assert archived(profile, Kind.LISTING, "BR") == set()
    assert archived(profile, Kind.LISTING, "US") == {""}


def test_light_entries_are_archived_a_page_at_a_time(profile: OpenProfile) -> None:
    """A listing that fails on its second page keeps its first page's light entries."""

    def fail(request: httpx.Request) -> int | None:
        second_page = '"start":1000' in request.url.params.get("input_json", "")
        return 400 if second_page else None

    steam = FakeSteam(listings={"BR": range(1, 1501)}, fail=fail)

    report = run(profile, steam, steps={Step.CATALOG})

    assert len(archived(profile, Kind.STORE_ITEM_LIGHT, "BR")) == 1000
    assert archived(profile, Kind.LISTING, "BR") == set()
    assert len(report.failed) == 1


def first_asked(request: httpx.Request) -> int | None:
    """
    Tell which app a ``GetItems`` request asks first.

    :param request: Any request.
    :return: The first appid of a ``GetItems`` request, else ``None``.
    """
    if not request.url.path.endswith("/GetItems/v1/"):
        return None
    return int(json.loads(request.url.params["input_json"])["ids"][0]["appid"])


def test_account_apps_and_their_references_get_full_entries(tmp_path: Path) -> None:
    """The apps the account apps point at get full entries too, once, but not included apps."""
    steam = FakeSteam(wishlist=[620, 2778580], followed=[1778820])
    with opened(tmp_path, ["BR"]) as profile:
        run(profile, steam, steps={Step.WISHLIST, Step.FOLLOWED, Step.APPS})

    asked = steam.items_asked("BR")
    account = [620, 1778820, 2778580]
    # 620's DLC, 2778580's parent game, and 1778820's demo.
    assert asked[:3] == account
    assert {323180, 1245620, 2524440} <= set(asked[3:])
    assert len(asked) == len(set(asked))
    # Apps 620 and 2778580 include, and nothing points at otherwise.
    assert not {104600, 240, 10, 80, 2778590, 2855520} & set(asked)


def test_fallbacks_ask_only_what_earlier_countries_dont_sell(tmp_path: Path) -> None:
    """A fallback asks for what no earlier country sells; what nobody sells, every one asks."""
    items = {(620, "BR"): sold(620), (12170, "US"): sold(12170)}
    steam = FakeSteam(wishlist=[620, 12170, 99], followed=[], items=items)
    with opened(tmp_path, ["BR", "US", "JP"]) as profile:
        run(profile, steam, steps={Step.WISHLIST, Step.APPS})

    assert steam.items_asked("BR") == [99, 620, 12170]
    assert steam.items_asked("US") == [99, 12170]
    assert steam.items_asked("JP") == [99]


def test_a_failed_batch_skips_only_that_batch(tmp_path: Path) -> None:
    """A batch that fails is reported, and the next batch's apps are still archived."""
    steam = FakeSteam(
        wishlist=range(1, 151), followed=[], fail=lambda r: 400 if first_asked(r) == 1 else None
    )
    with opened(tmp_path, ["BR"]) as profile:
        report = run(profile, steam, steps={Step.WISHLIST, Step.APPS})
        entries = archived(profile, Kind.STORE_ITEM, "BR")

    assert entries == {str(appid) for appid in range(101, 151)}
    assert len(report.failed) == 1
    assert "GetItems" in report.failed[0]


def test_a_failure_streak_stops_the_sync(tmp_path: Path) -> None:
    """A host failing ten requests in a row stops the sync; what came is loaded, and resumed."""

    def fail(request: httpx.Request) -> int | None:
        appid = first_asked(request)
        return 503 if appid is not None and appid > 200 else None

    steam = FakeSteam(wishlist=range(1, 1201), followed=[], fail=fail)
    steps = {Step.WISHLIST, Step.APPS}
    with opened(tmp_path, ["BR"]) as profile:
        report = run(profile, steam, steps=steps)
        with profile.engine.connect() as connection:
            described = connection.scalar(select(func.count()).where(App.success.is_not(None)))
        stopped_after = steam.methods()
        steam.asked.clear()
        steam.fail = lambda _request: None
        run(profile, steam, steps=steps)

    assert report.stopped is not None
    assert "api.steampowered.com" in report.stopped
    # Two batches, then ten that fail after five retries each, and nothing more.
    assert stopped_after == ["GetWishlist"] + ["GetItems"] * 62
    assert described == 200
    # The account apps still stale; then what 570 and 620, among them, point at.
    assert steam.items_asked("BR")[:1000] == list(range(201, 1201))


def test_current_players_for_account_apps(profile: OpenProfile) -> None:
    """How many play each account app is fetched, and stored on the app."""
    run(profile, FakeSteam(), steps={Step.WISHLIST, Step.FOLLOWED, Step.APPS})

    with profile.engine.connect() as connection:
        players = connection.execute(
            select(App.appid, App.current_players).where(App.appid.in_([620, 400, 70]))
        )
        found = {row.appid: row.current_players for row in players}

    assert archived(profile, Kind.CURRENT_PLAYERS) == {"620", "400", "70"}
    assert found == {620: 7, 400: 7, 70: 7}


def test_genre_names_are_asked_once_per_unnamed_genre(tmp_path: Path) -> None:
    """One app is asked per genre without a name; its other genres need no call of their own."""
    info = {
        (appid, "BR"): sold(appid, extra_details={"links_and_info": {"genreids": genres}})
        for appid, genres in ((620, [1, 25]), (2, [25, 37]))
    }
    steam = FakeSteam(wishlist=[620, 2], followed=[], items=info)
    with opened(tmp_path, ["BR"]) as profile:
        run(profile, steam, steps={Step.WISHLIST, Step.APPS})

    asked = [params["appids"] for path, params in steam.asked if path == "/api/appdetails"]
    assert asked == ["620", "2"]
