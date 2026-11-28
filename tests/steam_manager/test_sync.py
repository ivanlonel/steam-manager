"""Tests for the sync: what it asks Steam, what it archives, and what it loads."""

import asyncio
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import select

from steam_manager.answers import Kind
from steam_manager.archive import Archive
from steam_manager.db.schema.account import WishlistItem
from steam_manager.profiles import Settings, create_profile, open_profile
from steam_manager.steam.community import INDIVIDUAL_BASE
from steam_manager.sync import Step, stale, sync
from tests.steam_manager._steam import FakeSteam, fake_transport
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
