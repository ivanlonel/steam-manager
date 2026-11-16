"""Build the notebook's views and the reports on the same rows, and compare what they show."""

import math
import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING, Final, NamedTuple
lazy from pathlib import Path

from steam_manager.db.engine import open_database
from steam_manager.db.reports import create_views
from steam_manager.db.schema import SteamBase
from tests.steam_manager.db.schema._notebook import NOTEBOOK_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy import Connection

type Sample = Mapping[str, Sequence[Mapping[str, object]]]
"""Rows to insert, by table, in an order the foreign keys allow."""

NOTEBOOK_VIEWS: Final = NOTEBOOK_SCHEMA.with_name("steam_database_views.sql")
"""The notebook's public views, as its cell 7 builds them."""

TOLERANCE: Final = 1e-9
"""How far apart two scores may be, for float arithmetic done in another order."""


class View(NamedTuple):
    """What a view shows: its columns, in order, and its rows, ordered by appid."""

    columns: list[str]
    """The column names."""
    rows: list[dict[str, object]]
    """One mapping of column to value per row."""


def notebook_view(view: str, sample: Sample) -> View:
    """
    Read one of the notebook's views, over *sample*.

    :param view: The view.
    :param sample: The rows its tables hold.
    :return: What it shows.
    """
    with closing(_notebook(sample)) as connection:
        return _read(connection, view)


def report_view(folder: Path, view: str, sample: Sample, *, home_country: str = "BR") -> View:
    """
    Read a report's view, written into a new database holding *sample*.

    :param folder: Where the database goes.
    :param view: The view.
    :param sample: The rows its tables hold.
    :param home_country: The profile's home country.
    :return: What it shows.
    """
    with closing(_ours(folder, sample, home_country=home_country)) as connection:
        return _read(connection, view)


def _read(connection: sqlite3.Connection, view: str) -> View:
    """
    Read a view's columns and rows.

    :param connection: The database.
    :param view: The view.
    :return: What it shows.
    """
    columns = [name for _, name, *_ in connection.execute(f"PRAGMA table_info({view})")]
    cursor = connection.execute(f'SELECT * FROM "{view}" ORDER BY appid')  # noqa: S608  # the tests' view names
    names = [description[0] for description in cursor.description]
    return View(columns, [dict(zip(names, row, strict=True)) for row in cursor])


def _notebook(sample: Sample) -> sqlite3.Connection:
    """
    Build the notebook's tables and views in memory, holding *sample*.

    Columns the notebook doesn't have, such as the stored formatted prices, are left out.

    :param sample: The rows.
    :return: A connection holding them.
    """
    connection = sqlite3.connect(":memory:")
    connection.executescript(NOTEBOOK_SCHEMA.read_text(encoding="utf-8"))
    connection.executescript(NOTEBOOK_VIEWS.read_text(encoding="utf-8"))
    for table, table_rows in sample.items():
        known = {column for _, column, *_ in connection.execute(f"PRAGMA table_info({table})")}
        for row in table_rows:
            values = {column: value for column, value in row.items() if column in known}
            connection.execute(_insert(table, values), tuple(values.values()))
    connection.commit()
    return connection


def _ours(folder: Path, sample: Sample, *, home_country: str) -> sqlite3.Connection:
    """
    Build the Steam tables and the reports' views in a file, holding *sample*.

    :param folder: Where the file goes.
    :param sample: The rows.
    :param home_country: The profile's home country.
    :return: A connection to the file, opened apart from the engine that built it.
    """
    path = folder / "steam.sqlite"
    engine = open_database(path)
    SteamBase.metadata.create_all(engine)
    with engine.begin() as connection:
        _load(connection, sample)
    create_views(engine, home_country=home_country)
    engine.dispose()
    return sqlite3.connect(path)


def _load(connection: Connection, sample: Sample) -> None:
    """
    Insert *sample* through SQLAlchemy, with foreign keys on.

    :param connection: The database.
    :param sample: The rows.
    """
    for table, table_rows in sample.items():
        for row in table_rows:
            connection.exec_driver_sql(_insert(table, row), tuple(row.values()))


def _insert(table: str, row: Mapping[str, object]) -> str:
    """
    Write the INSERT for one row.

    :param table: The table.
    :param row: Its values, by column.
    :return: The statement, with a placeholder per value.
    """
    names, marks = ", ".join(row), ", ".join("?" * len(row))
    return f"INSERT INTO {table} ({names}) VALUES ({marks})"  # noqa: S608  # names are the tests'


def mismatches(
    expected_rows: Sequence[Mapping[str, object]], actual_rows: Sequence[Mapping[str, object]]
) -> list[str]:
    """
    List where two views' rows differ, on the columns they share.

    :param expected_rows: The notebook view's rows.
    :param actual_rows: The report's rows.
    :return: One line per differing value, such as ``"620 bayes_avg: 97.1 != 97.2"``.
    """
    counts = len(expected_rows), len(actual_rows)
    found = [f"rows: {counts[0]} != {counts[1]}"] if counts[0] != counts[1] else []
    for expected, actual in zip(expected_rows, actual_rows, strict=False):
        found += [
            f"{expected.get('appid')} {column}: {expected[column]!r} != {actual[column]!r}"
            for column in expected.keys() & actual.keys()
            if not _same(expected[column], actual[column])
        ]
    return sorted(found)


def _same(expected: object, actual: object) -> bool:
    """
    Say whether two values are equal, floats within :data:`TOLERANCE`.

    :param expected: The notebook's value.
    :param actual: The report's value.
    :return: Whether they match.
    """
    if isinstance(expected, float) and isinstance(actual, float):
        return math.isclose(expected, actual, rel_tol=TOLERANCE, abs_tol=TOLERANCE)
    return expected == actual
