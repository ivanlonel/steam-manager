"""The review tables: Steam's summaries, the exact totals, and the review history."""

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT, STRICT_WITHOUT_ROWID, SteamBase
from steam_manager.db.schema.lookups import ReviewScore


class AppReviewSummary(SteamBase):
    """One of an app's review summaries, as its store page shows it."""

    __tablename__ = "app_review_summary"
    __table_args__ = (
        CheckConstraint("scope IN ('filtered', 'language', 'unfiltered')"),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    scope: Mapped[str] = mapped_column(primary_key=True)
    """``filtered`` (without the reviews Steam filters out), ``language`` or ``unfiltered``."""
    review_count: Mapped[int | None]
    """How many reviews count."""
    percent_positive: Mapped[int | None]
    """The share of positive ones, truncated, not rounded, to a whole percent."""
    review_score: Mapped[int | None] = mapped_column(ForeignKey(ReviewScore.review_score))
    """Steam's score, from 0 to 9."""


class AppReviewTotal(SteamBase):
    """How many positive and negative reviews an app has."""

    __tablename__ = "app_review_total"
    __table_args__ = STRICT

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    positive: Mapped[int]
    """The positive reviews."""
    negative: Mapped[int]
    """The negative reviews."""
    counts_exact: Mapped[bool]
    """Whether the counts are exact, rather than a midpoint estimate from the percentage."""


class AppReviewHistogram(SteamBase):
    """The span of an app's review history, a separate figure from its review count."""

    __tablename__ = "app_review_histogram"
    __table_args__ = STRICT

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    rollup_type: Mapped[str | None]
    """How the history is grouped, such as by week or month."""
    start_date: Mapped[str | None]
    """Its first day."""
    end_date: Mapped[str | None]
    """Its last day."""


class ReviewHistory(SteamBase):
    """The reviews an app received in one period of its history."""

    __tablename__ = "review_history"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(AppReviewHistogram.appid), primary_key=True)
    """The app."""
    is_recent: Mapped[bool] = mapped_column(primary_key=True)
    """Whether it is one of the last few weeks' daily counts, which the rollups include."""
    date: Mapped[str] = mapped_column(primary_key=True)
    """When the period starts."""
    recommendations_up: Mapped[int | None]
    """The positive reviews in it."""
    recommendations_down: Mapped[int | None]
    """The negative reviews in it."""
