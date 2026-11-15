"""Tests for the account's public lists, compared with the notebook's."""

from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import exc, insert

from steam_manager.db.schema.account import WishlistItem
from steam_manager.db.schema.apps import App
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine

ACCOUNT_TABLES: Final = ("wishlist_item", "followed_app")
"""The account's lists that anyone can see on a public profile."""


@pytest.mark.parametrize("table", ACCOUNT_TABLES)
def test_an_account_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys and references."""
    assert differences(table) == []


def test_two_wishlist_items_cannot_share_a_position(steam_tables: Engine) -> None:
    """The position is the wishlist's order, so two items in one place is a loader mistake."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}, {"appid": 400}])
        connection.execute(insert(WishlistItem), [{"appid": 620, "position": 1}])

    with (
        pytest.raises(
            exc.IntegrityError, match=r"UNIQUE constraint failed: wishlist_item\.position"
        ),
        steam_tables.begin() as connection,
    ):
        connection.execute(insert(WishlistItem), [{"appid": 400, "position": 1}])
