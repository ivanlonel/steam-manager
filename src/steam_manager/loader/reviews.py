"""Work out an app's review totals, and turn its review histogram and player count into rows."""

from typing import TYPE_CHECKING, Final

from steam_manager.db.schema.lookups import ReviewScore
from steam_manager.db.schema.reviews import AppReviewHistogram, AppReviewTotal, ReviewHistory
from steam_manager.loader.rows import iso

if TYPE_CHECKING:
    from collections.abc import Mapping

    from steam_manager.loader.rows import Findings, Rows
    from steam_manager.steam.models.reviews import (
        AppReviewsAnswer,
        CurrentPlayersAnswer,
        QuerySummary,
        ReviewHistogramAnswer,
    )
    from steam_manager.steam.models.store_item import ReviewSummary

EXACT_UP_TO: Final = 100
"""Up to this many reviews, the truncated percentage fits one positive count only."""
TOLERANCE: Final = 0.02
"""How far an exact total of the app's purchase type may be from the store's count."""


def estimate_positive(percent: int, count: int) -> int:
    """
    Work out the positive reviews from Steam's truncated percentage, as steam-games does.

    :param percent: The share of positive reviews, truncated to a whole percent.
    :param count: How many reviews count.
    :return: Up to :data:`EXACT_UP_TO` reviews, the one count the percentage fits; above, the
        middle of the counts it allows.
    """
    if count <= EXACT_UP_TO:
        return -(-percent * count // 100)
    return min(count * (2 * percent + 1) // 200, count)


def exact_totals(answer: AppReviewsAnswer, findings: Findings) -> QuerySummary | None:
    """
    Take the totals from a ``GetAppReviews`` answer, skipping its paging on purpose.

    :param answer: The answer.
    :param findings: Where fields nothing stores are counted.
    :return: The totals, or ``None`` when the answer holds none.
    """
    response = answer.response
    findings.rest(answer, "app_reviews", {"response"})
    # The page's one review names its author and is never stored; the rest is paging.
    findings.rest(
        response,
        "app_reviews.response",
        {"query_summary", "reviews", "cursor", "day_range_used", "total_matching"},
    )
    return response.query_summary if response else None


def _sum(totals: QuerySummary) -> int:
    """
    Add a query's positive and negative counts.

    :param totals: The query's totals.
    :return: Their sum.
    """
    return (totals.total_positive or 0) + (totals.total_negative or 0)


def review_total(
    appid: int,
    summary: ReviewSummary | None,
    exact: Mapping[int, QuerySummary],
    *,
    is_free: bool | None,
    rows: Rows,
    findings: Findings,
) -> None:
    """
    Work out an app's positive and negative totals, exact when Steam's counts are archived.

    :param appid: The app.
    :param summary: Its store review summary without the filtered-out reviews.
    :param exact: The totals of its ``GetAppReviews`` answers, by purchase type: 0 for Steam
        purchases, 1 for all.
    :param is_free: Whether it is free, which makes all purchases its purchase type.
    :param rows: Where the ``app_review_total`` row, and the score labels, go.
    :param findings: Where fields nothing stores and totals that don't add up are counted.
    """
    for totals in exact.values():
        findings.rest(
            totals,
            "app_reviews.response.query_summary",
            {
                "total_positive",
                "total_negative",
                "total_reviews",  # checked
                "review_score",
                "review_score_desc",
                "num_reviews",  # the page's reviews: 1, as asked
            },
        )
        findings.same("app_reviews.total_reviews", totals.total_reviews, _sum(totals))
        if totals.review_score:
            rows.add(ReviewScore, review_score=totals.review_score, label=totals.review_score_desc)
    count = summary.review_count if summary else None
    usable = {kind: totals for kind, totals in exact.items() if _sum(totals)}
    if usable:
        preferred = usable.get(1 if is_free else 0)
        if count is None:
            chosen = preferred or next(iter(usable.values()))
        elif preferred is not None and abs(_sum(preferred) - count) <= TOLERANCE * count:
            chosen = preferred
        else:
            chosen = min(usable.values(), key=lambda totals: abs(_sum(totals) - count))
        positive, negative = chosen.total_positive or 0, chosen.total_negative or 0
        exactly = True
    elif count is not None:
        percent = (summary.percent_positive if summary else None) or 0
        positive = estimate_positive(percent, count)
        negative, exactly = count - positive, count <= EXACT_UP_TO
    else:
        return
    rows.add(
        AppReviewTotal, appid=appid, positive=positive, negative=negative, counts_exact=exactly
    )


def histogram(appid: int, answer: ReviewHistogramAnswer, rows: Rows, findings: Findings) -> None:
    """
    Turn an app's review histogram into its span and its periods.

    :param appid: The app.
    :param answer: The ``appreviewhistogram`` answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    # success is 1 whenever there are results; expand_graph is how the store page draws them.
    findings.rest(
        answer, "review_histogram", {"success", "results", "count_all_reviews", "expand_graph"}
    )
    results = answer.results
    if results is None:
        return
    for is_recent, key in ((False, "rollups"), (True, "recent")):
        for entry in getattr(results, key):
            findings.rest(
                entry,
                f"review_histogram.results.{key}[]",
                {"date", "recommendations_up", "recommendations_down"},
            )
            rows.add(
                ReviewHistory,
                appid=appid,
                is_recent=is_recent,
                date=iso(entry.date),
                recommendations_up=entry.recommendations_up,
                recommendations_down=entry.recommendations_down,
            )
    rows.add(
        AppReviewHistogram,
        appid=appid,
        rollup_type=results.rollup_type,
        start_date=iso(results.start_date),
        end_date=iso(results.end_date),
        count_all_reviews=answer.count_all_reviews,
    )
    # weeks has always been empty; it is reported the day it isn't.
    findings.rest(
        results,
        "review_histogram.results",
        {"start_date", "end_date", "rollup_type", "rollups", "recent"},
    )


def players(answer: CurrentPlayersAnswer, findings: Findings) -> int | None:
    """
    Read how many people play an app now.

    :param answer: The ``GetNumberOfCurrentPlayers`` answer.
    :param findings: Where fields nothing stores are counted.
    :return: The count, or ``None`` when Steam has no figure (its result isn't 1).
    """
    response = answer.response
    findings.rest(answer, "current_players", {"response"})
    findings.rest(response, "current_players.response", {"player_count", "result"})
    return response.player_count if response and response.result == 1 else None
