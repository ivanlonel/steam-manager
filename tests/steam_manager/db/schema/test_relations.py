"""Tests for the tables that link apps, compared with the notebook's."""

from typing import Final

import pytest
from sqlalchemy import inspect

from steam_manager.db.schema.relations import AppDlc
from tests.steam_manager.db.schema._notebook import differences

RELATION_TABLES: Final = (
    "app_related",
    "season_pass_milestone",
    "season_pass_milestone_date",
    "season_pass_milestone_text",
)
"""The tables that link apps."""


ADDED_SINCE_THE_NOTEBOOK: Final = {
    "app_related": [
        (
            "only in the notebook: app_related check (kind IN ('demo', 'standalone_demo',"
            " 'playtest', 'dlc_parent', 'included_app', 'related_f2p', 'season_pass'))"
        ),
        (
            "only declared: app_related check (kind IN ('demo', 'standalone_demo', 'playtest',"
            " 'dlc_parent', 'included_app', 'related_f2p', 'season_pass', 'engine'))"
        ),
    ],
    "season_pass_milestone": [
        (
            "only declared: season_pass_milestone.backfilled_release #7: INTEGER notnull=0 pk=0"
            " default=None hidden=0"
        ),
    ],
}
"""What Steam sends now that the notebook predates: the app giving the engine, and whether a
milestone shipped as a backfilled release."""


@pytest.mark.parametrize("table", RELATION_TABLES)
def test_a_relation_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, references and kinds, plus Steam's new kind."""
    assert differences(table) == ADDED_SINCE_THE_NOTEBOOK.get(table, [])


def test_app_dlc_keys_and_references() -> None:
    """A DLC is listed once per app, and both ends are apps."""
    mapper = inspect(AppDlc)

    assert [column.name for column in mapper.primary_key] == ["appid", "dlc_appid"]
    assert {(key.parent.name, key.target_fullname) for key in mapper.local_table.foreign_keys} == {
        ("appid", "app.appid"),
        ("dlc_appid", "app.appid"),
    }
