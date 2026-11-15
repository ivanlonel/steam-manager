"""Tests for raw answers, the records every source hands to the raw archive."""

import dataclasses
from datetime import UTC, datetime

import pytest

from steam_manager.answers import Answer, Kind


def test_kinds_are_the_archive_names() -> None:
    """Each kind is stored under its plain name, so the archive's rows stay readable."""
    assert [kind.value for kind in Kind] == [
        "store_item",
        "store_item_light",
        "listing",
        "store_categories",
        "tags",
        "app_genres",
        "app_reviews",
        "review_histogram",
        "current_players",
        "wishlist",
        "followed_apps",
    ]


def test_an_answer_cannot_change_once_made() -> None:
    """An answer is a record of what a source said, so nothing may rewrite it."""
    answer = Answer("steam", Kind.TAGS, "english", "", "{}", datetime.now(UTC))

    with pytest.raises(dataclasses.FrozenInstanceError):
        # The checkers are right to reject it: the assignment is what the test makes fail.
        answer.body = "[]"  # type: ignore[misc]  # ty: ignore[invalid-assignment]
