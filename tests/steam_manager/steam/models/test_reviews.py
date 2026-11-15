"""Tests for the review and player-count models, against answers recorded from Steam."""

from pathlib import Path
from typing import Final

from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.reviews import (
    AppReviewsAnswer,
    CurrentPlayersAnswer,
    ReviewHistogramAnswer,
)

FIXTURES: Final = Path(__file__).parents[3] / "fixtures" / "steam"
"""The recorded Steam answers."""


def test_exact_totals_are_fully_declared() -> None:
    """GetAppReviews carries Portal 2's exact totals."""
    path = FIXTURES / "app_reviews-620-0.json"
    answer = AppReviewsAnswer.model_validate_json(path.read_bytes())

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert answer.response.query_summary is not None
    assert (answer.response.query_summary.total_positive or 0) > 100_000


def test_the_recorded_reviews_hold_no_review() -> None:
    """The recorder drops the one review: its author is another account."""
    path = FIXTURES / "app_reviews-620-0.json"
    answer = AppReviewsAnswer.model_validate_json(path.read_bytes())

    assert answer.response is not None
    assert answer.response.reviews == ()


def test_the_histogram_is_fully_declared() -> None:
    """The histogram has its periods."""
    path = FIXTURES / "review_histogram-620.json"
    answer = ReviewHistogramAnswer.model_validate_json(path.read_bytes())

    assert unknown_fields(answer) == []
    assert answer.results is not None
    assert answer.results.rollups


def test_current_players_are_fully_declared() -> None:
    """Dota 2 always has players."""
    path = FIXTURES / "current_players-570.json"
    answer = CurrentPlayersAnswer.model_validate_json(path.read_bytes())

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert (answer.response.player_count or 0) > 0
