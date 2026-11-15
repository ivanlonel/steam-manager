"""The raw archive: the latest answer per source, kind, key and country, in one SQLite file."""

import compression.zstd
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Self

from sqlalchemy import URL, Integer, LargeBinary, Text, create_engine, event, insert, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from steam_manager.answers import Answer, Kind

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path
    from types import TracebackType

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

ARCHIVE_VERSION: Final = 1
"""The layout of the archive file this release reads and writes."""

_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND: Final = timedelta(microseconds=1)


class ArchiveVersionError(RuntimeError):
    """The archive file was written by a newer release, with a layout this one can't read."""

    def __init__(self, found: int, supported: int) -> None:
        """
        Name the two versions.

        :param found: The version the file records.
        :param supported: The newest version this release reads.
        """
        super().__init__(
            f"the archive has version {found}; this release reads up to {supported}. "
            "Upgrade steam-manager, or delete the archive: the next sync fetches it again."
        )
        self.found: int = found
        """The version the file records."""
        self.supported: int = supported
        """The newest version this release reads."""


class _Base(DeclarativeBase):
    """The declarative base of the archive's one table."""


class _ArchivedAnswer(_Base):
    """One answer as the archive stores it: compressed, and timed in microseconds."""

    __tablename__ = "answer"
    __table_args__ = {"sqlite_strict": True, "sqlite_with_rowid": False}  # noqa: RUF012  # SQLAlchemy reads this mapping once, at class creation

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    """Where the answer came from, such as ``steam``."""
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    """What the answer is about, a :class:`~steam_manager.answers.Kind`."""
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    """What it is about within its kind."""
    country: Mapped[str] = mapped_column(Text, primary_key=True)
    """The store country it was asked in, or ``""``."""
    fetched_at: Mapped[int] = mapped_column(Integer)
    """When it arrived, in microseconds since the Unix epoch."""
    body: Mapped[bytes] = mapped_column(LargeBinary)
    """Its JSON text, encoded as UTF-8 and compressed with zstd."""


def _micros(moment: datetime) -> int:
    """
    Turn an aware time into microseconds since the Unix epoch.

    :param moment: The time, with a zone.
    :return: The microseconds.
    :raise ValueError: When *moment* has no zone: it would be read back wrong.
    """
    if moment.utcoffset() is None:
        msg = f"an answer's time must be in UTC, not naive: {moment.isoformat()}"
        raise ValueError(msg)
    return (moment - _EPOCH) // _MICROSECOND


def _moment(micros: int) -> datetime:
    """
    Turn microseconds since the Unix epoch into a time in UTC.

    :param micros: The microseconds.
    :return: The time.
    """
    return _EPOCH + micros * _MICROSECOND


def _compress(body: str) -> bytes:
    """
    Compress an answer's JSON text.

    :param body: The text. Lone surrogates, from half an emoji escaped in Steam's JSON, are kept.
    :return: The compressed bytes.
    """
    return compression.zstd.compress(body.encode("utf-8", "surrogatepass"))


def _decompress(data: bytes) -> str:
    """
    Read back what :func:`_compress` wrote.

    :param data: The compressed bytes.
    :return: The text, exactly as it was.
    """
    return compression.zstd.decompress(data).decode("utf-8", "surrogatepass")


def _enable_wal(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """
    Turn on write-ahead logging on a new connection, so readers never wait for a writer.

    :param connection: The SQLite connection.
    :param _record: Its pool entry, unused.
    """
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class Archive:
    """A profile's raw archive: the only thing a source writes, and what the loader reads."""

    def __init__(self, path: Path) -> None:
        """
        Open the archive at *path*, creating it when missing.

        :param path: The archive file. Its folder must exist.
        :raise ArchiveVersionError: When the file was written by a newer release.
        """
        self._engine = create_engine(URL.create("sqlite", database=str(path)))
        event.listen(self._engine, "connect", _enable_wal)
        with self._engine.begin() as connection:
            version = connection.execute(text("PRAGMA user_version")).scalar_one()
            if version < ARCHIVE_VERSION:
                _Base.metadata.create_all(connection)
                connection.execute(text(f"PRAGMA user_version = {ARCHIVE_VERSION}"))
        if version > ARCHIVE_VERSION:
            self._engine.dispose()
            raise ArchiveVersionError(version, ARCHIVE_VERSION)

    def __enter__(self) -> Self:
        """
        Use the archive in a ``with`` block.

        :return: The archive.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Close the archive when the ``with`` block ends.

        :param exc_type: The exception's type, when one ended the block.
        :param exc: The exception.
        :param traceback: Its traceback.
        """
        self.close()

    def close(self) -> None:
        """Close the archive's connections."""
        self._engine.dispose()

    def put(self, answers: Iterable[Answer]) -> None:
        """
        Store answers.

        :param answers: The answers.
        :raise ValueError: When an answer's time has no zone.
        """
        rows = [
            {
                "source": answer.source,
                "kind": str(answer.kind),
                "key": answer.key,
                "country": answer.country,
                "fetched_at": _micros(answer.fetched_at),
                "body": _compress(answer.body),
            }
            for answer in answers
        ]
        if rows:
            with self._engine.begin() as connection:
                connection.execute(insert(_ArchivedAnswer), rows)

    def get(self, source: str, kind: Kind, key: str, country: str = "") -> Answer | None:
        """
        Fetch one answer.

        :param source: Where it came from, such as ``steam``.
        :param kind: What it is about.
        :param key: What it is about within its kind.
        :param country: The store country it was asked in, or ``""``.
        :return: The answer, or ``None`` when the archive has none.
        """
        query = select(_ArchivedAnswer.fetched_at, _ArchivedAnswer.body).where(
            _ArchivedAnswer.source == source,
            _ArchivedAnswer.kind == str(kind),
            _ArchivedAnswer.key == key,
            _ArchivedAnswer.country == country,
        )
        with self._engine.connect() as connection:
            row = connection.execute(query).one_or_none()
        if row is None:
            return None
        return Answer(source, kind, key, country, _decompress(row.body), _moment(row.fetched_at))
