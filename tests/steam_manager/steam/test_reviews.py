"""Tests for the review endpoints: exact totals and the histogram."""

import asyncio
import json
lazy from collections.abc import Callable

import httpx

from steam_manager.answers import Kind
from steam_manager.steam.reviews import app_reviews, exact_review_answers, review_histogram
from tests._fakes import FakeClock, answers, recorder, transport_for


def totals_by_purchase_type(
    totals: dict[int, tuple[int, int]],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[int]]:
    """
    Make a handler answering ``GetAppReviews`` with the totals of the purchase type asked.

    :param totals: The positive and negative totals per purchase type.
    :return: The handler and the purchase types asked, in order.
    """
    asked: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        purchase_type = json.loads(request.url.params["input_json"])["purchase_type"]
        asked.append(purchase_type)
        positive, negative = totals[purchase_type]
        summary = {"total_positive": positive, "total_negative": negative}
        return httpx.Response(200, json={"response": {"query_summary": summary}})

    return handler, asked


def test_app_reviews_ask_every_language_and_one_review() -> None:
    """Only the totals matter: all languages (none means English only), one review per page."""
    handler, requests = recorder(json={"response": {"query_summary": {}}})

    answer = asyncio.run(app_reviews(transport_for(handler, FakeClock()), 620, purchase_type=0))

    assert requests[0].url.path == "/IUserReviewsService/GetAppReviews/v1/"
    assert json.loads(requests[0].url.params["input_json"]) == {
        "appid": 620,
        "languages": ["all"],
        "num_per_page": 1,
        "purchase_type": 0,
    }
    assert (answer.kind, answer.key, answer.country) == (Kind.APP_REVIEWS, "620:0", "")


def test_exact_counts_ask_steam_purchases_for_a_paid_app() -> None:
    """For a paid app, Steam purchases match the store's review count, so one answer will do."""
    handler, asked = totals_by_purchase_type({0: (99, 1)})

    found = asyncio.run(
        exact_review_answers(
            transport_for(handler, FakeClock()), 620, is_free=False, review_count=100
        )
    )

    assert asked == [0]
    assert [answer.key for answer in found] == ["620:0"]


def test_exact_counts_ask_all_reviews_for_a_free_app() -> None:
    """For a free app, all reviews match the store's review count."""
    handler, asked = totals_by_purchase_type({1: (50, 50)})

    asyncio.run(
        exact_review_answers(
            transport_for(handler, FakeClock()), 570, is_free=True, review_count=100
        )
    )

    assert asked == [1]


def test_exact_counts_also_ask_the_other_type_when_three_percent_off() -> None:
    """When the totals miss the review count by more than 2%, the other type is asked too."""
    handler, asked = totals_by_purchase_type({0: (90, 7), 1: (95, 5)})

    found = asyncio.run(
        exact_review_answers(
            transport_for(handler, FakeClock()), 620, is_free=False, review_count=100
        )
    )

    assert asked == [0, 1]
    assert [answer.key for answer in found] == ["620:0", "620:1"]


def test_exact_counts_accept_two_percent_off() -> None:
    """A review can flip between the store's count and this call, so 2% off is a match."""
    handler, asked = totals_by_purchase_type({0: (90, 8)})

    asyncio.run(
        exact_review_answers(
            transport_for(handler, FakeClock()), 620, is_free=False, review_count=100
        )
    )

    assert asked == [0]


def test_exact_counts_ask_the_other_type_when_there_is_no_summary() -> None:
    """An answer without totals counts as zero, which misses any review count."""
    handler, requests = recorder(json={"response": {}})

    found = asyncio.run(
        exact_review_answers(
            transport_for(handler, FakeClock()), 620, is_free=False, review_count=10
        )
    )

    assert len(requests) == 2
    assert len(found) == 2


def test_review_histogram_is_asked_from_the_store() -> None:
    """The histogram comes from the store's page endpoint, in the language asked for."""
    handler, requests = recorder(json={"success": 1, "results": {}})

    answer = asyncio.run(review_histogram(transport_for(handler, FakeClock()), 620))

    assert requests[0].url.host == "store.steampowered.com"
    assert requests[0].url.path == "/appreviewhistogram/620"
    assert dict(requests[0].url.params) == {"l": "english"}
    assert (answer.kind, answer.key, answer.country) == (Kind.REVIEW_HISTOGRAM, "620", "")


def test_a_histogram_that_is_not_json_is_retried() -> None:
    """The store's error pages are HTML: they are retried, not archived."""
    clock = FakeClock()
    steps = [httpx.Response(200, text="<html>"), httpx.Response(200, json={"success": 1})]

    asyncio.run(review_histogram(transport_for(answers(steps), clock), 620))

    assert clock.sleeps == [10.0]
