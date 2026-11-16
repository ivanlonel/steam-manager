"""Tests for the app scores report, compared with the notebook's view."""

from typing import TYPE_CHECKING, Final

from tests.steam_manager.db.reports._parity import mismatches, notebook_view, report_view

if TYPE_CHECKING:
    from pathlib import Path

    from tests.steam_manager.db.reports._parity import Sample

SCORED: Final[Sample] = {
    "review_score": [
        {"review_score": 0, "label": None},
        {"review_score": 5, "label": "Mixed"},
        {"review_score": 9, "label": "Overwhelmingly Positive"},
    ],
    "app": [
        {"appid": 10, "name": "Counter-Strike"},
        {"appid": 30, "name": "Day of Defeat"},
        {"appid": 50, "name": "Opposing Force"},
        {"appid": 400, "name": "Portal"},
        {"appid": 620, "name": "Portal 2"},
    ],
    "app_review_summary": [
        {
            "appid": 10,
            "scope": "filtered",
            "review_count": 50,
            "percent_positive": 80,
            "review_score": 5,
        },
        {
            "appid": 30,
            "scope": "filtered",
            "review_count": 0,
            "percent_positive": 0,
            "review_score": 0,
        },
        {
            "appid": 50,
            "scope": "filtered",
            "review_count": 3,
            "percent_positive": 66,
            "review_score": 0,
        },
        {
            "appid": 400,
            "scope": "filtered",
            "review_count": 150000,
            "percent_positive": 98,
            "review_score": 9,
        },
        {
            "appid": 620,
            "scope": "filtered",
            "review_count": 400000,
            "percent_positive": 98,
            "review_score": 9,
        },
    ],
    "app_review_total": [
        {"appid": 10, "positive": 40, "negative": 10, "counts_exact": 1},
        {"appid": 30, "positive": 0, "negative": 0, "counts_exact": 1},
        {"appid": 50, "positive": 2, "negative": 1, "counts_exact": 1},
        {"appid": 400, "positive": 147000, "negative": 3000, "counts_exact": 0},
        {"appid": 620, "positive": 392000, "negative": 8000, "counts_exact": 1},
    ],
    "app_review_histogram": [
        {
            "appid": 620,
            "rollup_type": "week",
            "start_date": "2011-04-18",
            "end_date": "2026-11-01",
        },
    ],
    "review_history": [
        {
            "appid": 620,
            "is_recent": 0,
            "date": "2026-10-01",
            "recommendations_up": 100,
            "recommendations_down": 5,
        },
        {
            "appid": 620,
            "is_recent": 0,
            "date": "2026-11-01",
            "recommendations_up": 80,
            "recommendations_down": 3,
        },
        {
            "appid": 620,
            "is_recent": 1,
            "date": "2026-11-10",
            "recommendations_up": 10,
            "recommendations_down": 1,
        },
    ],
}
"""Apps with many, few and no reviews, an estimated total, and a review history."""

UNRATED: Final[Sample] = {
    "app": [{"appid": 30, "name": "Day of Defeat"}],
    "app_review_total": [{"appid": 30, "positive": 0, "negative": 0, "counts_exact": 1}],
}
"""A catalog where no app has a review."""


def test_app_scores_has_the_notebooks_columns(tmp_path: Path) -> None:
    """The report keeps the notebook's columns, names and order."""
    ours = report_view(tmp_path, "v_app_scores", {})

    assert ours.columns == notebook_view("v_app_scores", {}).columns


def test_app_scores_matches_the_notebook_on_the_same_rows(tmp_path: Path) -> None:
    """Labels, totals, both averages and the history sums come out as the notebook's."""
    expected = notebook_view("v_app_scores", SCORED).rows

    assert mismatches(expected, report_view(tmp_path, "v_app_scores", SCORED).rows) == []
    assert expected[0]["bayes_avg"] is not None


def test_no_rated_apps_gives_blank_scores(tmp_path: Path) -> None:
    """With no review anywhere, the prior and every score are blank rather than an error."""
    (row,) = report_view(tmp_path, "v_app_scores", UNRATED).rows

    assert (row["avg_rating"], row["bayes_avg"], row["wilson_score"]) == (None, None, None)
