"""Fixtures for the loader's tests: an archive and a profile database in a temporary folder."""

from typing import TYPE_CHECKING

import pytest

from steam_manager.archive import Archive
from steam_manager.db.engine import open_database
from steam_manager.db.steam_schema import ensure_steam_schema

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Engine


# Fixtures are named apart from their functions, so tests can take them as arguments without
# shadowing a module-level name (pylint's redefined-outer-name).
@pytest.fixture(name="archive")
def archive_fixture(tmp_path: Path) -> Iterator[Archive]:
    """
    Open an empty raw archive.

    :param tmp_path: Where the file goes.
    :yield: The archive, closed afterwards.
    """
    with Archive(tmp_path / "archive.sqlite") as archive:
        yield archive


@pytest.fixture(name="engine")
def engine_fixture(tmp_path: Path) -> Iterator[Engine]:
    """
    Open a profile database with empty Steam tables, as a first open leaves it.

    :param tmp_path: Where the file goes.
    :yield: Its engine, disposed of afterwards.
    """
    engine = open_database(tmp_path / "steam.sqlite")
    ensure_steam_schema(engine)
    yield engine
    engine.dispose()
