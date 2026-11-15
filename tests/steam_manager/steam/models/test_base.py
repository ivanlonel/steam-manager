"""Tests for the payload model base and the report of fields nothing declares."""

from pydantic import Field

from steam_manager.steam.models.base import SteamModel, unknown_fields


class Inner(SteamModel):
    """A nested part of a test payload."""

    price: int | None = None
    """A price in cents, which Steam sends as a string."""


class Outer(SteamModel):
    """A test payload with a list and a mapping of nested parts."""

    name: str | None = None
    """A name."""
    items: tuple[Inner, ...] = ()
    """Nested parts in a list."""
    by_id: dict[str, Inner] = Field(default_factory=dict)
    """Nested parts keyed by an id, as appdetails keys its answer by appid."""


def test_a_declared_payload_has_no_unknown_fields() -> None:
    """Every field of this payload is declared, so nothing is reported."""
    payload = {"name": "x", "items": [{"price": "5"}], "by_id": {"620": {"price": 1}}}

    assert unknown_fields(Outer.model_validate(payload)) == []


def test_an_unknown_field_is_reported_at_its_path() -> None:
    """A field nothing declares is reported once, at its path, with [] for list items."""
    payload = {
        "name": "x",
        "new": 1,
        "items": [{"price": "5", "extra": {"a": 1}}, {"extra": 2}],
        "by_id": {"620": {"odd": True}},
    }

    assert unknown_fields(Outer.model_validate(payload)) == [
        "by_id.*.odd",
        "items[].extra",
        "new",
    ]


def test_an_unknown_field_with_an_empty_value_is_not_reported() -> None:
    """Steam sends empty placeholders; like the notebooks, the report skips them."""
    payload: dict[str, object] = {"name": "x", "a": None, "b": [], "c": {}}

    assert unknown_fields(Outer.model_validate(payload)) == []


def test_an_unknown_false_or_zero_is_reported() -> None:
    """False, 0 and "" carry information, so an undeclared one is reported."""
    payload = {"name": "x", "flag": False, "count": 0, "text": ""}

    assert unknown_fields(Outer.model_validate(payload)) == ["count", "flag", "text"]


def test_int64_strings_become_ints() -> None:
    """Steam sends int64 values such as prices as strings; the models read them as ints."""
    payload = Outer.model_validate({"name": "x", "items": [{"price": "1999"}]})

    assert payload.items[0].price == 1999
