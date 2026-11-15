"""Tests for the store endpoints: the catalog listing, store items and lookups."""

import asyncio
import json
from typing import Any
lazy from collections.abc import AsyncIterator, Callable, Mapping, Sequence

import httpx
import pytest

from steam_manager.answers import Answer, Kind
from steam_manager.steam.store import (
    FULL_DATA_REQUEST,
    ListingMismatchError,
    app_genres,
    current_players,
    get_items,
    list_apps,
    store_categories,
    tag_list,
)
from steam_manager.transport import RequestFailedError
from tests._fakes import FakeClock, answers, recorder, transport_for


def collect(generator: AsyncIterator[Answer]) -> list[Answer]:
    """
    Run an answer generator to its end.

    :param generator: The generator.
    :return: Everything it yielded.
    """

    async def drain() -> list[Answer]:
        return [answer async for answer in generator]

    return asyncio.run(drain())


def query_pages(
    pages: Sequence[Sequence[int]], total: int, *, extra: Mapping[str, object] | None = None
) -> tuple[Callable[[httpx.Request], httpx.Response], list[Any]]:
    """
    Make a handler answering ``Query`` with one page of apps per request.

    :param pages: The ids on each page, in order.
    :param total: The total Steam reports on every page.
    :param extra: Fields to add to every page's ``response``, as Steam's ``ids`` is.
    :return: The handler and the decoded ``input_json`` of each request.
    """
    asked: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(json.loads(request.url.params["input_json"]))
        ids = pages[len(asked) - 1]
        items = [{"id": n, "name": f"App {n}", "type": 0} for n in ids]
        metadata = {"total_matching_records": total, "start": 0, "count": len(ids)}
        found = {"metadata": metadata, "ids": [{"appid": n} for n in ids], "store_items": items}
        return httpx.Response(200, json={"response": found | dict(extra or {})})

    return handler, asked


def test_list_apps_reports_page_fields_nothing_stores(caplog: pytest.LogCaptureFixture) -> None:
    """Only the items reach the archive, so a new field around them is reported once, here."""
    extra = {"new_field": 1, "empty": [], "metadata": {"total_matching_records": 1001, "odd": 3}}
    handler, _ = query_pages([range(1000), [1000]], total=1001, extra=extra)

    collect(list_apps(transport_for(handler, FakeClock()), country="BR"))

    reports = [
        record.getMessage() for record in caplog.records if "nothing stores" in record.getMessage()
    ]
    assert reports == ["Query sent fields nothing stores: metadata.odd, new_field"]


def test_get_items_reports_batch_fields_nothing_stores(caplog: pytest.LogCaptureFixture) -> None:
    """A new field beside GetItems' items is reported."""

    def handler(_request: httpx.Request) -> httpx.Response:
        found = {"store_items": [{"id": 620}], "explanation": "why some are missing"}
        return httpx.Response(200, json={"response": found})

    collect(get_items(transport_for(handler, FakeClock()), [620], country="BR"))

    assert "GetItems sent fields nothing stores: explanation" in caplog.text


def test_list_apps_asks_ascending_appid_pages_of_a_thousand() -> None:
    """The listing sorts by appid, since the default sort repeats and skips apps when paged."""
    handler, asked = query_pages([[10, 20]], total=2)

    collect(list_apps(transport_for(handler, FakeClock()), country="BR"))

    kinds = ("include_games", "include_mods", "include_software")
    query = {"start": 0, "count": 1000, "sort": 2}
    assert asked[0] == {
        "query": query | {"filters": {"type_filters": dict.fromkeys(kinds, True)}},
        "context": {"language": "english", "country_code": "BR"},
        "data_request": {"include_reviews": True},
    }


def test_list_apps_pages_until_the_total() -> None:
    """Pages are asked half a second apart until the reported total is reached."""
    clock = FakeClock()
    pages = [range(1000), range(1000, 2000), range(2000, 2500)]
    handler, asked = query_pages(pages, total=2500)

    found = collect(list_apps(transport_for(handler, clock), country="US", language="brazilian"))

    assert [page["query"]["start"] for page in asked] == [0, 1000, 2000]
    assert clock.sleeps == pytest.approx([0.5, 0.5])
    assert len(found) == 2501


def test_list_apps_yields_a_light_entry_per_app() -> None:
    """Each listed app becomes a light entry of its country, keyed by its id."""
    handler, _ = query_pages([[620]], total=1)

    first = collect(list_apps(transport_for(handler, FakeClock()), country="BR"))[0]

    assert (first.kind, first.key, first.country) == (Kind.STORE_ITEM_LIGHT, "620", "BR")
    assert json.loads(first.body) == {"id": 620, "name": "App 620", "type": 0}


