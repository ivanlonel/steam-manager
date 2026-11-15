"""Tests for the tables that classify apps, compared with the notebook's."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc, insert, select

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppCompatibilityTest
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine

DEVICES = ("steam_deck", "steam_os", "steam_machine", "steam_frame")
"""The devices Steam reports compatibility results for."""


@pytest.mark.parametrize(
    "table",
    [
        "app_category",
        "app_tag",
        "app_genre",
        "app_language",
        "app_content_descriptor",
        "app_interactive_element",
        "app_rating_descriptor",
        "app_document",
        "app_manufacturer",
    ],
)
def test_a_classification_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, its composite key and its references."""
    assert differences(table) == []


def test_compatibility_results_keep_their_device_and_order(steam_tables: Engine) -> None:
    """Each device's results are stored apart, in the order Steam lists them."""
    results = [
        {"appid": 620, "device": device, "position": position, "display_type": 4 - position}
        for device in DEVICES
        for position in (0, 1)
    ]
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        connection.execute(insert(AppCompatibilityTest), results)

        stored = connection.execute(
            select(
                AppCompatibilityTest.device,
                AppCompatibilityTest.position,
                AppCompatibilityTest.display_type,
            ).order_by(AppCompatibilityTest.device, AppCompatibilityTest.position)
        ).all()

    assert [tuple(row) for row in stored] == sorted(
        (result["device"], result["position"], result["display_type"]) for result in results
    )


def test_an_unknown_device_is_refused(steam_tables: Engine) -> None:
    """A device Steam adds later fails loudly, not stored under a name no view reads."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])

    with (
        pytest.raises(exc.IntegrityError, match="CHECK constraint failed"),
        steam_tables.begin() as connection,
    ):
        connection.execute(
            insert(AppCompatibilityTest), [{"appid": 620, "device": "steam_phone", "position": 0}]
        )
