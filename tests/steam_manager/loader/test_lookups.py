"""Tests for turning the lookups into rows, against lookups recorded from Steam."""

from collections import Counter
from pathlib import Path
from typing import Final

import pytest

from steam_manager.loader.lookups import LANGUAGES, genres, languages, store_categories, tags
from steam_manager.loader.rows import Findings, MalformedAnswerError, Rows
from steam_manager.steam.models.lookups import (
    AppDetailsGenresAnswer,
    StoreCategoriesAnswer,
    TagListAnswer,
)

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam"
"""The recorded Steam answers."""


def test_store_categories_keep_show_in_search() -> None:
    """Every store category is a row, with the flag Steam added since the notebooks."""
    answer = StoreCategoriesAnswer.model_validate_json(
        (FIXTURES / "store_categories.json").read_bytes()
    )
    assert answer.response is not None
    rows, findings = Rows(), Findings()

    store_categories(answer, rows, findings)

    stored = rows.tables["store_category"]
    assert len(stored) == len(answer.response.categories)
    assert {"categoryid", "internal_name", "show_in_search"} <= stored[0].keys()
    assert any(row["show_in_search"] is not None for row in stored)
    assert findings.unknown == Counter()


def test_the_tag_list_stores_names_and_skips_its_version() -> None:
    """Every tag is a row; the list's version is neither stored nor reported."""
    answer = TagListAnswer.model_validate_json((FIXTURES / "tags.json").read_bytes())
    assert answer.response is not None
    rows, findings = Rows(), Findings()

    tags(answer, rows, findings)

    assert rows.tables["tag"][0] == {"tagid": 9, "name": "Strategy"}
    assert len(rows.tables["tag"]) == len(answer.response.tags)
    assert findings.unknown == Counter()


def test_genre_ids_become_numbers() -> None:
    """Appdetails sends genre ids as text; the table keys them by number."""
    answer = AppDetailsGenresAnswer.model_validate_json(
        (FIXTURES / "app_genres-620.json").read_bytes()
    )
    rows, findings = Rows(), Findings()

    genres(answer, rows, findings)

    assert rows.tables["genre"] == [
        {"genreid": 1, "name": "Action"},
        {"genreid": 25, "name": "Adventure"},
    ]
    assert findings.unknown == Counter()


def test_an_app_without_genres_gives_none() -> None:
    """Steam's shapes for "no genres" add no rows."""
    answer = AppDetailsGenresAnswer.model_validate(
        {"1": None, "2": {"success": True, "data": []}, "3": {"success": False}}
    )
    rows = Rows()

    genres(answer, rows, Findings())

    assert not rows.tables


def test_a_genre_without_an_id_is_malformed() -> None:
    """A genre is known by its id; without one it can't be stored."""
    answer = AppDetailsGenresAnswer.model_validate(
        {"1": {"success": True, "data": {"genres": [{"description": "Action"}]}}}
    )

    with pytest.raises(MalformedAnswerError, match="has no id"):
        genres(answer, Rows(), Findings())


def test_languages_name_steams_numbers() -> None:
    """No endpoint lists languages, so Steam's fixed numbers are named here."""
    rows = Rows()

    languages(rows)

    named = {row["elanguage"]: row["name"] for row in rows.tables["language"]}
    assert named[0] == "English"
    assert named[22] == "Portuguese - Brazil"
    assert named[30] == "Indonesian"
    assert named == dict(LANGUAGES)
