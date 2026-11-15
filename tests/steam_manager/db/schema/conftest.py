"""Fixtures for the Steam table tests."""

from typing import TYPE_CHECKING

import pytest

from steam_manager.db.engine import open_database
from steam_manager.db.schema import SteamBase

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Engine


@pytest.fixture
def steam_tables(tmp_path: Path) -> Iterator[Engine]:
    """
    Open a database holding every Steam table, as the application opens one.

    :param tmp_path: Where the file goes.
    :yield: Its engine, disposed of afterwards.
    """
    engine = open_database(tmp_path / "steam.sqlite")
    SteamBase.metadata.create_all(engine)
    yield engine
    engine.dispose()
