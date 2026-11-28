"""Tests for review totals, the review histogram and player counts."""

import json
from collections import Counter
from pathlib import Path
from typing import Final

from steam_manager.loader.reviews import (
    estimate_positive,
    exact_totals,
    histogram,
    players,
    review_total,
)
from steam_manager.loader.rows import Findings, Rows, iso
from steam_manager.steam.models.reviews import (
    AppReviewsAnswer,
    CurrentPlayersAnswer,
    QuerySummary,
    ReviewHistogramAnswer,
)
from steam_manager.steam.models.store_item import ReviewSummary

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam"
"""The recorded Steam answers."""


def total(
    summary: ReviewSummary | None,
    exact: dict[int, QuerySummary] | None = None,
    *,
    is_free: bool = False,
) -> tuple[list[dict[str, object]], Findings]:
    """
    Work out an app's totals.

    :param summary: Its store review summary.
    :param exact: Its exact counts, by purchase type.
    :param is_free: Whether it is free.
    :return: Its ``app_review_total`` rows, and the findings.
    """
    rows, findings = Rows(), Findings()
    review_total(620, summary, exact or {}, is_free=is_free, rows=rows, findings=findings)
    return rows.tables.get("app_review_total", []), findings


def counts(positive: int, negative: int, **fields: object) -> QuerySummary:
    r"""
    Build the totals of a ``GetAppReviews`` query.

    :param positive: The positive reviews.
    :param negative: The negative reviews.
    :param \*\*fields: Its other fields.
    :return: The totals.
    """
    return QuerySummary.model_validate(
        {"total_positive": positive, "total_negative": negative, **fields}
    )


