"""Tests for the lookup tables, compared with the notebook's."""

from typing import Final

import pytest

from tests.steam_manager.db.schema._notebook import differences

ADDED_SINCE_THE_NOTEBOOK: dict[str, list[str]] = {
    "store_category": [
        "only declared: store_category.show_in_search #8: INTEGER notnull=0 pk=0",
    ],
}
"""The columns Steam sends now that the notebook predates."""

LOOKUPS: Final = (
    "store_category",
    "tag",
    "genre",
    "language",
    "review_score",
    "rating_agency",
    "age_rating",
    "anticheat",
)
"""The lookup tables."""


@pytest.mark.parametrize("table", LOOKUPS)
def test_a_lookup_matches_the_notebook(table: str) -> None:
    """Each lookup has the notebook's columns, keys and STRICT options, plus what Steam added."""
    assert differences(table) == ADDED_SINCE_THE_NOTEBOOK.get(table, [])
