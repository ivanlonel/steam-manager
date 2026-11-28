"""Tests for the loader's progress, kept among the Steam tables."""

from sqlalchemy import inspect

from steam_manager.db.schema.progress import LoadedAnswer


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
