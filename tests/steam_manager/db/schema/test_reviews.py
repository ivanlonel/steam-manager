"""Tests for the review tables, compared with the notebook's."""

from typing import Final

import pytest

from tests.steam_manager.db.schema._notebook import differences

REVIEW_TABLES: Final = (
    "app_review_summary",
    "app_review_total",
    "app_review_histogram",
    "review_history",
)
"""The tables of what players think of an app."""


@pytest.mark.parametrize("table", REVIEW_TABLES)
def test_a_review_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, scopes and references."""
    assert differences(table) == []
