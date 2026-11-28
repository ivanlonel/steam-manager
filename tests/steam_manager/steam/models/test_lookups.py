"""Tests for the lookup models, against lookups recorded from Steam."""

from pathlib import Path
from typing import Final

from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.lookups import (
    AppDetailsGenresAnswer,
    StoreCategoriesAnswer,
    TagListAnswer,
)

FIXTURES: Final = Path(__file__).parents[3] / "fixtures" / "steam"
"""The recorded Steam answers."""


def test_the_store_categories_are_fully_declared() -> None:
    """Every store category arrives with its id and both of its names."""
    answer = StoreCategoriesAnswer.model_validate_json(
        (FIXTURES / "store_categories.json").read_bytes()
    )

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert any(category.internal_name for category in answer.response.categories)


def test_the_tag_list_is_fully_declared() -> None:
    """Every tag arrives with its id and name."""
    answer = TagListAnswer.model_validate_json((FIXTURES / "tags.json").read_bytes())

    assert unknown_fields(answer) == []
    assert answer.response is not None
    assert len(answer.response.tags) > 100


def test_the_genres_of_an_app_are_fully_declared() -> None:
    """The answer of appdetails is keyed by the appid asked for."""
    answer = AppDetailsGenresAnswer.model_validate_json(
        (FIXTURES / "app_genres-620.json").read_bytes()
    )

    assert unknown_fields(answer) == []
    part = answer.root["620"]
    assert part is not None
    data = part.data
    assert data is not None
    assert data.genres


def test_genres_without_data_validate() -> None:
    """Steam says "no genres" as an empty list, or with no part for the app at all."""
    empty = AppDetailsGenresAnswer.model_validate_json('{"1": {"success": true, "data": []}}')
    missing = AppDetailsGenresAnswer.model_validate_json('{"1": null}')

    part = empty.root["1"]
    assert part is not None
    assert part.data is None
    assert missing.root["1"] is None
