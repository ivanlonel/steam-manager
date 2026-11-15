"""Tests for the credit tables, compared with the notebook's."""

from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import exc, insert

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.creators import AppCredit, Creator, Credit
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine


CREDIT_TABLES: Final = ("creator", "credit", "app_credit")
"""The tables that say who made an app."""


@pytest.mark.parametrize("table", CREDIT_TABLES)
def test_a_credit_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys and unique indexes, the partial one included."""
    assert differences(table) == []


def test_a_credit_name_may_repeat_only_with_a_creator(steam_tables: Engine) -> None:
    """Valve with its creator page and Valve without one are two credits; two without are one."""
    with steam_tables.begin() as connection:
        connection.execute(insert(Creator), [{"creator_id": 1, "name": "Valve"}])
        connection.execute(
            insert(Credit),
            [{"name": "Valve", "creator_id": 1}, {"name": "Valve", "creator_id": None}],
        )

    with (
        pytest.raises(exc.IntegrityError, match=r"UNIQUE constraint failed: credit\.name"),
        steam_tables.begin() as connection,
    ):
        connection.execute(insert(Credit), [{"name": "Valve"}])


def test_an_unknown_role_is_refused(steam_tables: Engine) -> None:
    """A credit is a developer, a publisher or a franchise, as the notebook's views expect."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        connection.execute(insert(Credit), [{"credit_id": 1, "name": "Valve"}])

    with (
        pytest.raises(exc.IntegrityError, match="CHECK constraint failed"),
        steam_tables.begin() as connection,
    ):
        connection.execute(
            insert(AppCredit),
            [{"appid": 620, "role": "composer", "position": 0, "credit_id": 1}],
        )
