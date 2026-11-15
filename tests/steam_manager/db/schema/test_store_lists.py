"""Tests for the store page's other lists, compared with the notebook's."""

from typing import Final

import pytest

from tests.steam_manager.db.schema._notebook import differences

STORE_LIST_TABLES: Final = (
    "app_link",
    "app_eula",
    "app_press_review",
    "app_section",
    "app_sale_page",
    "app_steam_award",
    "app_purchase_note",
    "app_optin_tag",
)
"""The lists on an app's store page that no other table holds."""


@pytest.mark.parametrize("table", STORE_LIST_TABLES)
def test_a_store_list_matches_the_notebook(table: str) -> None:
    """Each keeps the notebook's columns, and Steam's order where the list has one."""
    assert differences(table) == []
