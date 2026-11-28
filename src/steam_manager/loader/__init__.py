"""
The loader: the one path from archived answers to database rows (ADR 0002).

A load makes the Steam tables reflect the raw archive in one transaction. It reads every
answer's stamp, finds those fetched since the database last reflected them, and loads only
what they change: each app they describe is replaced in place, from its most complete answer.
"""

import itertools
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Final, cast

from pydantic import ValidationError
from sqlalchemy import Column, MetaData, Table, Text, and_, delete, insert, select
from sqlalchemy.dialects.sqlite import insert as upsert

from steam_manager.answers import Kind
from steam_manager.archive import CorruptAnswerError
from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.lookups import StoreCategory
from steam_manager.db.schema.progress import LoadedAnswer
from steam_manager.loader.store_item import describe
from steam_manager.loader.write import ForeignKeyViolationError, Writer, check_foreign_keys
from steam_manager.steam.models.store_item import StoreItem

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pydantic import BaseModel
    from sqlalchemy import Connection, Engine, Row, Select

    from steam_manager.archive import Archive
    from steam_manager.loader.rows import Findings
    from steam_manager.loader.store_item import Described

__all__ = [
    "LOAD_BATCH",
    "ForeignKeyViolationError",
    "LoadReport",
    "Malformed",
    "describe",
    "load",
    "rebuild",
]

LOAD_BATCH: Final = 500
"""Apps written at a time, inside the load's one transaction."""
STAMP_CHUNK: Final = 5000
"""Stamps copied into the database at a time."""

_STORE_KINDS: Final = (str(Kind.STORE_ITEM), str(Kind.STORE_ITEM_LIGHT))
_NESTED: Final = "included_items.included_apps[]"
_IDENTITY: Final = ("source", "kind", "key", "country")
_LOADED: Final = cast("Table", LoadedAnswer.__table__)
_STAMP: Final = Table(
    "stamp",
    MetaData(),
    Column("source", Text, primary_key=True),
    Column("kind", Text, primary_key=True),
    Column("key", Text, primary_key=True),
    Column("country", Text, primary_key=True),
    Column("fetched_at", Text, nullable=False),
    prefixes=["TEMPORARY"],
    sqlite_with_rowid=False,
)

type StampRow = Row[*tuple[Any, ...]]
"""An archived answer's stamp, as the load's temporary table holds it."""


@dataclass(frozen=True, slots=True)
class Malformed:
    """An archived answer the load skipped, named without a word of what it holds."""

    source: str
    """Where it came from."""
    kind: str
    """What it is about."""
    key: str
    """What it is about within its kind."""
    country: str
    """The store country it was asked in, or ``""``."""
    reason: str
    """Why it was skipped: ``damaged``, or where and how it failed validation."""


@dataclass
class LoadReport:
    """What a load did, and what a healthy one leaves empty."""

    unknown: Counter[str] = field(default_factory=Counter)
    """Fields Steam sent that nothing stores, by path. A store item's paths start at its top;
    every other kind's start with the kind."""
    mismatches: Counter[str] = field(default_factory=Counter)
    """Values left out as derivable, with how often they didn't follow."""
    malformed: list[Malformed] = field(default_factory=list)
    """Answers skipped because they couldn't be read or didn't validate."""
    loaded: Counter[str] = field(default_factory=Counter)
    """Rows written, by table."""
    blank_parents: Counter[str] = field(default_factory=Counter)
    """Blank rows added for references to rows nothing describes, by table."""

    def add(self, findings: Findings) -> None:
        """
        Count what one answer left out or contradicted.

        :param findings: Its findings.
        """
        self.unknown.update(findings.unknown)
        self.mismatches.update(findings.mismatches)


def load(archive: Archive, engine: Engine, *, countries: Sequence[str]) -> LoadReport:
    """
    Make the Steam tables reflect the archive, loading only what changed since the last load.

    A load that stops before it commits leaves the tables as they were, and the next one does
    its work too. A change of countries needs :func:`rebuild` instead: a load ranks again only
    the apps whose answers changed.

    :param archive: The profile's raw archive.
    :param engine: The profile database, its Steam tables current.
    :param countries: The home country, then the fallback countries in order.
    :return: What the load did and found.
    """
    return _load(archive, engine, countries, fresh=False)


def rebuild(archive: Archive, engine: Engine, *, countries: Sequence[str]) -> LoadReport:
    """
    Empty the Steam tables and load the whole archive again, in one transaction.

    :param archive: The profile's raw archive.
    :param engine: The profile database, its Steam tables current.
    :param countries: The home country, then the fallback countries in order.
    :return: What the rebuild did and found.
    """
    return _load(archive, engine, countries, fresh=True)


