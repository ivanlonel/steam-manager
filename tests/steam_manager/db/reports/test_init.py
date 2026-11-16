"""Tests for writing the reports into the database as views."""

from typing import TYPE_CHECKING

from sqlalchemy import inspect

from steam_manager.db.engine import open_database
from steam_manager.db.reports import create_views, reports
from steam_manager.db.schema import SteamBase

if TYPE_CHECKING:
    from pathlib import Path


def test_every_report_becomes_a_view(tmp_path: Path) -> None:
    """Each report is written into the file under its own name."""
    engine = open_database(tmp_path / "steam.sqlite")
    SteamBase.metadata.create_all(engine)

    create_views(engine, home_country="BR")

    with engine.connect() as connection:
        views = set(inspect(connection).get_view_names())
    engine.dispose()
    assert views == set(reports(home_country="BR"))


def test_views_are_replaced_and_others_kept(tmp_path: Path) -> None:
    """An older release's view under a report's name is replaced; the user's own view stays."""
    engine = open_database(tmp_path / "steam.sqlite")
    SteamBase.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE VIEW v_app_scores AS SELECT 1 AS appid")
        connection.exec_driver_sql("CREATE VIEW v_mine AS SELECT appid FROM app")

    create_views(engine, home_country="BR")

    with engine.connect() as connection:
        found = inspect(connection)
        scores = [column["name"] for column in found.get_columns("v_app_scores")]
        views = set(found.get_view_names())
    engine.dispose()
    assert "bayes_avg" in scores
    assert "v_mine" in views
