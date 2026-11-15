"""Tests for the raw archive: the latest answer per source, kind, key and country."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from typing import Final
lazy from collections.abc import Iterator
lazy from pathlib import Path

import pytest

from steam_manager.answers import Answer, Kind
from steam_manager.archive import ARCHIVE_VERSION, Archive, ArchiveVersionError

AT: Final = datetime(2026, 11, 15, 12, 0, 0, 123456, UTC)
"""When the test answers arrived, to the microsecond."""


def answer(
    key: str = "620",
    *,
    country: str = "BR",
    kind: Kind = Kind.STORE_ITEM,
    body: str = '{"id":620}',
    at: datetime = AT,
) -> Answer:
    """
    Make a Steam answer for the tests.

    :param key: What it is about.
    :param country: The store country it was asked in.
    :param kind: What kind of answer it is.
    :param body: Its JSON text.
    :param at: When it arrived.
    :return: The answer.
    """
    return Answer("steam", kind, key, country, body, at)


# Fixtures are named apart from their functions, so tests can take them as arguments without
# shadowing a module-level name (pylint's redefined-outer-name).
@pytest.fixture(name="path")
def path_fixture(tmp_path: Path) -> Path:
    """
    Name an archive file in a temporary folder.

    :param tmp_path: pytest's temporary folder for the test.
    :return: Where the archive goes.
    """
    return tmp_path / "archive.sqlite"


@pytest.fixture(name="archive")
def archive_fixture(path: Path) -> Iterator[Archive]:
    """
    Open a new archive, and close it after the test.

    :param path: Where the archive goes.
    :yield: The archive.
    """
    with Archive(path) as opened:
        yield opened


def test_an_answer_comes_back_as_it_was_put(archive: Archive) -> None:
    """Every part of an answer, its time to the microsecond included, is read back."""
    archive.put([answer()])

    assert archive.get("steam", Kind.STORE_ITEM, "620", "BR") == answer()


def test_a_missing_answer_is_none(archive: Archive) -> None:
    """An answer never put is ``None``, not an error."""
    assert archive.get("steam", Kind.STORE_ITEM, "620", "BR") is None


def test_the_body_is_stored_compressed(archive: Archive, path: Path) -> None:
    """Bodies are compressed with zstd; JSON shrinks a lot."""
    archive.put([answer(body='{"text":"' + "Portal 2 " * 6000 + '"}')])

    with closing(sqlite3.connect(path)) as connection:
        blob = connection.execute("SELECT body FROM answer").fetchone()[0]

    assert blob[:4] == bytes.fromhex("28b52ffd")  # zstd's magic number
    assert len(blob) < 5_000


def test_text_outside_ascii_comes_back_exactly(archive: Archive) -> None:
    """CJK text, an emoji, and half of one (which Steam's JSON can carry) survive the trip."""
    body = '{"name": "ポータル2 🎮 \ud83d"}'
    archive.put([answer(body=body)])

    found = archive.get("steam", Kind.STORE_ITEM, "620", "BR")

    assert found is not None
    assert found.body == body


def test_the_table_is_strict_without_rowid(archive: Archive, path: Path) -> None:
    """The table checks its column types, and is stored by its key."""
    del archive  # the fixture created the file
    with closing(sqlite3.connect(path)) as connection:
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'answer'").fetchone()[
            0
        ]

    assert "STRICT" in sql
    assert "WITHOUT ROWID" in sql


def test_the_archive_runs_in_wal_mode(archive: Archive, path: Path) -> None:
    """WAL lets the web interface read while a sync writes."""
    del archive
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_a_new_archive_has_this_version(archive: Archive, path: Path) -> None:
    """A new file records the archive version that wrote it."""
    del archive
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == ARCHIVE_VERSION


def test_a_newer_archive_is_refused(path: Path) -> None:
    """A file written by a newer release is never read by this one."""
    Archive(path).close()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(ArchiveVersionError) as caught:
        Archive(path)

    assert (caught.value.found, caught.value.supported) == (2, 1)


def test_putting_nothing_writes_nothing(archive: Archive) -> None:
    """An empty batch, such as a page with no new apps, is fine."""
    archive.put([])

    assert archive.get("steam", Kind.STORE_ITEM, "620", "BR") is None


def test_a_naive_time_is_refused(archive: Archive) -> None:
    """A time without a zone would be read back wrong, so it is refused."""
    with pytest.raises(ValueError, match="UTC"):
        archive.put([answer(at=datetime(2026, 11, 15))])  # noqa: DTZ001  # the naive time is the point


LATER: Final = AT + timedelta(hours=1)
"""An hour after :data:`AT`."""


def test_a_newer_answer_replaces_the_older(archive: Archive) -> None:
    """Only the latest answer of a key is kept."""
    archive.put([answer(body='{"v":1}')])
    archive.put([answer(body='{"v":2}', at=LATER)])

    found = archive.get("steam", Kind.STORE_ITEM, "620", "BR")

    assert found is not None
    assert (found.body, found.fetched_at) == ('{"v":2}', LATER)


def test_an_older_answer_never_replaces_a_newer(archive: Archive) -> None:
    """Latest means fetched last: a Kaggle import dated by its file never undoes a fresh fetch."""
    archive.put([answer(body='{"v":2}', at=LATER)])
    archive.put([answer(body='{"v":1}')])

    found = archive.get("steam", Kind.STORE_ITEM, "620", "BR")

    assert found is not None
    assert found.body == '{"v":2}'


def test_the_country_and_the_kind_keep_answers_apart(archive: Archive) -> None:
    """One app's BR entry, US entry and light entry are three answers."""
    archive.put(
        [
            answer(body='{"c":"BR"}'),
            answer(country="US", body='{"c":"US"}'),
            answer(kind=Kind.STORE_ITEM_LIGHT, body='{"light":true}'),
        ]
    )

    br = archive.get("steam", Kind.STORE_ITEM, "620", "BR")
    us = archive.get("steam", Kind.STORE_ITEM, "620", "US")
    light = archive.get("steam", Kind.STORE_ITEM_LIGHT, "620", "BR")

    assert br is not None
    assert us is not None
    assert light is not None
    assert (br.body, us.body, light.body) == ('{"c":"BR"}', '{"c":"US"}', '{"light":true}')


def test_a_bad_answer_writes_nothing_of_its_batch(archive: Archive) -> None:
    """A batch is written whole or not at all, so an interrupted sync leaves no half batch."""
    naive = datetime(2026, 11, 15)  # noqa: DTZ001  # the naive time is the point
    batch = [answer("10"), answer("20", at=naive), answer("30")]

    with pytest.raises(ValueError, match="UTC"):
        archive.put(batch)

    assert archive.get("steam", Kind.STORE_ITEM, "10", "BR") is None


def test_another_archive_on_the_file_sees_each_batch(archive: Archive, path: Path) -> None:
    """The web interface's archive sees what the sync's archive committed, at once."""
    with Archive(path) as reader:
        archive.put([answer()])

        assert reader.get("steam", Kind.STORE_ITEM, "620", "BR") == answer()


def test_the_archive_works_from_worker_threads(archive: Archive) -> None:
    """The sync calls the archive through asyncio.to_thread, from any worker thread."""

    async def through_threads() -> Answer | None:
        await asyncio.to_thread(archive.put, [answer()])
        return await asyncio.to_thread(archive.get, "steam", Kind.STORE_ITEM, "620", "BR")

    assert asyncio.run(through_threads()) == answer()
