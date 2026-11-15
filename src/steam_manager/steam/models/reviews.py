"""Payload models of review totals, the review histogram and current players."""

from pydantic import JsonValue

from steam_manager.steam.models.base import SteamModel


class QuerySummary(SteamModel):
    """The totals of a ``GetAppReviews`` query."""

    num_reviews: int | None = None
    """How many reviews this page holds."""
    review_score: int | None = None
    """Steam's score, from 0 to 9."""
    review_score_desc: str | None = None
    """The score's label."""
    total_positive: int | None = None
    """Positive reviews: the exact count."""
    total_negative: int | None = None
    """Negative reviews: the exact count."""
    total_reviews: int | None = None
    """All reviews counted."""


class AppReviewsResponse(SteamModel):
    """The ``response`` of ``GetAppReviews``."""

    query_summary: QuerySummary | None = None
    """The totals: the part that matters."""
    reviews: tuple[dict[str, JsonValue], ...] = ()
    """The reviews on this page, with their authors; never read, and kept out of fixtures."""
    cursor: str | None = None
    """Where the next page starts."""
    day_range_used: int | None = None
    """How many days back the query looked."""
    total_matching: int | None = None
    """How many reviews matched."""


class AppReviewsAnswer(SteamModel):
    """The answer of ``GetAppReviews``."""

    response: AppReviewsResponse | None = None
    """The totals and one review."""


class Rollup(SteamModel):
    """The reviews of one period of the histogram."""

    date: int | None = None
    """When the period starts, in epoch seconds."""
    recommendations_up: int | None = None
    """Positive reviews in it."""
    recommendations_down: int | None = None
    """Negative reviews in it."""


class HistogramResults(SteamModel):
    """The histogram itself."""

    start_date: int | None = None
    """Its first date, in epoch seconds."""
    end_date: int | None = None
    """Its last date, in epoch seconds."""
    rollup_type: str | None = None
    """The length of its periods, such as ``month``."""
    rollups: tuple[Rollup, ...] = ()
    """The whole history, period by period."""
    recent: tuple[Rollup, ...] = ()
    """The last weeks, day by day."""
    weeks: tuple[Rollup, ...] = ()
    """Always empty so far."""


class ReviewHistogramAnswer(SteamModel):
    """The answer of ``appreviewhistogram``. Its totals differ from the store's review count."""

    success: int | None = None
    """1 when the store knows the app."""
    results: HistogramResults | None = None
    """The histogram."""
    count_all_reviews: bool | None = None
    """Whether it counts reviews by people who didn't buy the app on Steam."""
    expand_graph: bool | None = None
    """Whether the store page shows it expanded."""


class CurrentPlayersResponse(SteamModel):
    """The ``response`` of ``GetNumberOfCurrentPlayers``."""

    player_count: int | None = None
    """How many people play the app now."""
    result: int | None = None
    """Steam's result code: 1 with a figure, 42 without one."""


class CurrentPlayersAnswer(SteamModel):
    """The answer of ``GetNumberOfCurrentPlayers``."""

    response: CurrentPlayersResponse | None = None
    """The count."""
