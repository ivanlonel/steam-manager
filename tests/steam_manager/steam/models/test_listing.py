"""Tests for the listing model: the appids a store lists, as list_apps archives them."""

from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.listing import ListingAnswer


def test_a_listing_holds_its_appids_and_total() -> None:
    """A listing answer, as list_apps builds it, is fully declared."""
    answer = ListingAnswer.model_validate({"total_matching_records": 3, "appids": [10, 20, 30]})

    assert answer.appids == (10, 20, 30)
    assert answer.total_matching_records == 3
    assert unknown_fields(answer) == []
