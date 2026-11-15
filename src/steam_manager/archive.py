"""The raw archive: the latest answer per source, kind, key and country, in one SQLite file."""

import compression.zstd
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Self

from sqlalchemy import URL, Integer, LargeBinary, Text, create_engine, event, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from steam_manager.answers import Answer, Kind

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path
    from types import TracebackType

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

ARCHIVE_VERSION: Final = 1
"""The layout of the archive file this release reads and writes."""
STREAM_ROWS: Final = 500
"""Rows read from SQLite at a time while :meth:Archive.answers streams."""

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


class CorruptAnswerError(ValueError):
    """An archived answer can't be read back: its stored bytes are damaged."""

    def __init__(self, source: str, kind: str, key: str, country: str) -> None:
        """
        Name the answer that can't be read.

        :param source: Where it came from.
        :param kind: What it is about.
        :param key: What it is about within its kind.
        :param country: The store country it was asked in, or ``""``.
        """
        super().__init__(f"the archived answer {source} {kind} {key} {country} is damaged")
        self.source: str = source
        """Where it came from."""
        self.kind: str = kind
        """What it is about."""
        self.key: str = key
        """What it is about within its kind."""
        self.country: str = country
        """The store country it was asked in, or ``""``."""


def _answer(
    source: str, kind: str, key: str, country: str, *, fetched_at: int, body: bytes
) -> Answer:
    """
    Rebuild an answer from an archive row.

    :param source: The row's source.
    :param kind: Its kind.
    :param key: Its key.
    :param country: Its country.
    :param fetched_at: Its time, in microseconds since the Unix epoch.
    :param body: Its compressed body.
    :return: The answer, exactly as it was put.
    :raise CorruptAnswerError: When the body doesn't decompress.
    """
    try:
        text_ = compression.zstd.decompress(body).decode("utf-8", "surrogatepass")
    except compression.zstd.ZstdError, UnicodeDecodeError:
        raise CorruptAnswerError(source, kind, key, country) from None
    return Answer(source, Kind(kind), key, country, text_, _moment(fetched_at))


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
        Store answers, keeping for each key the one fetched last, in one transaction.

        :param answers: The answers; all of them are written, or none.
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
            # Latest means fetched last, not written last: an older answer, such as a Kaggle
            # import dated by its file, never replaces a newer one. A tie keeps the first.
            upsert = insert(_ArchivedAnswer)
            upsert = upsert.on_conflict_do_update(
                index_elements=["source", "kind", "key", "country"],
                set_={"fetched_at": upsert.excluded.fetched_at, "body": upsert.excluded.body},
                where=upsert.excluded.fetched_at > _ArchivedAnswer.fetched_at,
            )
            with self._engine.begin() as connection:
                connection.execute(upsert, rows)

    def get(self, source: str, kind: Kind, key: str, country: str = "") -> Answer | None:
        """
        Fetch one answer.

        :param source: Where it came from, such as ``steam``.
        :param kind: What it is about.
        :param key: What it is about within its kind.
        :param country: The store country it was asked in, or ``""``.
        :return: The answer, or ``None`` when the archive has none.
        :raise CorruptAnswerError: When its stored bytes are damaged.
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
        return _answer(source, str(kind), key, country, fetched_at=row.fetched_at, body=row.body)

    def answers(self, *, source: str | None = None, kind: Kind | None = None) -> Generator[Answer]:
        """
        Read every answer, or those of one source or kind, as the loader and a rebuild do.

        :param source: Only answers from this source, such as ``steam``.
        :param kind: Only answers of this kind.
        :yield: The answers, ordered by source, kind, key and country, read as they are used:
            a whole catalog is never held at once.
        :raise CorruptAnswerError: At an answer whose stored bytes are damaged.
        """
        key = (
            _ArchivedAnswer.source,
            _ArchivedAnswer.kind,
            _ArchivedAnswer.key,
            _ArchivedAnswer.country,
        )
        query = select(*key, _ArchivedAnswer.fetched_at, _ArchivedAnswer.body).order_by(*key)
        if source is not None:
            query = query.where(_ArchivedAnswer.source == source)
        if kind is not None:
            query = query.where(_ArchivedAnswer.kind == str(kind))
        with self._engine.connect() as connection:
            for row in connection.execute(query.execution_options(yield_per=STREAM_ROWS)):
                yield _answer(
                    row.source,
                    row.kind,
                    row.key,
                    row.country,
                    fetched_at=row.fetched_at,
                    body=row.body,
                )

    def fetched_at(self, source: str, kind: Kind, *, country: str = "") -> dict[str, datetime]:
        """
        Tell when each key's answer of one kind arrived: what the sync's staleness rests on.

        :param source: Where the answers came from, such as ``steam``.
        :param kind: Their kind.
        :param country: The store country they were asked in, or ``""``.
        :return: Each key's time, in UTC.
        """
        query = select(_ArchivedAnswer.key, _ArchivedAnswer.fetched_at).where(
            _ArchivedAnswer.source == source,
            _ArchivedAnswer.kind == str(kind),
            _ArchivedAnswer.country == country,
        )
        with self._engine.connect() as connection:
            return {row.key: _moment(row.fetched_at) for row in connection.execute(query)}
