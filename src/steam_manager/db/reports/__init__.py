"""
The reports: named tables of results the application computes over the database.

Each is a query the application runs with the profile's home country. :func:`create_views`
also writes every report into the database as a view of the same name, so that other SQLite
tools see them.
"""

from typing import TYPE_CHECKING

from sqlalchemy.schema import CreateView, DropView

from steam_manager.db.reports import followed, games, scores, store_columns

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from steam_manager.db.reports.scores import Report

__all__ = ["create_views", "followed", "games", "reports", "scores", "store_columns"]


def reports(*, home_country: str) -> dict[str, Report]:
    """
    Build every report for one profile.

    :param home_country: The profile's home country, whose prices the reports show.
    :return: Each report's query, by the name of its view.
    """
    return {
        "v_app_scores": scores.app_scores(),
        "v_games": games.games(home_country),
        "v_followed": followed.followed(home_country),
    }


def create_views(engine: Engine, *, home_country: str) -> None:
    """
    Write every report into the database as a view, replacing the views of an earlier call.

    Views hold no data, so they are dropped and created again on every call: a view an older
    release wrote, or one from another home country, never lingers. Views of other names are
    left alone.

    :param engine: The profile database.
    :param home_country: The profile's home country.
    """
    with engine.begin() as connection:
        for name, query in reports(home_country=home_country).items():
            view = CreateView(query, name)
            connection.execute(DropView(view.table, if_exists=True))
            connection.execute(view)
