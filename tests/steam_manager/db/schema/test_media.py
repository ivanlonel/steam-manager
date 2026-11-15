"""Tests for the media tables, compared with the notebook's."""

from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import exc, insert

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.media import AppAsset
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine

MEDIA_TABLES: Final = ("app_asset", "app_screenshot", "trailer", "app_trailer", "trailer_file")
"""The tables of an app's images and videos."""


@pytest.mark.parametrize("table", MEDIA_TABLES)
def test_a_media_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, references and checks."""
    assert differences(table) == []


def test_a_base_filename_needs_an_override(steam_tables: Engine) -> None:
    """Only a file Steam shows instead of another names the one it replaces."""
    assets = [
        {
            "kind": "header",
            "filename": "header.jpg",
            "is_override": True,
            "base_filename": "h.jpg",
        },
        {"kind": "capsule", "filename": "capsule.jpg", "is_override": True, "base_filename": None},
        {"kind": "hero", "filename": "hero.jpg", "is_override": False, "base_filename": None},
    ]
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        connection.execute(insert(AppAsset), [{"appid": 620, **asset} for asset in assets])

    with (
        pytest.raises(exc.IntegrityError, match="CHECK constraint failed"),
        steam_tables.begin() as connection,
    ):
        connection.execute(
            insert(AppAsset),
            [
                {
                    "appid": 620,
                    "kind": "logo",
                    "filename": "logo.png",
                    "is_override": False,
                    "base_filename": "base.png",
                }
            ],
        )
