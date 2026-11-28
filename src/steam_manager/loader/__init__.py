"""
The loader: the one path from archived answers to database rows (ADR 0002).

A load makes the Steam tables reflect the raw archive in one transaction. It reads every
answer's stamp, finds those fetched since the database last reflected them, and loads only
what they change: each app they describe is replaced in place, from its most complete answer,
and every other kind of answer fills the tables it owns.
"""

import itertools
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Final, cast

from pydantic import ValidationError
from sqlalchemy import (
    Column,
    MetaData,
    Table,
    Text,
    and_,
    bindparam,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.sqlite import insert as upsert

from steam_manager.answers import Kind
from steam_manager.archive import CorruptAnswerError
from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.account import FollowedApp, WishlistItem
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.lookups import StoreCategory
from steam_manager.db.schema.progress import LoadedAnswer, LoadedCountry
from steam_manager.db.schema.reviews import (
    AppReviewHistogram,
    AppReviewSummary,
    AppReviewTotal,
    ReviewHistory,
)
from steam_manager.loader import (
    account,
    details,
    lookups,
    media,
    offers,
    reviews,
    rows,
    store_item,
    write,
)
from steam_manager.loader.account import followed, wishlist
from steam_manager.loader.lookups import genres, languages, store_categories, tags
from steam_manager.loader.reviews import exact_totals, histogram, players, review_total
from steam_manager.loader.rows import Findings, MalformedAnswerError, Rows
from steam_manager.loader.store_item import describe
from steam_manager.loader.write import ForeignKeyViolationError, Writer, check_foreign_keys
from steam_manager.steam.models.account import FollowedAppsAnswer, WishlistAnswer
from steam_manager.steam.models.listing import ListingAnswer
from steam_manager.steam.models.lookups import (
    AppDetailsGenresAnswer,
    StoreCategoriesAnswer,
    TagListAnswer,
)
from steam_manager.steam.models.reviews import (
    AppReviewsAnswer,
    CurrentPlayersAnswer,
    ReviewHistogramAnswer,
)
from steam_manager.steam.models.store_item import ReviewSummary, StoreItem
from steam_manager.steam.webapi import STEAM

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence

    from pydantic import BaseModel
    from sqlalchemy import Connection, Engine, Row, Select

    from steam_manager.archive import Archive
    from steam_manager.loader.store_item import Described
    from steam_manager.steam.models.reviews import QuerySummary

# The docs list these, the submodules included; describe stays importable for the tests.
__all__ = [
    "LISTED_TYPES",
    "LOAD_BATCH",
    "ForeignKeyViolationError",
    "LoadReport",
    "Malformed",
    "account",
    "details",
    "load",
    "lookups",
    "media",
    "offers",
    "rebuild",
    "reviews",
    "rows",
    "store_item",
    "write",
]

LOAD_BATCH: Final = 500
"""Apps written at a time, inside the load's one transaction."""
STAMP_CHUNK: Final = 5000
"""Stamps copied into the database at a time."""
LISTED_TYPES: Final = frozenset({0, 2, 6})
"""The app types a listing covers: games, mods and software, what ``list_apps`` asks for."""

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
    """
    Fields Steam sent that nothing stores, by path.

    A store item's paths start at its top; every other kind's start with the kind.
    """
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
    its work too. A load that finds other countries than the tables were ranked for rebuilds
    them, in the same transaction.

    :param archive: The profile's raw archive.
    :param engine: The profile database, its Steam tables current.
    :param countries: The home country, then the fallback countries in order.
    :return: What the load did and found.
    :raise ValueError: When *countries* is empty.
    :raise RuntimeError: When SQLite kept foreign keys on, so rows couldn't load in any order.
    :raise ForeignKeyViolationError: When the load would leave a reference dangling; nothing
        is written.
    """
    return _load(archive, engine, countries, fresh=False)


def rebuild(archive: Archive, engine: Engine, *, countries: Sequence[str]) -> LoadReport:
    """
    Empty the Steam tables and load the whole archive again, in one transaction.

    :param archive: The profile's raw archive.
    :param engine: The profile database, its Steam tables current.
    :param countries: The home country, then the fallback countries in order.
    :return: What the rebuild did and found.
    :raise ValueError: When *countries* is empty.
    :raise RuntimeError: When SQLite kept foreign keys on, so rows couldn't load in any order.
    :raise ForeignKeyViolationError: When the rebuild would leave a reference dangling; nothing
        is written.
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
    :param fresh: Whether to empty the Steam tables first; a change of countries implies it.
    :return: What it did and found.
    :raise ValueError: When *countries* is empty.
    :raise RuntimeError: When SQLite kept foreign keys on, or didn't turn them back on.
    :raise ForeignKeyViolationError: When it would leave a reference dangling.
    """
    if not countries:
        message = "a load needs the home country"
        raise ValueError(message)
    report = LoadReport()
    with engine.connect() as connection:
        try:
            with connection.begin():
                _foreign_keys_off(connection)
                order = select(LoadedCountry.country).order_by(LoadedCountry.position)
                ranked = list(connection.scalars(order))
                if fresh or (ranked and ranked != list(countries)):
                    for table in reversed(SteamBase.metadata.sorted_tables):
                        connection.execute(delete(table))
                _Load(connection, archive, countries, report).run()
                connection.execute(delete(LoadedCountry))
                connection.execute(
                    insert(LoadedCountry),
                    [{"position": place, "country": name} for place, name in enumerate(countries)],
                )
        except BaseException:
            # The failure may have left a cursor on the temporary table: the connection goes,
            # and its temporary table and pragma with it.
            connection.invalidate()
            raise
        connection.exec_driver_sql("DROP TABLE temp.stamp")
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.commit()
        enforced = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
        if not enforced:  # pragma: no cover  # SQLite ignores it only inside a transaction
            message = "foreign keys didn't turn back on after the load"
            raise RuntimeError(message)
    return report


def _foreign_keys_off(connection: Connection) -> None:
    """
    Turn foreign keys off for a load, so its rows can load in any order.

    It must be the first statement of the transaction: SQLite ignores the pragma once a write
    began one.

    :param connection: The load's connection.
    :raise RuntimeError: When SQLite kept them on.
    """
    connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar():
        message = "foreign keys are still on: rows can't load in any order"
        raise RuntimeError(message)


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


def _latest(stamps: Iterable[StampRow]) -> StampRow | None:
    """
    Pick the stamp fetched last.

    :param stamps: Some stamps.
    :return: The latest, or ``None`` without any; their times are text of a fixed width.
    """
    return max(stamps, key=attrgetter("fetched_at"), default=None)


@dataclass(slots=True)
class _Known:
    """What a load has learned in its earlier steps, for its later ones."""

    category_types: dict[int, int] = field(default_factory=dict)
    """Each store category's list, by id."""
    listed: frozenset[int] | None = None
    """The apps the profile's latest listings hold, or ``None`` before any listing."""
    listing_changed: bool = False
    """Whether one of those listings changed in this load."""
    nested: dict[int, tuple[tuple[int, float], StampRow]] = field(default_factory=dict)
    """The best short record of each app, as its holder's place and stamp."""
    written: dict[int, tuple[ReviewSummary | None, bool | None]] = field(default_factory=dict)
    """Each app this load wrote, with its review summary and whether it is free."""


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
        self._known = _Known()

    def run(self) -> None:
        """
        Copy the stamps, load what changed, check every reference and record the progress.

        :raise ForeignKeyViolationError: When the load would leave a reference dangling.
        """
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
        self._lookups()
        self._listings()
        self._apps()
        self._gaps()
        if self._known.listing_changed:
            self._relist()
        self._players()
        self._totals()
        self._histograms()
        self._replace_list(Kind.WISHLIST, WishlistAnswer, wishlist, WishlistItem)
        self._replace_list(Kind.FOLLOWED_APPS, FollowedAppsAnswer, followed, FollowedApp)
        check_foreign_keys(self._connection)
        statement = upsert(_LOADED).from_select([*_IDENTITY, "fetched_at"], _changed())
        statement = statement.on_conflict_do_update(
            index_elements=_IDENTITY, set_={"fetched_at": statement.excluded.fetched_at}
        )
        self._connection.execute(statement)
        self._report.add(self._writer.findings)
        self._report.loaded.update(self._writer.loaded)
        self._report.blank_parents.update(self._writer.blank_parents)

    def _stamps(self, kind: Kind, *, changed: bool = False) -> list[StampRow]:
        """
        Read the stamps of one kind.

        :param kind: The kind.
        :param changed: Only those fetched since the database last reflected them.
        :return: The stamps.
        """
        query = (
            _changed([str(kind)])
            if changed
            else select(*_STAMP.c).where(_STAMP.c.kind == str(kind))
        )
        return list(self._connection.execute(query))

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

    def _turn[M: BaseModel](
        self, stamp: StampRow, model: type[M], turn: Callable[[M, Rows, Findings], None]
    ) -> Rows | None:
        """
        Read an archived answer and turn it into rows, reporting it when it can't be.

        :param stamp: The answer's stamp.
        :param model: Its payload model.
        :param turn: What turns the validated answer into rows.
        :return: The rows, or ``None`` when the answer was skipped.
        """
        answer = self._parse(stamp, model)
        if answer is None:
            return None
        new, findings = Rows(), Findings()
        try:
            turn(answer, new, findings)
        except MalformedAnswerError as error:
            self._malformed(stamp, str(error))
            return None
        self._report.add(findings)
        return new

    def _malformed(self, stamp: StampRow, reason: str) -> None:
        """
        Report an answer the load skips.

        :param stamp: Its stamp.
        :param reason: Why it is skipped.
        """
        self._report.malformed.append(
            Malformed(stamp.source, stamp.kind, stamp.key, stamp.country, reason)
        )

    def _lookups(self) -> None:
        """Name languages, store categories, tags and genres, from the latest lists."""
        new = Rows()
        languages(new)
        lists = (
            (
                Kind.STORE_CATEGORIES,
                partial(self._turn, model=StoreCategoriesAnswer, turn=store_categories),
            ),
            (Kind.TAGS, partial(self._turn, model=TagListAnswer, turn=tags)),
        )
        for kind, turn in lists:
            latest = _latest(self._stamps(kind))
            if latest is not None and latest in self._stamps(kind, changed=True):
                new.extend(turn(latest) or Rows())
        for stamp in self._stamps(Kind.APP_GENRES, changed=True):
            new.extend(self._turn(stamp, AppDetailsGenresAnswer, genres) or Rows())
        self._writer.write(new, home=True)
        types = select(StoreCategory.categoryid, StoreCategory.type)
        self._known.category_types = {
            categoryid: kind
            for categoryid, kind in self._connection.execute(types)
            if kind is not None
        }

    def _listings(self) -> None:
        """Read the apps the latest listing of each of the profile's countries holds."""
        stamps = self._stamps(Kind.LISTING)
        changed = set(self._stamps(Kind.LISTING, changed=True))
        listed: set[int] = set()
        found = False
        for country in self._countries:
            latest = _latest(stamp for stamp in stamps if stamp.country == country)
            if latest is None:
                continue
            found = True
            self._known.listing_changed |= latest in changed
            answer = self._parse(latest, ListingAnswer)
            if answer is None:  # an unreadable listing says nothing about what is listed
                self._known.listed, self._known.listing_changed = None, False
                return
            findings = Findings()
            # total_matching_records is what the sync checks the listing against.
            findings.rest(answer, "listing", {"total_matching_records", "appids"})
            self._report.add(findings)
            listed.update(answer.appids)
        self._known.listed = frozenset(listed) if found else None

    def _is_listed(self, appid: int, kind: int | None) -> bool | None:
        """
        Tell whether a listing of the profile's stores holds an app.

        :param appid: The app.
        :param kind: Its type, such as 0 for a game.
        :return: ``True`` when one does; ``False`` when none does and listings cover its type;
            ``None`` otherwise, and before any listing.
        """
        listed = self._known.listed
        if listed is None:
            return None
        if appid in listed:
            return True
        return False if kind in LISTED_TYPES else None

    def _relist(self) -> None:
        """Write again whether each app is listed, where a changed listing changed it."""
        changes = [
            {"b_appid": appid, "b_listed": now}
            for appid, kind, was in self._connection.execute(
                select(App.appid, App.type, App.is_listed)
            ).all()
            if (now := self._is_listed(appid, kind)) != was
        ]
        if changes:
            statement = update(App).where(App.appid == bindparam("b_appid"))
            self._connection.execute(statement.values(is_listed=bindparam("b_listed")), changes)

    def _apps(self) -> None:
        """Replace every app whose own answers changed, from its most complete answer."""
        changed = _changed(_STORE_KINDS).subquery()
        keys = sorted(set(self._connection.scalars(select(changed.c.key))))
        batch: list[tuple[Described, StampRow]] = []
        # Each chunk's stamps are read whole: no cursor stays open while the load writes.
        for chunk in itertools.batched(keys, LOAD_BATCH, strict=False):
            candidates = (
                select(*_STAMP.c)
                .where(_STAMP.c.kind.in_(_STORE_KINDS), _STAMP.c.key.in_(chunk))
                .order_by(_STAMP.c.key)
            )
            results = self._connection.execute(candidates).all()
            for _, stamps in itertools.groupby(results, key=attrgetter("key")):
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
                found = describe(
                    item, country=stamp.country, category_types=self._known.category_types
                )
            except MalformedAnswerError as error:
                self._malformed(stamp, str(error))
                continue
            if item.success == 1:
                return found, stamp
            fallback = fallback or (found, stamp)
        return fallback

    def _write(self, batch: Sequence[tuple[Described, StampRow]]) -> None:
        """
        Write a batch of apps, and remember what later steps need of them.

        :param batch: Each app's rows, with the answer they came from.
        """
        known = self._known
        for found, stamp in batch:
            item = found.item
            self._report.add(found.findings)
            found.rows.tables["app"][0]["is_listed"] = self._is_listed(item.id, item.type)
            summary = item.reviews.summary_filtered if item.reviews else None
            known.written[item.id] = (summary, item.is_free)
            place = self._place(stamp)
            for record in found.nested:
                best = known.nested.get(record.id)
                if best is None or place < best[0]:
                    known.nested[record.id] = (place, stamp)
        self._writer.apps([(found, stamp.country) for found, stamp in batch])

    def _gaps(self) -> None:
        """
        Fill gaps with short records: an app with no row, no name, or a failed answer's row.

        A gap takes the best short record this load read, by country, then the latest. Ceiling:
        an app keeps a short record from an earlier load until a rebuild.
        """
        nested = self._known.nested
        filled: set[int] = set()
        for chunk in itertools.batched(nested, LOAD_BATCH, strict=False):
            query = select(App.appid).where(
                App.appid.in_(chunk), App.name.is_not(None), App.success == 1
            )
            filled.update(self._connection.scalars(query))
        holders: dict[StampRow, set[int]] = {}
        for appid, (_, stamp) in nested.items():
            if appid not in filled:
                holders.setdefault(stamp, set()).add(appid)
        nested.clear()
        batch: list[tuple[Described, StampRow]] = []
        for stamp, appids in holders.items():
            for found in self._short_records(stamp, appids):
                batch.append((found, stamp))
                if len(batch) >= LOAD_BATCH:
                    self._write(batch)
                    batch = []
        if batch:
            self._write(batch)

    def _short_records(self, stamp: StampRow, appids: Collection[int]) -> list[Described]:
        """
        Describe some apps from the short records one full entry holds.

        :param stamp: The full entry's stamp.
        :param appids: The apps to describe.
        :return: Each app's rows; a malformed short record is reported and left out.
        """
        holder = self._parse(stamp, StoreItem)
        included = holder.included_items if holder else None
        described = []
        for record in included.included_apps if included else ():
            if record.id not in appids:
                continue
            try:
                found = describe(
                    record,
                    country=stamp.country,
                    category_types=self._known.category_types,
                    path=_NESTED,
                )
            except MalformedAnswerError as error:
                self._malformed(stamp, str(error))
                continue
            described.append(found)
        return described

    def _players(self) -> None:
        """Write how many play each app, where the figure changed or its app was written."""
        latest: dict[str, StampRow] = {}
        for stamp in sorted(self._stamps(Kind.CURRENT_PLAYERS), key=attrgetter("fetched_at")):
            latest[stamp.key] = stamp
        changed = {stamp.key for stamp in self._stamps(Kind.CURRENT_PLAYERS, changed=True)}
        figures = []
        for key, stamp in latest.items():
            if key not in changed and int(key) not in self._known.written:
                continue
            answer = self._parse(stamp, CurrentPlayersAnswer)
            if answer is not None:
                findings = Findings()
                figures.append({"appid": int(key), "current_players": players(answer, findings)})
                self._report.add(findings)
        if figures:
            statement = upsert(App)
            statement = statement.on_conflict_do_update(
                index_elements=["appid"],
                set_={"current_players": statement.excluded.current_players},
            )
            self._connection.execute(statement, figures)

    def _totals(self) -> None:
        """Work out the review totals of every app written, and of those whose counts changed."""
        changed = {
            int(stamp.key.split(":")[0]) for stamp in self._stamps(Kind.APP_REVIEWS, changed=True)
        }
        targets = sorted(changed | self._known.written.keys())
        new, findings = Rows(), Findings()
        for chunk in itertools.batched(targets, LOAD_BATCH, strict=False):
            stored = self._summaries(
                [appid for appid in chunk if appid not in self._known.written]
            )
            exact = self._exact(chunk, findings)
            for appid in chunk:
                summary, is_free = self._known.written.get(appid) or stored.get(
                    appid, (None, None)
                )
                review_total(
                    appid,
                    summary,
                    exact.get(appid, {}),
                    is_free=is_free,
                    rows=new,
                    findings=findings,
                )
        self._report.add(findings)
        self._writer.clear([AppReviewTotal], targets)
        self._writer.write(new, home=True)

    def _exact(
        self, appids: Collection[int], findings: Findings
    ) -> dict[int, dict[int, QuerySummary]]:
        """
        Read the exact review counts Steam's archived answers give some apps.

        :param appids: The apps.
        :param findings: Where fields nothing stores are counted.
        :return: Each app's totals, by purchase type.
        """
        query = select(*_STAMP.c).where(
            _STAMP.c.kind == str(Kind.APP_REVIEWS),
            _STAMP.c.source == STEAM,
            _STAMP.c.key.in_([f"{appid}:{kind}" for appid in appids for kind in (0, 1)]),
        )
        exact: dict[int, dict[int, QuerySummary]] = {}
        for stamp in self._connection.execute(query).all():
            answer = self._parse(stamp, AppReviewsAnswer)
            counts = exact_totals(answer, findings) if answer else None
            if counts is not None:
                appid, kind = map(int, stamp.key.split(":"))
                exact.setdefault(appid, {})[kind] = counts
        return exact

    def _summaries(
        self, appids: Collection[int]
    ) -> dict[int, tuple[ReviewSummary | None, bool | None]]:
        """
        Read the stored review summaries of apps this load didn't write.

        :param appids: The apps.
        :return: Each app's summary without the filtered-out reviews, and whether it is free.
        """
        query = (
            select(
                App.appid,
                App.is_free,
                AppReviewSummary.review_count,
                AppReviewSummary.percent_positive,
            )
            .outerjoin(
                AppReviewSummary,
                and_(AppReviewSummary.appid == App.appid, AppReviewSummary.scope == "filtered"),
            )
            .where(App.appid.in_(appids))
        )
        return {
            row.appid: (
                None
                if row.review_count is None
                else ReviewSummary(
                    review_count=row.review_count, percent_positive=row.percent_positive
                ),
                row.is_free,
            )
            for row in self._connection.execute(query)
        }

    def _histograms(self) -> None:
        """Replace the review histograms that changed."""
        latest: dict[str, StampRow] = {}
        changed = self._stamps(Kind.REVIEW_HISTOGRAM, changed=True)
        for stamp in sorted(changed, key=attrgetter("fetched_at")):
            latest[stamp.key] = stamp
        new = Rows()
        appids = []
        for key, stamp in latest.items():
            turn = partial(histogram, int(key))
            found = self._turn(stamp, ReviewHistogramAnswer, turn)
            if found is not None:
                appids.append(int(key))
                new.extend(found)
        self._writer.clear([ReviewHistory, AppReviewHistogram], appids)
        self._writer.write(new, home=True)

    def _replace_list[M: BaseModel](
        self,
        kind: Kind,
        model: type[M],
        turn: Callable[[M, Rows, Findings], None],
        table: type[SteamBase],
    ) -> None:
        """
        Replace an account list whole with its latest answer, when that answer changed.

        :param kind: The list's kind of answer.
        :param model: Its payload model.
        :param turn: What turns it into rows.
        :param table: The table the list fills, emptied first.
        """
        latest = _latest(self._stamps(kind))
        if latest is None or latest not in self._stamps(kind, changed=True):
            return
        new = self._turn(latest, model, turn)
        if new is not None:
            self._writer.clear([table], None)  # positions are unique: delete before inserting
            self._writer.write(new, home=True)
