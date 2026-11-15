"""Tests for the store item model, against store items recorded from Steam."""

import json
from operator import attrgetter
from pathlib import Path
from typing import Final

import pytest

from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.store_item import StoreItem

FIXTURES: Final = Path(__file__).parents[3] / "fixtures" / "steam"
"""The recorded Steam answers."""
PORTAL_2_BR: Final = FIXTURES / "store_item" / "620-BR.json"
"""Portal 2's full entry from the Brazilian store."""
RECORDED: Final = sorted(
    [*FIXTURES.glob("store_item/*.json"), *FIXTURES.glob("store_item_light/*.json")]
)
"""Every recorded store item, full and light."""


@pytest.mark.parametrize("path", RECORDED, ids=attrgetter("stem"))
def test_a_recorded_store_item_has_no_unknown_fields(path: Path) -> None:
    """Every field Steam sends is declared; a new one would show up here first."""
    item = StoreItem.model_validate_json(path.read_bytes())

    assert unknown_fields(item) == []


def test_every_case_is_recorded() -> None:
    """The fixtures keep covering a free game, a DLC, Early Access and a delisted app."""
    items = [StoreItem.model_validate_json(path.read_bytes()) for path in RECORDED]

    assert any(item.is_free for item in items)
    assert any(item.type == 4 for item in items)  # DLC
    assert any(item.is_early_access for item in items)
    assert any(item.success == 15 for item in items)  # not sold in the country


def test_a_new_field_deep_down_is_reported() -> None:
    """A field Steam adds inside a list inside a list is reported at its full path."""
    payload = json.loads(PORTAL_2_BR.read_bytes())
    payload["purchase_options"][0]["active_discounts"] = [{"new_field": 1}]

    found = unknown_fields(StoreItem.model_validate(payload))

    assert found == ["purchase_options[].active_discounts[].new_field"]


def test_portal_2_carries_the_values_the_loader_needs() -> None:
    """Portal 2's entry reads back with its id, reviews and an int price."""
    item = StoreItem.model_validate_json(PORTAL_2_BR.read_bytes())

    assert item.id == 620
    assert item.name == "Portal 2"
    assert item.reviews is not None
    assert item.reviews.summary_filtered is not None
    assert (item.reviews.summary_filtered.review_count or 0) > 100_000
    assert item.best_purchase_option is not None
    assert isinstance(item.best_purchase_option.final_price_in_cents, int)


def test_included_apps_are_store_items_too() -> None:
    """A short record inside an entry is read with the same model, recursively."""
    payload = json.loads(PORTAL_2_BR.read_bytes())
    payload["included_items"] = {"included_apps": [{"id": 323180, "name": "A DLC", "odd": 1}]}

    item = StoreItem.model_validate(payload)

    assert item.included_items is not None
    assert item.included_items.included_apps[0].id == 323180
    assert unknown_fields(item) == ["included_items.included_apps[].odd"]
