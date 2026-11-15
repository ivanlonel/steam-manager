"""Tests for the account list models, against fixtures written by hand: no account's data."""

from pathlib import Path
from typing import Final

from steam_manager.steam.models.account import FollowedAppsAnswer, WishlistAnswer
from steam_manager.steam.models.base import unknown_fields

FIXTURES: Final = Path(__file__).parents[3] / "fixtures" / "steam"
"""The Steam answers, recorded or written."""


def test_the_wishlist_is_fully_declared() -> None:
    """A wishlist item has its app, rank and date; rank 0 is unranked."""
    answer = WishlistAnswer.model_validate_json((FIXTURES / "wishlist.json").read_bytes())

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert [item.priority for item in answer.response.items] == [1, 2, 0]


def test_the_followed_apps_are_fully_declared() -> None:
    """Followed apps are a list of appids."""
    answer = FollowedAppsAnswer.model_validate_json((FIXTURES / "followed_apps.json").read_bytes())

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert answer.response.appids == (620, 400, 70)
