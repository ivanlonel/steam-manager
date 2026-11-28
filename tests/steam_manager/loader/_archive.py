"""Put recorded and changed answers into an archive, for the loader's tests."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from steam_manager.answers import Answer

if TYPE_CHECKING:
    from collections.abc import Callable

    from steam_manager.answers import Kind
    from steam_manager.archive import Archive

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam"
"""The recorded Steam answers."""
AT: Final = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
"""When the test answers arrived."""


def recorded(name: str) -> str:
    """
    Read a recorded answer's text.

    :param name: Its path under the fixtures, such as ``store_item/620-BR.json``.
    :return: The text.
    """
    return (FIXTURES / name).read_text(encoding="utf-8")


def changed(name: str, change: Callable[[dict[str, object]], None]) -> str:
    """
    Read a recorded answer and change it, as a later answer from Steam might differ.

    :param name: Its path under the fixtures.
    :param change: What to change in it, in place.
    :return: The changed answer's text.
    """
    answer: dict[str, object] = json.loads(recorded(name))
    change(answer)
    return json.dumps(answer, ensure_ascii=False)


def put(  # an answer's identity, its text and its time
    archive: Archive,
    kind: Kind,
    key: str,
    country: str,
    body: str,
    *,
    at: datetime = AT,
    source: str = "steam",
) -> None:
    """
    Archive one answer.

    :param archive: The archive.
    :param kind: What it is about.
    :param key: What it is about within its kind.
    :param country: The store country it was asked in, or ``""``.
    :param body: Its text.
    :param at: When it arrived.
    :param source: Where it came from.
    """
    archive.put([Answer(source, kind, key, country, body, at)])


def damage(path: Path, key: str) -> None:
    """
    Overwrite an archived answer's body with bytes that don't decompress.

    :param path: The archive file.
    :param key: The answer's key.
    """
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE answer SET body = ? WHERE key = ?", (b"oops", key))
        connection.commit()