def test_up_to_100_reviews_the_count_is_exact() -> None:
    """Steam truncates the percentage, so up to 100 reviews only one positive count fits it."""
    for count in range(1, 101):
        for positive in range(count + 1):
            assert estimate_positive(100 * positive // count, count) == positive


def test_above_100_the_midpoint_is_estimated() -> None:
    """Above 100 reviews the count is the middle of the counts the percentage allows."""
    assert estimate_positive(50, 1000) == 505
    assert estimate_positive(100, 1000) == 1000

    rows, _ = total(ReviewSummary(review_count=1000, percent_positive=50))

    assert rows == [{"appid": 620, "positive": 505, "negative": 495, "counts_exact": False}]


def test_up_to_100_reviews_the_totals_are_exact() -> None:
    """A small count follows exactly from the percentage, and is flagged so."""
    rows, _ = total(ReviewSummary(review_count=3, percent_positive=66))

    assert rows == [{"appid": 620, "positive": 2, "negative": 1, "counts_exact": True}]


def test_exact_counts_prefer_the_apps_purchase_type_within_2_percent() -> None:
    """A paid app's Steam purchases are its counts when they are within 2% of the store's."""
    summary = ReviewSummary(review_count=1000, percent_positive=50)

    rows, _ = total(summary, {0: counts(600, 415), 1: counts(500, 500)})

    assert rows == [{"appid": 620, "positive": 600, "negative": 415, "counts_exact": True}]


def test_exact_counts_otherwise_take_the_closest_total() -> None:
    """When the app's purchase type is more than 2% off, the closer total is the one."""
    summary = ReviewSummary(review_count=1000, percent_positive=50)

    rows, _ = total(summary, {0: counts(600, 500), 1: counts(480, 510)})

    assert rows == [{"appid": 620, "positive": 480, "negative": 510, "counts_exact": True}]


def test_a_query_without_totals_is_ignored() -> None:
    """Totals of 0 mean the query found nothing; the estimate stands."""
    rows, _ = total(ReviewSummary(review_count=1000, percent_positive=50), {0: counts(0, 0)})

    assert rows == [{"appid": 620, "positive": 505, "negative": 495, "counts_exact": False}]


def test_exact_counts_without_a_summary_take_the_apps_purchase_type() -> None:
    """Without a store count to compare with, a free app's exact counts are all purchases."""
    rows, _ = total(None, {0: counts(10, 2), 1: counts(12, 3)}, is_free=True)

    assert rows == [{"appid": 620, "positive": 12, "negative": 3, "counts_exact": True}]


def test_no_summary_and_no_counts_give_no_row() -> None:
    """An app without reviews of any kind has no totals."""
    rows, _ = total(None)

    assert rows == []


def test_total_reviews_is_checked() -> None:
    """The query's total follows from its two counts."""
    _, agrees = total(None, {0: counts(600, 400, total_reviews=1000)})
    _, differs = total(None, {0: counts(600, 400, total_reviews=1001)})

    assert agrees.mismatches["app_reviews.total_reviews"] == 0
    assert differs.mismatches["app_reviews.total_reviews"] == 1


def test_a_query_names_its_score() -> None:
    """The query's score label is the label of that score, like the store's."""
    rows, findings = Rows(), Findings()
    exact = {0: counts(1, 0, review_score=9, review_score_desc="Overwhelmingly Positive")}

    review_total(620, None, exact, is_free=False, rows=rows, findings=findings)

    assert rows.tables["review_score"] == [{"review_score": 9, "label": "Overwhelmingly Positive"}]


def test_a_recorded_query_gives_its_totals() -> None:
    """Portal 2's recorded query leaves nothing out: its paging is skipped on purpose."""
    answer = AppReviewsAnswer.model_validate_json(
        (FIXTURES / "app_reviews-620-0.json").read_bytes()
    )
    findings = Findings()

    summary = exact_totals(answer, findings)

    assert summary is not None
    assert (summary.total_positive, summary.total_negative) == (387851, 5009)
    assert findings.unknown == Counter()


def test_a_query_without_a_response_has_no_totals() -> None:
    """An answer without its response object holds no counts."""
    assert exact_totals(AppReviewsAnswer(), Findings()) is None


def test_a_histogram_gives_periods_and_recent_days() -> None:
    """The whole history goes in periods, the last weeks in days, and the span beside them."""
    answer = ReviewHistogramAnswer.model_validate_json(
        (FIXTURES / "review_histogram-620.json").read_bytes()
    )
    assert answer.results is not None
    rows, findings = Rows(), Findings()

    histogram(620, answer, rows, findings)

    assert rows.tables["app_review_histogram"] == [
        {
            "appid": 620,
            "rollup_type": "month",
            "start_date": iso(answer.results.start_date),
            "end_date": iso(answer.results.end_date),
            "count_all_reviews": False,
        }
    ]
    history = rows.tables["review_history"]
    assert [row["is_recent"] for row in history].count(False) == len(answer.results.rollups)
    assert [row["is_recent"] for row in history].count(True) == len(answer.results.recent)
    first = answer.results.rollups[0]
    assert history[0] == {
        "appid": 620,
        "is_recent": False,
        "date": iso(first.date),
        "recommendations_up": first.recommendations_up,
        "recommendations_down": first.recommendations_down,
    }
    assert findings.unknown == Counter()


def test_a_histograms_events_are_stored() -> None:
    """The periods a histogram marks keep their order, with dates as the history's."""
    answer = json.loads((FIXTURES / "review_histogram-620.json").read_bytes())
    answer["past_events"] = [
        {"type": 0, "start_date": 1739491200, "end_date": 1743379200},
        {"type": 0, "start_date": 1790121600, "end_date": 1790726400},
    ]
    rows, findings = Rows(), Findings()

    histogram(620, ReviewHistogramAnswer.model_validate(answer), rows, findings)

    assert rows.tables["review_event"] == [
        {
            "appid": 620,
            "position": position,
            "type": 0,
            "start_date": iso(event["start_date"]),
            "end_date": iso(event["end_date"]),
        }
        for position, event in enumerate(answer["past_events"])
    ]
    assert findings.unknown == Counter()


def test_a_histogram_without_results_gives_no_rows() -> None:
    """The store answers an app it doesn't know without a histogram."""
    rows = Rows()

    histogram(620, ReviewHistogramAnswer(success=2), rows, Findings())

    assert not rows.tables


def test_events_without_results_are_reported() -> None:
    """Events need the histogram they mark: without one they are reported, not dropped."""
    answer = ReviewHistogramAnswer.model_validate({"success": 2, "past_events": [{"type": 0}]})
    rows, findings = Rows(), Findings()

    histogram(620, answer, rows, findings)

    assert not rows.tables
    assert findings.unknown == Counter({"review_histogram.past_events": 1})


def test_players_are_counted() -> None:
    """Dota 2's recorded figure is its player count."""
    answer = CurrentPlayersAnswer.model_validate_json(
        (FIXTURES / "current_players-570.json").read_bytes()
    )
    findings = Findings()

    assert players(answer, findings) == 820992
    assert findings.unknown == Counter()


def test_no_figure_gives_no_player_count() -> None:
    """Steam's result 42 means it has no figure for the app."""
    answer = CurrentPlayersAnswer.model_validate({"response": {"result": 42}})

    assert players(answer, Findings()) is None
