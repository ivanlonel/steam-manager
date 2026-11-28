"""Tests for the loader's progress, kept among the Steam tables."""

from sqlalchemy import inspect

from steam_manager.db.schema.progress import LoadedAnswer, LoadedCountry


def test_a_loaded_answer_is_keyed_as_the_archive_keys_it() -> None:
    """One row per archived answer the tables reflect, keyed by source, kind, key and country."""
    mapper = inspect(LoadedAnswer)

    assert [column.name for column in mapper.primary_key] == ["source", "kind", "key", "country"]
    assert [column.name for column in mapper.columns] == [
        "source",
        "kind",
        "key",
        "country",
        "fetched_at",
    ]


def test_the_countries_loaded_keep_their_order() -> None:
    """The countries the tables reflect, home first, each with its place."""
    mapper = inspect(LoadedCountry)

    assert [column.name for column in mapper.primary_key] == ["position"]
    assert [column.name for column in mapper.columns] == ["position", "country"]