def test_list_apps_drops_repeated_ids() -> None:
    """An app that shows up on two pages is listed once."""
    handler, _ = query_pages([range(1000), [999, 1000]], total=1001)

    found = collect(list_apps(transport_for(handler, FakeClock()), country="BR"))

    assert [answer.key for answer in found].count("999") == 1


def test_list_apps_ends_with_the_listing() -> None:
    """The last answer is the listing: which appids the country lists, and its total."""
    handler, _ = query_pages([[30, 10, 20]], total=3)

    listing = collect(list_apps(transport_for(handler, FakeClock()), country="BR"))[-1]

    assert (listing.kind, listing.key, listing.country) == (Kind.LISTING, "", "BR")
    assert json.loads(listing.body) == {"total_matching_records": 3, "appids": [10, 20, 30]}


def test_a_small_gap_from_the_total_is_accepted() -> None:
    """Apps appear and vanish while a listing runs, so a gap of 0.1% is fine."""
    handler, _ = query_pages([range(999), range(999, 1998)], total=2000)

    found = collect(list_apps(transport_for(handler, FakeClock()), country="BR"))

    assert found[-1].kind is Kind.LISTING


def test_a_gap_over_a_thousandth_raises_after_yielding() -> None:
    """A bigger gap means the paging broke: the listing fails, keeping the answers it gave."""
    handler, _ = query_pages([range(990)], total=1000)
    found: list[Answer] = []

    async def run() -> None:
        async for answer in list_apps(transport_for(handler, FakeClock()), country="BR"):
            found.append(answer)  # noqa: PERF401  # a comprehension loses them when it raises

    with pytest.raises(ListingMismatchError, match="BR") as caught:
        asyncio.run(run())

    assert (caught.value.unique, caught.value.total) == (990, 1000)
    assert len(found) == 990


def items_handler(
    respond: Callable[[list[int]], list[dict[str, object]]],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[Any]]:
    """
    Make a handler answering ``GetItems`` with the items *respond* builds for each batch.

    :param respond: Builds the items for the appids asked.
    :return: The handler and the decoded ``input_json`` of each request.
    """
    asked: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.url.params["input_json"])
        asked.append(body)
        appids = [entry["appid"] for entry in body["ids"]]
        return httpx.Response(200, json={"response": {"store_items": respond(appids)}})

    return handler, asked


def sold(appids: list[int]) -> list[dict[str, object]]:
    """
    Answer every asked app as sold, with its id.

    :param appids: The appids asked.
    :return: One item per appid.
    """
    return [{"id": n, "appid": n, "success": 1} for n in appids]


def test_get_items_asks_batches_of_a_hundred_with_the_full_request() -> None:
    """Full entries are asked 100 at a time, a second apart, with every data flag set."""
    clock = FakeClock()
    handler, asked = items_handler(sold)

    found = collect(get_items(transport_for(handler, clock), range(250, 0, -1), country="BR"))

    assert [len(batch["ids"]) for batch in asked] == [100, 100, 50]
    assert asked[0]["ids"][0] == {"appid": 1}  # ascending
    assert asked[0]["data_request"] == FULL_DATA_REQUEST
    assert asked[0]["context"] == {"language": "english", "country_code": "BR"}
    assert clock.sleeps == pytest.approx([1.0, 1.0])
    assert len(found) == 250
    assert {answer.kind for answer in found} == {Kind.STORE_ITEM}


def test_get_items_keys_by_id_even_when_appid_is_zero() -> None:
    """Delisted apps come back with appid 0, so the key is their id."""
    handler, _ = items_handler(lambda appids: [{"id": n, "appid": 0} for n in appids])

    found = collect(get_items(transport_for(handler, FakeClock()), [12170], country="BR"))

    assert [answer.key for answer in found] == ["12170"]


def test_get_items_yields_items_not_sold_in_the_country() -> None:
    """An app the country doesn't sell (success 15) is still an answer: the sync asks elsewhere."""
    handler, _ = items_handler(lambda appids: [{"id": n, "success": 15} for n in appids])

    found = collect(get_items(transport_for(handler, FakeClock()), [400], country="BR"))

    assert json.loads(found[0].body)["success"] == 15


