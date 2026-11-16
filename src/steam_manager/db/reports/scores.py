"""
The review scores every report shows, and the app scores report.

The Bayes average and the Wilson lower bound come from an app's positive and negative totals,
with the prior taken from every rated app. Each report writes them out on its own totals
instead of joining :func:`app_scores`: joining a view like it makes SQLite scan it once per
row, which the notebooks measured at about 25 ms a row.
"""

from typing import TYPE_CHECKING, Any, Final
lazy from collections.abc import Mapping

from sqlalchemy import Select, and_, case, func, label, select
from sqlalchemy.orm import aliased
lazy from sqlalchemy import SQLColumnExpression

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.lookups import ReviewScore
from steam_manager.db.schema.reviews import AppReviewSummary, AppReviewTotal, ReviewHistory

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

__all__ = [
    "Columns",
    "Report",
    "Z",
    "app_scores",
    "history_total",
    "labelled",
    "score_label",
    "scores",
]

type Columns = Mapping[str, SQLColumnExpression[Any]]
"""A report's columns: each one's name and what it holds."""

type Report = Select[*tuple[Any, ...]]
"""A report's query."""


def labelled(columns: Columns) -> list[ColumnElement[Any]]:
    """
    Name each column of a report.

    :param columns: The columns, in order.
    :return: Each one labelled with its name.
    """
    return [label(name, expression) for name, expression in columns.items()]


Z: Final = 2.5758293035489004
"""The normal quantile for 99% confidence, as steam-games uses for the Wilson bound."""


def scores(totals: type[AppReviewTotal]) -> dict[str, SQLColumnExpression[Any]]:
    """
    Work out an app's scores from its review totals.

    :param totals: The ``app_review_total`` alias the report reads.
    :return: ``total_ratings``, ``avg_rating``, ``bayes_avg`` and ``wilson_score``, in order.
    """
    rated = aliased(AppReviewTotal)
    is_rated = rated.positive + rated.negative > 0
    prior_count = (
        select(func.avg(rated.positive + rated.negative)).where(is_rated).scalar_subquery()
    )
    prior_rating = (
        select(func.avg(100.0 * rated.positive / (rated.positive + rated.negative)))
        .where(is_rated)
        .scalar_subquery()
    )
    total = totals.positive + totals.negative
    share = 1.0 * totals.positive / func.nullif(total, 0)
    z2 = Z * Z
    bayes = (100.0 * totals.positive + prior_count * prior_rating) / (total + prior_count)
    wilson = (
        100
        * (
            share
            + z2 / (2 * total)
            - Z * func.sqrt((share * (1 - share) + z2 / (4.0 * total)) / total)
        )
        / (1 + z2 / total)
    )
    return {
        "total_ratings": total,
        "avg_rating": 100 * share,
        "bayes_avg": case((total > 0, bayes)),
        "wilson_score": wilson,
    }


def score_label(summary: type[AppReviewSummary]) -> ColumnElement[Any]:
    """
    Label a review summary's score as the store does.

    Score 0 has no label of its own: the store shows the count, or that there are none.

    :param summary: The ``app_review_summary`` alias the report reads.
    :return: The label.
    """
    named = (
        select(ReviewScore.label)
        .where(ReviewScore.review_score == summary.review_score)
        .scalar_subquery()
    )
    count = case(
        (summary.review_count > 0, summary.review_count.concat(" user reviews")),
        else_="No user reviews",
    )
    return case((summary.review_score == 0, count), else_=named)


def history_total(
    column: SQLColumnExpression[int | None], appid: SQLColumnExpression[int]
) -> ColumnElement[Any]:
    """
    Add up an app's review history, leaving out the recent days the rollups already count.

    :param column: ``ReviewHistory.recommendations_up`` or ``recommendations_down``.
    :param appid: The app the report is on.
    :return: The sum, blank when the app has no history.
    """
    return (
        select(func.sum(column))
        .where(ReviewHistory.appid == appid, ReviewHistory.is_recent.is_(False))
        .scalar_subquery()
    )


def app_scores() -> Report:
    """
    Build the app scores report: every app's review summary, totals and scores.

    :return: The query behind ``v_app_scores``.
    """
    app = aliased(App, name="n")
    summary = aliased(AppReviewSummary, name="f")
    totals = aliased(AppReviewTotal, name="s")
    columns: Columns = {
        "appid": app.appid,
        "name": app.name,
        "review_count": summary.review_count,
        "percent_positive": summary.percent_positive,
        "review_score": summary.review_score,
        "review_score_label": score_label(summary),
        "positive": totals.positive,
        "negative": totals.negative,
        "counts_exact": totals.counts_exact,
        **scores(totals),
        "hist_positive": history_total(ReviewHistory.recommendations_up, app.appid),
        "hist_negative": history_total(ReviewHistory.recommendations_down, app.appid),
    }
    return (
        select(*labelled(columns))
        .select_from(app)
        .outerjoin(summary, and_(summary.appid == app.appid, summary.scope == "filtered"))
        .outerjoin(totals, totals.appid == app.appid)
    )
