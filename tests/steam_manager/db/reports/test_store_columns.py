"""Tests for the store columns the wishlist and followed reports share."""

from typing import TYPE_CHECKING, Final

import pytest

from tests.steam_manager.db.reports._parity import report_view
from tests.steam_manager.db.reports._samples import FALLBACK_WITH_HOME_PRICE, FULL_GAME

if TYPE_CHECKING:
    from pathlib import Path

STORE_REPORTS: Final = ("v_wishlist", "v_followed")
"""The reports that show the store columns."""

PRICE_COLUMNS: Final = (
    "final_price_in_cents",
    "formatted_final_price",
    "original_price_in_cents",
    "formatted_original_price",
    "discount_pct",
)
"""Columns that hold a price or come from one."""


def test_store_categories_lists_internal_names(tmp_path: Path) -> None:
    """An app's store categories are one JSON list of their internal names, in id order."""
    rows = report_view(tmp_path, "v_followed", FULL_GAME).rows

    assert [row["store_categories"] for row in rows] == [
        None,
        '["SinglePlayer","FullControllerSupport"]',
    ]


@pytest.mark.parametrize("view", STORE_REPORTS)
def test_a_home_price_never_shows_on_an_app_another_store_described(
    tmp_path: Path, view: str
) -> None:
    """An app the US store described shows no price, even one its offer has at home."""
    (row,) = report_view(tmp_path, view, FALLBACK_WITH_HOME_PRICE).rows

    assert row["unvailable_for_country_restriction"] == 1
    assert [row[column] for column in PRICE_COLUMNS] == [None] * len(PRICE_COLUMNS)
