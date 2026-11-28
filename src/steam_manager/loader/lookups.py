"""Turn the lookups, the names of store categories, tags, genres and languages, into rows."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from steam_manager.db.schema.lookups import Genre, Language, StoreCategory, Tag
from steam_manager.loader.rows import read_columns

if TYPE_CHECKING:
    from collections.abc import Mapping

    from steam_manager.loader.rows import Findings, Rows
    from steam_manager.steam.models.lookups import (
        AppDetailsGenresAnswer,
        StoreCategoriesAnswer,
        TagListAnswer,
    )

LANGUAGES: Final[Mapping[int, str]] = MappingProxyType(
    dict(
        enumerate(
            (
                "English",
                "German",
                "French",
                "Italian",
                "Korean",
                "Spanish - Spain",
                "Simplified Chinese",
                "Traditional Chinese",
                "Russian",
                "Thai",
                "Japanese",
                "Portuguese - Portugal",
                "Polish",
                "Danish",
                "Dutch",
                "Finnish",
                "Norwegian",
                "Swedish",
                "Hungarian",
                "Czech",
                "Romanian",
                "Turkish",
                "Portuguese - Brazil",
                "Bulgarian",
                "Greek",
                "Arabic",
                "Ukrainian",
                "Spanish - Latin America",
                "Vietnamese",
            )
        )
    )
    | {30: "Indonesian"}
)
"""
Steam's ELanguage numbers and their names, as steam-games checked them against the store's
language lists. No endpoint lists them; 29 and 31 have no reliable name yet.
"""


def languages(rows: Rows) -> None:
    """
    Name Steam's language numbers.

    :param rows: Where the rows go.
    """
    for elanguage, name in LANGUAGES.items():
        rows.add(Language, elanguage=elanguage, name=name)


def store_categories(answer: StoreCategoriesAnswer, rows: Rows, findings: Findings) -> None:
    """
    Turn the ``GetStoreCategories`` answer into a row per store category.

    :param answer: The answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    response = answer.response
    findings.rest(answer, "store_categories", {"response"})
    findings.rest(response, "store_categories.response", {"categories"})
    names = (
        "categoryid",
        "type",
        "internal_name",
        "display_name",
        "image_url",
        "computed",
        "edit_url",
        "edit_sort_order",
        "show_in_search",
    )
    for category in response.categories if response else ():
        where = "store_categories.response.categories[]"
        rows.add(StoreCategory, **read_columns(category, where, names, findings))


def tags(answer: TagListAnswer, rows: Rows, findings: Findings) -> None:
    """
    Turn the ``GetTagList`` answer into a row per tag.

    :param answer: The answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    response = answer.response
    findings.rest(answer, "tags", {"response"})
    # version_hash identifies this version of the list, not anything about a tag.
    findings.rest(response, "tags.response", {"version_hash", "tags"})
    for tag in response.tags if response else ():
        rows.add(Tag, **read_columns(tag, "tags.response.tags[]", ("tagid", "name"), findings))


def genres(answer: AppDetailsGenresAnswer, rows: Rows, findings: Findings) -> None:
    """
    Name the genres of an ``appdetails`` answer: no endpoint lists genres by id.

    :param answer: The answer, a part per appid asked.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    :raise ValueError: When a genre has no id.
    """
    for part in answer.root.values():
        findings.rest(part, "app_genres.*", {"success", "data"})
        data = part.data if part else None
        findings.rest(data, "app_genres.*.data", {"genres"})
        for genre in data.genres if data else ():
            findings.rest(genre, "app_genres.*.data.genres[]", {"id", "description"})
            if genre.id is None:
                message = "app_genres.*.data.genres[] has no id"
                raise ValueError(message)
            rows.add(Genre, genreid=int(genre.id), name=genre.description)
