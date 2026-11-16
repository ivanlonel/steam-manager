"""Tests for opening the profile database."""

import sqlite3
lazy from pathlib import Path

import pytest
from sqlalchemy import exc, text

from steam_manager.db.engine import open_database


def test_an_old_sqlite_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reports need SQLite 3.44; an older one is named, not left to fail on a statement."""
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 1))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.40.1")

    with pytest.raises(RuntimeError, match=r"SQLite 3\.40\.1 .* 3\.44"):
        open_database(tmp_path / "steam.sqlite")


def test_the_database_runs_in_wal_mode(tmp_path: Path) -> None:
    """WAL lets the web interface read while a sync writes."""
    engine = open_database(tmp_path / "steam.sqlite")

    with engine.connect() as first, engine.connect() as second:
        first.execute(text("SELECT 1"))
        mode = second.execute(text("PRAGMA journal_mode")).scalar_one()
    engine.dispose()

    assert mode == "wal"


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    """A row pointing at a missing parent is refused."""
    engine = open_database(tmp_path / "steam.sqlite")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY) STRICT"))
        connection.execute(
            text("CREATE TABLE child (parent INTEGER REFERENCES parent (id)) STRICT")
        )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO child VALUES (620)"))
    engine.dispose()


def test_each_connection_gets_the_pragmas(tmp_path: Path) -> None:
    """Foreign keys are a per-connection setting in SQLite: every connection turns them on."""
    engine = open_database(tmp_path / "steam.sqlite")

    with engine.connect() as first, engine.connect() as second:
        values = [
            connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            for connection in (first, second)
        ]
    engine.dispose()

    assert values == [1, 1]
