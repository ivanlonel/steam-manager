"""
The reports: named tables of results the application computes over the database.

Each is a query the application runs with the profile's home country. :func:`create_views`
also writes every report into the database as a view of the same name, so that other SQLite
tools see them.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.schema import CreateView, DropView

from steam_manager.db.reports import followed, games, scores, store_columns, wishlist

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from steam_manager.db.reports.scores import Report

__all__ = [
    "create_views",
    "followed",
    "games",
    "reports",
    "scores",
    "store_columns",
    "wishlist",
]


def reports(*, home_country: str) -> dict[str, Report]:
    """
    Build every report for one profile.

    :param home_country: The profile's home country, whose prices the reports show.
    :return: Each report's query, by the name of its view.
    """
    return {
        "v_app_scores": scores.app_scores(),
        "v_games": games.games(home_country),
        "v_wishlist": wishlist.wishlist(home_country),
        "v_followed": followed.followed(home_country),
    }


def create_views(engine: Engine, *, home_country: str) -> None:
    """
    Write every report into the database as a view, where the file's view differs from it.

    A view an older release wrote, or one for another home country, is replaced. A view that is
    already current is only read, so opening a database while a sync writes to it never waits
    for the sync's lock. Views of other names are left alone.

    :param engine: The profile database.
    :param home_country: The profile's home country.
    """
    # ponytail: only the current reports' names are looked at, so a report a later release
    # retires leaves its view behind; that release drops it by name. A stale view also stops
    # SQLite renaming the tables it reads, which matters once Alembic migrates user tables.
    with engine.begin() as connection:
        views = text("SELECT name, sql FROM sqlite_schema WHERE type = 'view'")
        stored: dict[str, str] = {row.name: row.sql for row in connection.execute(views)}
        for name, query in reports(home_country=home_country).items():
            view = CreateView(query, name)
            if stored.get(name) == str(view.compile(dialect=connection.dialect)):
                continue
            connection.execute(DropView(view.table, if_exists=True))
            connection.execute(view)
