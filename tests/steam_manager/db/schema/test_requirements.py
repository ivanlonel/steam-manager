"""Tests for the system requirement tables, compared with the notebook's."""

from typing import Final

import pytest

from tests.steam_manager.db.schema._notebook import differences

REQUIREMENT_TABLES: Final = ("app_platform_requirement", "app_system_requirement")
"""The tables of what an app needs to run."""


@pytest.mark.parametrize("table", REQUIREMENT_TABLES)
def test_a_requirement_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, tiers and the link between the two."""
    assert differences(table) == []