def _load(
    archive: Archive, engine: Engine, countries: Sequence[str], *, fresh: bool
) -> LoadReport:
    """
    Run a load, or a rebuild when *fresh*.

    :param archive: The profile's raw archive.
    :param engine: The profile database.
    :param countries: The home country, then the fallback countries in order.
    :param fresh: Whether to empty the Steam tables first.
    :return: What it did and found.
    :raise ValueError: When *countries* is empty.
    :raise RuntimeError: When SQLite kept foreign keys on, so rows couldn't load in any order.
    """
    if not countries:
        message = "a load needs the home country"
        raise ValueError(message)
    report = LoadReport()
    with engine.connect() as connection:
        try:
            with connection.begin():
                # First in the transaction: SQLite ignores the pragma once a write began one.
                connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
                if connection.exec_driver_sql("PRAGMA foreign_keys").scalar():
                    message = "foreign keys are still on: rows can't load in any order"
                    raise RuntimeError(message)
                if fresh:
                    for table in reversed(SteamBase.metadata.sorted_tables):
                        connection.execute(delete(table))
                _Load(connection, archive, countries, report).run()
        finally:
            connection.rollback()  # no transaction stays open for the clean-up
            connection.exec_driver_sql("DROP TABLE IF EXISTS temp.stamp")
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.commit()
    return report


def _reason(error: ValidationError) -> str:
    """
    Say where and how an answer failed validation, never with a value from it.

    :param error: The validation error.
    :return: Each failure's location and type, such as ``tags.0.tagid: int_parsing``.
    """
    return "; ".join(
        f"{'.'.join(map(str, failure['loc'])) or 'answer'}: {failure['type']}"
        for failure in error.errors(include_url=False, include_context=False, include_input=False)
    )


def _changed(kinds: Iterable[str] | None = None) -> Select[*tuple[Any, ...]]:
    """
    Select the stamps fetched since the database last reflected them.

    :param kinds: Only stamps of these kinds; every kind when ``None``.
    :return: The query.
    """
    same = and_(*(_STAMP.c[name] == _LOADED.c[name] for name in _IDENTITY))
    query = (
        select(*_STAMP.c)
        .select_from(_STAMP.outerjoin(_LOADED, same))
        .where(_LOADED.c.fetched_at.is_distinct_from(_STAMP.c.fetched_at))
    )
    return query if kinds is None else query.where(_STAMP.c.kind.in_(list(kinds)))


