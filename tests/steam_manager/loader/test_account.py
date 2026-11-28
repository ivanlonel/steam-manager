"""Tests for turning an account's public lists into rows, against recorded lists."""

from collections import Counter
from pathlib import Path
from typing import Final

from steam_manager.loader.account import followed, wishlist
from steam_manager.loader.rows import Findings, Rows
from steam_manager.steam.models.account import FollowedAppsAnswer, WishlistAnswer

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam"
"""The recorded Steam answers."""


def test_the_wishlist_keeps_steams_order() -> None:
    """Positions count from 1 in Steam's order, and an unranked app has no priority."""
    answer = WishlistAnswer.model_validate_json((FIXTURES / "wishlist.json").read_bytes())
    rows, findings = Rows(), Findings()

    wishlist(answer, rows, findings)

    assert rows.tables["wishlist_item"] == [
        {"appid": 620, "position": 1, "priority": 1, "date_added": "2023-11-14 22:13:20"},
        {"appid": 400, "position": 2, "priority": 2, "date_added": "2023-11-15 22:13:20"},
        {"appid": 70, "position": 3, "priority": None, "date_added": "2023-11-16 22:13:20"},
    ]
    assert findings.unknown == Counter()


def test_followed_apps() -> None:
    """Each followed app is a row."""
    answer = FollowedAppsAnswer.model_validate_json((FIXTURES / "followed_apps.json").read_bytes())
    rows, findings = Rows(), Findings()

    followed(answer, rows, findings)

    assert rows.tables["followed_app"] == [{"appid": 620}, {"appid": 400}, {"appid": 70}]
    assert findings.unknown == Counter()


def test_an_empty_answer_gives_no_rows() -> None:
    """An answer without its response object lists nothing."""
    rows = Rows()

    wishlist(WishlistAnswer(), rows, Findings())
    followed(FollowedAppsAnswer(), rows, Findings())

    assert not rows.tables
