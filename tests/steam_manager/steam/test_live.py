"""
Live checks of every Steam endpoint against the real Steam: run with ``pytest -m live``.

They never run in CI. Each test module mirrors one source module, except this one: these checks
span store.py, reviews.py and community.py, and what they share is the network.
"""

import asyncio
import contextlib
import json
lazy from collections.abc import Awaitable, Callable

import pytest

from steam_manager.steam.community import followed_apps, resolve_steamid, wishlist
from steam_manager.steam.models.account import FollowedAppsAnswer, WishlistAnswer
from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.lookups import StoreCategoriesAnswer, TagListAnswer
from steam_manager.steam.models.reviews import (
    AppReviewsAnswer,
    CurrentPlayersAnswer,
    ReviewHistogramAnswer,
)
from steam_manager.steam.models.store_item import StoreItem
from steam_manager.steam.reviews import exact_review_answers, review_histogram
from steam_manager.steam.store import (
    current_players,
    get_items,
    list_apps,
    store_categories,
    tag_list,
)
from steam_manager.transport import Transport, make_client

pytestmark = pytest.mark.live

GABEN = 76561197960287930
"""A public SteamID64, of Steam's best-known account."""


def live[T](run: Callable[[Transport], Awaitable[T]]) -> T:
    """
    Run *run* with a transport on the real network.

    :param run: What to do with the transport.
    :return: What *run* returned.
    """

    async def with_client() -> T:
        async with make_client() as client:
            return await run(Transport(client))

    return asyncio.run(with_client())


def test_portal_2_is_fully_declared() -> None:
    """Portal 2's full entry from the Brazilian store has no field the models miss."""

    async def fetch(transport: Transport) -> StoreItem:
        answers = [answer async for answer in get_items(transport, [620], country="BR")]
        return StoreItem.model_validate_json(answers[0].body)

    item = live(fetch)

    assert item.id == 620
    assert unknown_fields(item) == []


def test_a_light_entry_is_fully_declared() -> None:
    """The first app of the Brazilian listing has no field the models miss."""

    async def first(transport: Transport) -> StoreItem:
        async with contextlib.aclosing(list_apps(transport, country="BR")) as listing:
            answer = await anext(listing)
        return StoreItem.model_validate_json(answer.body)

    assert unknown_fields(live(first)) == []


def test_the_lookups_are_fully_declared() -> None:
    """Category and tag names come back complete."""
    categories = StoreCategoriesAnswer.model_validate_json(live(store_categories).body)
    tags = TagListAnswer.model_validate_json(live(tag_list).body)

    assert unknown_fields(categories) == []
    assert unknown_fields(tags) == []
    assert categories.response is not None
    assert tags.response is not None
    assert categories.response.categories
    assert len(tags.response.tags) > 100


def test_portal_2_has_over_300_000_positive_reviews() -> None:
    """The exact totals across every language pass the milestone's own check."""

    async def fetch(transport: Transport) -> list[AppReviewsAnswer]:
        found = await exact_review_answers(transport, 620, is_free=False, review_count=320_000)
        return [AppReviewsAnswer.model_validate_json(answer.body) for answer in found]

    positives = [
        answer.response.query_summary.total_positive or 0
        for answer in live(fetch)
        if answer.response is not None and answer.response.query_summary is not None
    ]

    assert max(positives) > 300_000


def test_the_histogram_has_periods() -> None:
    """Portal 2's histogram has its history."""

    async def fetch(transport: Transport) -> ReviewHistogramAnswer:
        return ReviewHistogramAnswer.model_validate_json(
            (await review_histogram(transport, 620)).body
        )

    histogram = live(fetch)

    assert unknown_fields(histogram) == []
    assert histogram.results is not None
    assert histogram.results.rollups


def test_dota_2_has_players() -> None:
    """Dota 2 always has players."""

    async def fetch(transport: Transport) -> CurrentPlayersAnswer:
        return CurrentPlayersAnswer.model_validate_json(
            (await current_players(transport, 570)).body
        )

    answer = live(fetch)

    assert answer.response is not None
    assert (answer.response.player_count or 0) > 0


def test_a_vanity_url_resolves_to_its_steamid() -> None:
    """A vanity URL is resolved through the community's XML profile."""

    async def resolve(transport: Transport) -> int:
        return await resolve_steamid(transport, "https://steamcommunity.com/id/gabelogannewell")

    assert live(resolve) == GABEN


def test_a_public_accounts_lists_are_fully_declared() -> None:
    """A wishlist and followed apps come back without a login, in the declared shape."""

    async def fetch(transport: Transport) -> tuple[str, str]:
        return (await wishlist(transport, GABEN)).body, (
            await followed_apps(transport, GABEN)
        ).body

    wishlist_body, followed_body = live(fetch)

    assert unknown_fields(WishlistAnswer.model_validate_json(wishlist_body)) == []
    assert unknown_fields(FollowedAppsAnswer.model_validate_json(followed_body)) == []
    assert "response" in json.loads(wishlist_body)
