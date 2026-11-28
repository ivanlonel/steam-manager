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

ADDED_SINCE_THE_NOTEBOOK: Final = {
    "app_review_histogram": [
        (
            "only declared: app_review_histogram.count_all_reviews #4: INTEGER notnull=0 pk=0"
            " default=None hidden=0"
        ),
    ],
}
"""What Steam sends now that the notebook predates."""


@pytest.mark.parametrize("table", REVIEW_TABLES)
def test_a_review_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, scopes and references, plus what Steam added."""
    assert differences(table) == ADDED_SINCE_THE_NOTEBOOK.get(table, [])
