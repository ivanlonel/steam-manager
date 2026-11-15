"""Ask Steam about an app's reviews: exact totals and the histogram over time."""

import json
from typing import TYPE_CHECKING, Final

from steam_manager.answers import Answer, Kind
from steam_manager.steam.webapi import STORE, call, is_json, response_answer

if TYPE_CHECKING:
    from steam_manager.transport import Transport

REVIEWS_INTERVAL: Final = 0.2
"""Seconds between two ``GetAppReviews`` calls: 30,225 ran this way with no retries."""
HISTOGRAM_INTERVAL: Final = 1.0
"""Seconds between two histograms, as the notebooks paused."""
TOTAL_TOLERANCE: Final = 0.02
"""How far exact totals may miss the store's review count and still be the right type."""


async def app_reviews(transport: Transport, appid: int, *, purchase_type: int) -> Answer:
    """
    Fetch one app's exact review totals, in every language, for one purchase type.

    :param transport: Sends the request.
    :param appid: The app.
    :param purchase_type: 0 for reviews by Steam purchasers, 1 for all reviews.
    :return: The answer, keyed ``<appid>:<purchase_type>``.
    """
    response = await call(
        transport,
        "IUserReviewsService",
        "GetAppReviews",
        interval=REVIEWS_INTERVAL,
        # No languages means English only; a page of 0 means 20, so ask for 1.
        input_json={
            "appid": appid,
            "languages": ["all"],
            "num_per_page": 1,
            "purchase_type": purchase_type,
        },
    )
    return response_answer(Kind.APP_REVIEWS, response, key=f"{appid}:{purchase_type}")


def _total(answer: Answer) -> int:
    """
    Add up the positive and negative totals of a ``GetAppReviews`` answer.

    :param answer: The answer.
    :return: The sum, 0 when the answer has no totals.
    """
    summary = json.loads(answer.body)["response"].get("query_summary", {})
    return int(summary.get("total_positive", 0)) + int(summary.get("total_negative", 0))


async def exact_review_answers(
    transport: Transport, appid: int, *, is_free: bool, review_count: int
) -> list[Answer]:
    """
    Fetch the exact totals that match the store's review count, as the notebooks did.

    Steam purchases match the count of a paid app, all reviews that of a free one. When the
    totals miss *review_count* by more than :data:`TOTAL_TOLERANCE`, the other type is asked
    too, since ``is_free`` is missing on delisted apps. The loader picks the closer one.

    :param transport: Sends the requests.
    :param appid: The app.
    :param is_free: Whether the store says the app is free.
    :param review_count: The store's review count for the app.
    :return: One answer, or two when the first missed.
    """
    first = 1 if is_free else 0
    found = [await app_reviews(transport, appid, purchase_type=first)]
    if abs(_total(found[0]) - review_count) > TOTAL_TOLERANCE * review_count:
        found.append(await app_reviews(transport, appid, purchase_type=1 - first))
    return found


async def review_histogram(
    transport: Transport, appid: int, *, language: str = "english"
) -> Answer:
    """
    Fetch one app's reviews over time, as the store page's chart shows them.

    :param transport: Sends the request.
    :param appid: The app.
    :param language: Steam's name for the language of the answer, such as ``english``.
    :return: The answer, keyed by *appid*. Its totals are a different figure from the store's
        review count.
    """
    response = await transport.get(
        f"{STORE}/appreviewhistogram/{appid}",
        interval=HISTOGRAM_INTERVAL,
        params={"l": language},
        check=is_json,
    )
    return response_answer(Kind.REVIEW_HISTOGRAM, response, key=str(appid))