class _Load:
    """One load's work, inside its transaction."""

    def __init__(
        self,
        connection: Connection,
        archive: Archive,
        countries: Sequence[str],
        report: LoadReport,
    ) -> None:
        """
        Prepare a load.

        :param connection: Its connection, inside its transaction, foreign keys off.
        :param archive: The raw archive.
        :param countries: The home country, then the fallback countries in order.
        :param report: Where what it does and finds goes.
        """
        self._connection = connection
        self._archive = archive
        self._countries = list(countries)
        self._report = report
        self._writer = Writer(connection, home=countries[0])
        self._category_types: dict[int, int] = {}
        self._nested: dict[int, tuple[tuple[int, float], StampRow]] = {}

    def run(self) -> None:
        """Copy the stamps, load what changed, check every reference and record the progress."""
        _STAMP.create(self._connection)
        for chunk in itertools.batched(self._archive.stamps(), STAMP_CHUNK, strict=False):
            self._connection.execute(
                insert(_STAMP),
                [
                    {
                        "source": stamp.source,
                        "kind": stamp.kind,
                        "key": stamp.key,
                        "country": stamp.country,
                        "fetched_at": stamp.fetched_at.isoformat(timespec="microseconds"),
                    }
                    for stamp in chunk
                ],
            )
        types = select(StoreCategory.categoryid, StoreCategory.type)
        self._category_types = {
            categoryid: kind
            for categoryid, kind in self._connection.execute(types)
            if kind is not None
        }
        self._apps()
        self._gaps()
        check_foreign_keys(self._connection)
        statement = upsert(_LOADED).from_select([*_IDENTITY, "fetched_at"], _changed())
        statement = statement.on_conflict_do_update(
            index_elements=_IDENTITY, set_={"fetched_at": statement.excluded.fetched_at}
        )
        self._connection.execute(statement)
        self._report.add(self._writer.findings)
        self._report.loaded.update(self._writer.loaded)
        self._report.blank_parents.update(self._writer.blank_parents)

    def _place(self, stamp: StampRow) -> tuple[int, float]:
        """
        Place an answer by its country, then by when it was fetched, the latest first.

        :param stamp: The answer's stamp.
        :return: The country's place in the profile's list, others after it, and the time
            negated.
        """
        country = (
            self._countries.index(stamp.country)
            if stamp.country in self._countries
            else len(self._countries)
        )
        return country, -datetime.fromisoformat(stamp.fetched_at).timestamp()

    def _rank(self, stamp: StampRow) -> tuple[int, int, float]:
        """
        Rank an app's own answer: full before light, then by its place.

        :param stamp: The answer's stamp.
        :return: Its rank; lower is better.
        """
        return (0 if stamp.kind == str(Kind.STORE_ITEM) else 1, *self._place(stamp))

    def _parse[M: BaseModel](self, stamp: StampRow, model: type[M]) -> M | None:
        """
        Read an archived answer and validate it, reporting it when it can't be.

        :param stamp: The answer's stamp.
        :param model: Its payload model.
        :return: The validated answer, or ``None`` when it was skipped.
        """
        try:
            answer = self._archive.get(stamp.source, Kind(stamp.kind), stamp.key, stamp.country)
        except CorruptAnswerError:
            self._malformed(stamp, "damaged")
            return None
        if answer is None:  # pragma: no cover  # another process can't delete an answer yet
            return None
        try:
            return model.model_validate_json(answer.body)
        except ValidationError as error:
            self._malformed(stamp, _reason(error))
            return None

    def _malformed(self, stamp: StampRow, reason: str) -> None:
        """
        Report an answer the load skips.

        :param stamp: Its stamp.
        :param reason: Why it is skipped.
        """
        self._report.malformed.append(
            Malformed(stamp.source, stamp.kind, stamp.key, stamp.country, reason)
        )

    def _apps(self) -> None:
        """Replace every app whose own answers changed, from its most complete answer."""
        keys = select(_changed(_STORE_KINDS).subquery().c.key).scalar_subquery()
        candidates = (
            select(*_STAMP.c)
            .where(_STAMP.c.kind.in_(_STORE_KINDS), _STAMP.c.key.in_(keys))
            .order_by(_STAMP.c.key)
        )
        batch: list[tuple[Described, StampRow]] = []
        rows = self._connection.execute(candidates)
        for _, stamps in itertools.groupby(rows, key=attrgetter("key")):
            if chosen := self._choose(list(stamps)):
                batch.append(chosen)
            if len(batch) >= LOAD_BATCH:
                self._write(batch)
                batch = []
        if batch:
            self._write(batch)

    def _choose(self, stamps: Sequence[StampRow]) -> tuple[Described, StampRow] | None:
        """
        Describe an app from its best answer: the first that succeeded, else the first one read.

        :param stamps: The stamps of the app's own answers.
        :return: The app's rows and the answer they came from, or ``None`` when none could be
            read.
        """
        fallback = None
        for stamp in sorted(stamps, key=self._rank):
            item = self._parse(stamp, StoreItem)
            if item is None:
                continue
            if str(item.id) != stamp.key:
                self._malformed(stamp, "its id isn't its key")
                continue
            try:
                found = describe(item, country=stamp.country, category_types=self._category_types)
            except ValueError as error:
                self._malformed(stamp, str(error))
                continue
            if item.success == 1:
                return found, stamp
            fallback = fallback or (found, stamp)
        return fallback

    def _write(self, batch: Sequence[tuple[Described, StampRow]]) -> None:
        """
        Write a batch of apps, and remember the best short records they hold.

        :param batch: Each app's rows, with the answer they came from.
        """
        for found, stamp in batch:
            self._report.add(found.findings)
            place = self._place(stamp)
            for record in found.nested:
                best = self._nested.get(record.id)
                if best is None or place < best[0]:
                    self._nested[record.id] = (place, stamp)
        self._writer.apps([(found, stamp.country) for found, stamp in batch])

    def _gaps(self) -> None:
        """
        Fill gaps with short records: an app with no row, no name, or a failed answer's row.

        A gap takes the best short record this load read, by country, then the latest. Ceiling:
        an app keeps a short record from an earlier load until a rebuild.
        """
        filled: set[int] = set()
        for chunk in itertools.batched(self._nested, LOAD_BATCH, strict=False):
            query = select(App.appid).where(
                App.appid.in_(chunk), App.name.is_not(None), App.success == 1
            )
            filled.update(self._connection.scalars(query))
        holders: dict[StampRow, set[int]] = {}
        for appid, (_, stamp) in self._nested.items():
            if appid not in filled:
                holders.setdefault(stamp, set()).add(appid)
        self._nested.clear()
        batch: list[tuple[Described, StampRow]] = []
        for stamp, appids in holders.items():
            holder = self._parse(stamp, StoreItem)
            included = holder.included_items if holder else None
            records = included.included_apps if included else ()
            for record in records:
                if record.id in appids:
                    found = describe(
                        record,
                        country=stamp.country,
                        category_types=self._category_types,
                        path=_NESTED,
                    )
                    batch.append((found, stamp))
        if batch:
            self._write(batch)