def test_get_items_retries_an_answer_without_items() -> None:
    """A 200 without store_items is Steam failing a big answer: it is retried."""
    clock = FakeClock()
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(200, json={"response": {}})
        body = json.loads(request.url.params["input_json"])
        return httpx.Response(
            200, json={"response": {"store_items": sold([body["ids"][0]["appid"]])}}
        )

    found = collect(get_items(transport_for(handler, clock), [620], country="BR"))

    assert [answer.key for answer in found] == ["620"]
    assert clock.sleeps == [10.0]


def test_get_items_fails_naming_the_missing_items() -> None:
    """When the items never come, the failure says so."""

    def empty(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {}})

    with pytest.raises(RequestFailedError, match="no store_items"):
        collect(get_items(transport_for(empty, FakeClock()), [620], country="BR"))


def test_get_items_logs_apps_left_out(caplog: pytest.LogCaptureFixture) -> None:
    """An asked app missing from the answer is logged, so a gap never passes unseen."""
    handler, _ = items_handler(lambda appids: sold(appids[:1]))

    collect(get_items(transport_for(handler, FakeClock()), [10, 20, 30], country="BR"))

    assert "left out 2 of 3" in caplog.text


def test_store_categories_are_asked_in_one_language() -> None:
    """Category names come from GetStoreCategories, in the ELanguage asked for."""
    handler, requests = recorder(json={"response": {"categories": []}})

    answer = asyncio.run(store_categories(transport_for(handler, FakeClock()), elanguage=22))

    assert requests[0].url.path == "/IStoreBrowseService/GetStoreCategories/v1/"
    assert dict(requests[0].url.params) == {"elanguage": "22"}
    assert (answer.kind, answer.key, answer.country) == (Kind.STORE_CATEGORIES, "22", "")
    assert json.loads(answer.body) == {"response": {"categories": []}}


def test_tag_list_is_asked_in_one_language() -> None:
    """Tag names come from GetTagList, in the language asked for."""
    handler, requests = recorder(json={"response": {"tags": []}})

    answer = asyncio.run(tag_list(transport_for(handler, FakeClock()), language="brazilian"))

    assert requests[0].url.path == "/IStoreService/GetTagList/v1/"
    assert dict(requests[0].url.params) == {"language": "brazilian"}
    assert (answer.kind, answer.key) == (Kind.TAGS, "brazilian")


def test_a_lookup_without_its_list_is_retried() -> None:
    """A lookup answer missing its list is a failure, like GetItems without items."""
    clock = FakeClock()
    steps = [
        httpx.Response(200, json={"response": {}}),
        httpx.Response(200, json={"response": {"tags": []}}),
    ]

    asyncio.run(tag_list(transport_for(answers(steps), clock)))

    assert clock.sleeps == [10.0]


def test_app_genres_ask_appdetails_for_genres_only() -> None:
    """No endpoint lists genres, so one app's genres are asked from appdetails."""
    handler, requests = recorder(json={"620": {"success": True, "data": {"genres": []}}})

    answer = asyncio.run(app_genres(transport_for(handler, FakeClock()), 620))

    assert requests[0].url.host == "store.steampowered.com"
    assert requests[0].url.path == "/api/appdetails"
    assert dict(requests[0].url.params) == {"appids": "620", "filters": "genres", "l": "english"}
    assert (answer.kind, answer.key, answer.country) == (Kind.APP_GENRES, "620", "")


def test_app_genres_retry_an_answer_that_is_not_json() -> None:
    """The store's error pages are HTML: they are retried, not archived."""
    clock = FakeClock()
    steps = [httpx.Response(200, text="<html>"), httpx.Response(200, json={})]

    asyncio.run(app_genres(transport_for(answers(steps), clock), 620))

    assert clock.sleeps == [10.0]


def test_current_players_are_asked_by_appid() -> None:
    """The player count of one app comes from ISteamUserStats."""
    handler, requests = recorder(json={"response": {"player_count": 5, "result": 1}})

    answer = asyncio.run(current_players(transport_for(handler, FakeClock()), 570))

    assert requests[0].url.path == "/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    assert dict(requests[0].url.params) == {"appid": "570"}
    assert (answer.kind, answer.key) == (Kind.CURRENT_PLAYERS, "570")


def test_a_404_is_an_answer_for_current_players() -> None:
    """A 404 means Steam has no figure for the app: an answer, not a failure."""
    handler, _ = recorder(status=404, json={"response": {"result": 42}})

    answer = asyncio.run(current_players(transport_for(handler, FakeClock()), 12170))

    assert json.loads(answer.body) == {"response": {"result": 42}}
