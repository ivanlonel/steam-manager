"""Tests for the wishlist report, compared with the notebook's view."""

from typing import TYPE_CHECKING, Final

from tests.steam_manager.db.reports._parity import mismatches, notebook_view, report_view
from tests.steam_manager.db.reports.test_followed import FALLBACK_ONLY, FULL_GAME

if TYPE_CHECKING:
    from pathlib import Path

    from tests.steam_manager.db.reports._parity import Sample

WISHLIST: Final[Sample] = {
    **FULL_GAME,
    "app_review_histogram": [{"appid": 620, "rollup_type": "week"}],
    "review_history": [
        {
            "appid": 620,
            "is_recent": 0,
            "date": "2026-10-01",
            "recommendations_up": 90,
            "recommendations_down": 4,
        },
        {
            "appid": 620,
            "is_recent": 1,
            "date": "2026-11-10",
            "recommendations_up": 9,
            "recommendations_down": 1,
        },
    ],
    "wishlist_item": [
        {"appid": 70, "position": 1, "priority": None, "date_added": "2026-01-02 03:04:05"},
        {"appid": 620, "position": 2, "priority": 1, "date_added": "2025-06-07 08:09:10"},
    ],
}
"""Two Brazilian apps on the wishlist, one ranked and one not, one of them followed."""


def test_wishlist_has_the_notebooks_columns_with_the_owners_changes(tmp_path: Path) -> None:
    """No recommended order, the describing store after visible, store categories as a list."""
    expected = list(notebook_view("v_wishlist", {}).columns)
    expected.remove("recommended_sort_order")
    expected.insert(expected.index("visible") + 1, "store_country")
    expected.insert(expected.index("extra.season_pass.appid") + 1, "store_categories")

    assert report_view(tmp_path, "v_wishlist", {}).columns == expected


def test_wishlist_matches_the_notebook_on_the_same_rows(tmp_path: Path) -> None:
    """Every shared column agrees; the ranked item comes first in the original order."""
    expected = notebook_view("v_wishlist", WISHLIST).rows

    assert mismatches(expected, report_view(tmp_path, "v_wishlist", WISHLIST).rows) == []
    assert [(row["appid"], row["original_sort_order"]) for row in expected] == [(70, 2), (620, 1)]
    assert expected[1]["hist_positive"] == 90


def test_a_fallback_app_shows_its_store_but_no_price(tmp_path: Path) -> None:
    """A wishlisted app only the US store described shows its data, not sold at home, unpriced."""
    sample = {**FALLBACK_ONLY, "wishlist_item": [{"appid": 10, "position": 1}]}

    (row,) = report_view(tmp_path, "v_wishlist", sample).rows

    assert (row["store_country"], row["success"], row["review_count"]) == ("US", 1, 900)
    assert row["unvailable_for_country_restriction"] == 1
    assert (row["final_price_in_cents"], row["formatted_final_price"]) == (None, None)
