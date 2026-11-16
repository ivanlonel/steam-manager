"""Tests for the followed apps report, compared with the notebook's view."""

from typing import TYPE_CHECKING

from tests.steam_manager.db.reports._parity import mismatches, notebook_view, report_view
from tests.steam_manager.db.reports._samples import FALLBACK_ONLY, FULL_GAME

if TYPE_CHECKING:
    from pathlib import Path


def test_followed_has_the_notebooks_columns_plus_store_categories(tmp_path: Path) -> None:
    """The notebook's columns in order, with the store categories as one list at the end."""
    notebooks = notebook_view("v_followed", {}).columns

    assert report_view(tmp_path, "v_followed", {}).columns == [*notebooks, "store_categories"]


def test_followed_matches_the_notebook_on_the_same_rows(tmp_path: Path) -> None:
    """Every store column agrees, and the sample leaves almost none of them blank."""
    expected = notebook_view("v_followed", FULL_GAME).rows

    assert mismatches(expected, report_view(tmp_path, "v_followed", FULL_GAME).rows) == []
    half_life, portal_2 = expected
    assert [column for column, value in portal_2.items() if value is None] == ["bundleid"]
    assert half_life["bundleid"] == 9


def test_a_fallback_app_shows_its_store_but_no_price(tmp_path: Path) -> None:
    """The US store's reviews and description show; its dollar prices never do."""
    (row,) = report_view(tmp_path, "v_followed", FALLBACK_ONLY).rows

    assert (row["store_country"], row["review_count"], row["short_description"]) == (
        "US",
        900,
        "The original.",
    )
    assert row["genres"] == "Action"
    prices = (
        "final_price_in_cents",
        "formatted_final_price",
        "original_price_in_cents",
        "discount_pct",
        "active_discounts",
    )
    assert [row[column] for column in prices] == [None] * len(prices)
    assert row["unvailable_for_country_restriction"] == 1
