"""Tests for the app tables, compared with the notebook's."""

from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import exc, insert, select

from steam_manager.db.schema.apps import App
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine


APP_TABLES: Final = ("app", "app_text")
"""The app tables."""

CHANGED_FROM_THE_NOTEBOOK: Final = {
    "app": [
        "only in the notebook: app check (store_country IN ('BR', 'US'))",
        (
            "only declared: app.counts_all_purchases #82: INTEGER notnull=0 pk=0 default=None"
            " hidden=0"
        ),
        (
            "only declared: app.dlc_formatted_total_price #83: TEXT notnull=0 pk=0 default=None"
            " hidden=0"
        ),
    ],
}
"""What the spec changes: a profile can be in any country, and two fields Steam added."""


@pytest.mark.parametrize("table", APP_TABLES)
def test_an_app_table_matches_the_notebook(table: str) -> None:
    """Every column in the notebook's order, its keys, and the references between apps."""
    assert differences(table) == CHANGED_FROM_THE_NOTEBOOK.get(table, [])


def test_any_store_country_is_accepted(steam_tables: Engine) -> None:
    """The notebook allowed only BR and US; a profile can be anywhere."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620, "store_country": "JP"}])

        assert connection.scalar(select(App.store_country)) == "JP"


def test_strict_refuses_a_flag_written_as_text(steam_tables: Engine) -> None:
    """A loose value is an error, not a row that a view later reads wrongly."""
    with (
        pytest.raises(exc.IntegrityError, match="cannot store TEXT value in INTEGER column"),
        steam_tables.begin() as connection,
    ):
        connection.exec_driver_sql("INSERT INTO app (appid, is_free) VALUES (620, 'yes')")


def test_strict_stores_a_number_given_as_a_name_as_text(steam_tables: Engine) -> None:
    """STRICT converts a value it can convert without loss, such as a game named 1234."""
    with steam_tables.begin() as connection:
        connection.exec_driver_sql("INSERT INTO app (appid, name) VALUES (620, 1234)")

        stored = connection.exec_driver_sql("SELECT name, typeof(name) FROM app").one()

    assert tuple(stored) == ("1234", "text")
