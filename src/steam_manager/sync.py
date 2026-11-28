"""
The sync: fetch what is stale, archive it as it arrives, and load it after each step.

Steps run in a fixed order, since each reads what the earlier ones loaded. A request that fails
skips its unit of work and is reported; a host that keeps failing stops the sync, which then
loads what it archived and returns. A sync run again continues from what the archive holds.
"""

import asyncio
import itertools
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Final

from sqlalchemy import select, union

from steam_manager.answers import Kind
from steam_manager.db.schema.account import FollowedApp, WishlistItem
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.classification import AppGenre
from steam_manager.db.schema.lookups import Genre
from steam_manager.db.schema.relations import AppDlc, AppRelated
from steam_manager.db.schema.reviews import AppReviewSummary
from steam_manager.loader import LoadReport, load
from steam_manager.loader.reviews import EXACT_UP_TO
from steam_manager.steam.community import followed_apps, wishlist
from steam_manager.steam.models.listing import ListingAnswer
from steam_manager.steam.reviews import exact_review_answers, review_histogram
from steam_manager.steam.store import (
    API_LANGUAGES,
    BATCH_SIZE,
    PAGE_SIZE,
    ListingMismatchError,
    app_genres,
    current_players,
    get_items,
    list_apps,
    store_categories,
    tag_list,
)
from steam_manager.steam.webapi import STEAM
from steam_manager.transport import FailureStreakError, RequestFailedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Iterable
    from collections.abc import Set as AbstractSet
    from datetime import timedelta

    from sqlalchemy import CompoundSelect, Select

    from steam_manager.answers import Answer
    from steam_manager.archive import Archive
    from steam_manager.profiles import OpenProfile
    from steam_manager.transport import Transport

# The docs list only these; the names imported from SQLAlchemy stay out of them.
__all__ = ["ARCHIVE_CHUNK", "Step", "SyncReport", "fetch_full_catalog", "stale", "sync"]

ARCHIVE_CHUNK: Final = 100
"""Answers asked one app at a time that are archived together, so a stop loses few."""

_ACCOUNT: Final = union(select(WishlistItem.appid), select(FollowedApp.appid))
# The apps the account apps point at, one level deep: an included app comes with its short
# record, and bundles are out. The parent game sits on the app's own row.
_REFERENCES: Final[CompoundSelect[int]] = union(
    select(AppRelated.related_appid).where(
        AppRelated.appid.in_(_ACCOUNT), AppRelated.kind != "included_app"
    ),
    select(AppDlc.dlc_appid).where(AppDlc.appid.in_(_ACCOUNT)),
    select(App.parent_appid).where(App.appid.in_(_ACCOUNT), App.parent_appid.is_not(None)),
)


class Step(StrEnum):
    """A part of the sync, named as the command line names it."""

    LOOKUPS = "lookups"
    """The names of the store categories and the tags."""
    WISHLIST = "wishlist"
    """The account's wishlist."""
    FOLLOWED = "followed"
    """The apps the account follows."""
    CATALOG = "catalog"
    """Each country's listing, and a light entry per app listed."""
    APPS = "apps"
    """Full entries for the account apps and the apps they reference, and their figures."""
    REVIEWS = "reviews"
    """Exact review totals and review histograms."""


@dataclass
class SyncReport:
    """What a sync fetched, what failed, and what its loads found."""

    fetched: Counter[str] = field(default_factory=Counter)
    """Answers archived, by kind."""
    failed: list[str] = field(default_factory=list)
    """Requests that failed after their retries, each named by its endpoint alone."""
    load: LoadReport = field(default_factory=LoadReport)
    """What every load of the sync did and found, added up."""
    stopped: str | None = None
    """Why the sync stopped before its end, when a host kept failing."""


def _now() -> datetime:
    """
    Tell the time.

    :return: Now, in UTC.
    """
    return datetime.now(UTC)


def stale(
    archive: Archive,
    kind: Kind,
    keys: Iterable[str],
    *,
    country: str,
    max_age: timedelta,
    now: datetime,
) -> list[str]:
    """
    Pick the keys whose answer is missing, or as old as *max_age* or older.

    :param archive: The raw archive.
    :param kind: The answers' kind.
    :param keys: The keys to look at.
    :param country: The store country the answers were asked in, or ``""``.
    :param max_age: How old an answer may be and still be fresh, exclusive.
    :param now: The time to measure ages from.
    :return: The stale keys, in the order given.
    """
    fetched = archive.fetched_at(STEAM, kind, country=country)
    return [key for key in keys if key not in fetched or now - fetched[key] >= max_age]


def _merge(into: LoadReport, found: LoadReport) -> None:
    """
    Add what one load did and found to a sync's report.

    :param into: The sync's report of its loads.
    :param found: What one load did and found.
    """
    into.unknown.update(found.unknown)
    into.mismatches.update(found.mismatches)
    into.malformed.extend(found.malformed)
    into.loaded.update(found.loaded)
    into.blank_parents.update(found.blank_parents)


class _Sync:
    """One run of the sync: what it archived since its last load, and its report."""

    def __init__(
        self,
        profile: OpenProfile,
        transport: Transport,
        *,
        force: bool,
        now: Callable[[], datetime],
    ) -> None:
        """
        Prepare a run.

        :param profile: The open profile.
        :param transport: Sends the requests.
        :param force: Whether to fetch fresh answers too.
        :param now: Tells the time staleness is measured from.
        """
        self._profile = profile
        self._transport = transport
        self._force = force
        self._now = now
        self._pending: list[Answer] = []
        self._unloaded = False
        self.report: SyncReport = SyncReport()
        """What the run fetched, what failed, and what its loads found."""

    async def run(self, steps: Iterable[Callable[[], Awaitable[None]]]) -> SyncReport:
        """
        Run steps in order, loading after each, until they end or a host keeps failing.

        :param steps: The steps.
        :return: The report.
        """
        try:
            for step in steps:
                await step()
                await self._load()
        except FailureStreakError as error:
            self.report.stopped = str(error)
            await self._load()
        finally:
            self._flush()
        return self.report

    def _stale(self, kind: Kind, keys: Iterable[str], country: str = "") -> list[str]:
        """
        Pick the keys this run fetches: the stale ones, or all of them when forced.

        :param kind: The answers' kind.
        :param keys: The keys to look at.
        :param country: The store country, or ``""``.
        :return: The keys to fetch, in the order given.
        """
        if self._force:
            return list(keys)
        return stale(
            self._profile.archive,
            kind,
            keys,
            country=country,
            max_age=self._profile.settings.max_age(kind),
            now=self._now(),
        )

    def _flush(self) -> None:
        """Archive the answers waiting, in one transaction."""
        if self._pending:
            self._profile.archive.put(self._pending)
            self.report.fetched.update(str(answer.kind) for answer in self._pending)
            self._pending.clear()
            self._unloaded = True

    def _add(self, answers: Iterable[Answer], *, chunk: int = ARCHIVE_CHUNK) -> None:
        """
        Queue answers for the archive, archiving the queue once it holds a chunk.

        :param answers: The answers.
        :param chunk: How many answers to archive at a time.
        """
        self._pending.extend(answers)
        if len(self._pending) >= chunk:
            self._flush()

    def _failed(self, error: Exception) -> None:
        """
        Report a unit of work that failed; the step goes on without it.

        :param error: Why it failed; its message names the endpoint, never the full URL.
        """
        self.report.failed.append(str(error))

    async def _load(self) -> None:
        """Load what was archived since the last load, in a thread: SQLite's writer blocks."""
        self._flush()
        if not self._unloaded:
            return
        self._unloaded = False
        found = await asyncio.to_thread(
            load,
            self._profile.archive,
            self._profile.engine,
            countries=self._profile.settings.countries,
        )
        _merge(self.report.load, found)

    async def _one(self, request: Awaitable[Answer]) -> None:
        """
        Archive the answer of one request, or report its failure.

        :param request: The request.
        """
        try:
            self._add([await request])
        except RequestFailedError as error:
            self._failed(error)

    async def lookups(self) -> None:
        """Fetch the names of the store categories and of the tags, in the profile's language."""
        language = self._profile.settings.language
        elanguage = API_LANGUAGES[language]
        if self._stale(Kind.STORE_CATEGORIES, [str(elanguage)]):
            await self._one(store_categories(self._transport, elanguage=elanguage))
        if self._stale(Kind.TAGS, [language]):
            await self._one(tag_list(self._transport, language=language))

    async def wishlist(self) -> None:
        """Fetch the account's wishlist."""
        steamid = self._profile.settings.steamid
        if self._stale(Kind.WISHLIST, [str(steamid)]):
            await self._one(wishlist(self._transport, steamid))

    async def followed(self) -> None:
        """Fetch the apps the account follows."""
        steamid = self._profile.settings.steamid
        if self._stale(Kind.FOLLOWED_APPS, [str(steamid)]):
            await self._one(followed_apps(self._transport, steamid))

    async def catalog(self) -> None:
        """List each country whose listing is stale, the home country first."""
        settings = self._profile.settings
        for place, country in enumerate(settings.countries):
            if self._stale(Kind.LISTING, [""], country):
                await self._list(country, self._listed(settings.countries[:place]))

    def _listed(self, countries: Iterable[str]) -> set[int]:
        """
        Read the apps the latest archived listings of some countries hold.

        :param countries: The countries.
        :return: The appids.
        """
        found: set[int] = set()
        for country in countries:
            answer = self._profile.archive.get(STEAM, Kind.LISTING, "", country)
            if answer is not None:
                found.update(ListingAnswer.model_validate_json(answer.body).appids)
        return found

    async def _list(self, country: str, earlier: Collection[int]) -> None:
        """
        List one country, archiving its light entries a page at a time, then its listing.

        :param country: The country.
        :param earlier: The apps earlier countries list, whose light entries this one skips.
        """
        language = self._profile.settings.language
        try:
            async for answer in list_apps(self._transport, country=country, language=language):
                if answer.kind is Kind.LISTING or int(answer.key) not in earlier:
                    self._add([answer], chunk=PAGE_SIZE)
        except (RequestFailedError, ListingMismatchError) as error:
            self._failed(error)
        self._flush()

    def _appids(self, query: Select[int] | CompoundSelect[int]) -> set[int]:
        """
        Read appids from the database.

        :param query: A query of one column of appids.
        :return: The appids.
        """
        with self._profile.engine.connect() as connection:
            return set(connection.scalars(query))

    async def apps(self) -> None:
        """Fetch full entries for the account apps and what they point at, and their figures."""
        account = self._appids(_ACCOUNT)
        await self._entries(account)
        await self._entries(self._appids(_REFERENCES) - account)
        for key in self._stale(Kind.CURRENT_PLAYERS, map(str, sorted(account))):
            await self._one(current_players(self._transport, int(key)))
        await self._genres()

    async def _entries(self, appids: AbstractSet[int]) -> None:
        """
        Fetch the stale full entries of some apps, a country at a time, loading after each.

        The home country is asked for every app, and each fallback for the apps no earlier
        country sells, as the loaded rows tell.

        :param appids: The apps.
        """
        settings = self._profile.settings
        for place, country in enumerate(settings.countries):
            wanted = appids
            if place:
                sold = select(App.appid).where(
                    App.success == 1, App.store_country.in_(settings.countries[:place])
                )
                wanted = appids - self._appids(sold)
            keys = self._stale(Kind.STORE_ITEM, map(str, sorted(wanted)), country)
            for batch in itertools.batched(map(int, keys), BATCH_SIZE, strict=False):
                try:
                    self._add(
                        [
                            answer
                            async for answer in get_items(
                                self._transport, batch, country=country, language=settings.language
                            )
                        ]
                    )
                except RequestFailedError as error:
                    self._failed(error)
            await self._load()

    async def _genres(self) -> None:
        """Ask one app per genre without a name, skipping genres an app asked before has."""
        query = (
            select(AppGenre.genreid, AppGenre.appid)
            .join(Genre, Genre.genreid == AppGenre.genreid)
            .where(Genre.name.is_(None))
            .order_by(AppGenre.genreid, AppGenre.appid)
        )
        holders: dict[int, list[int]] = {}
        held: dict[int, set[int]] = {}
        with self._profile.engine.connect() as connection:
            for genreid, appid in connection.execute(query):
                holders.setdefault(genreid, []).append(appid)
                held.setdefault(appid, set()).add(genreid)
        covered: set[int] = set()
        for genreid, appids in holders.items():
            if genreid not in covered:
                covered |= held[appids[0]]
                language = self._profile.settings.language
                await self._one(app_genres(self._transport, appids[0], language=language))

    async def reviews(self, *, catalog: bool) -> None:
        """
        Fetch exact review totals where Steam's percentage can't give them, then histograms.

        :param catalog: Whether every app above :data:`~steam_manager.loader.reviews.EXACT_UP_TO`
            reviews gets exact totals, not only the account apps; the most reviewed go first.
        """
        query = (
            select(App.appid, App.is_free, AppReviewSummary.review_count)
            .join(AppReviewSummary, AppReviewSummary.appid == App.appid)
            .where(
                AppReviewSummary.scope == "filtered", AppReviewSummary.review_count > EXACT_UP_TO
            )
            .order_by(AppReviewSummary.review_count.desc(), App.appid)
        )
        if not catalog:
            query = query.where(App.appid.in_(_ACCOUNT))
        with self._profile.engine.connect() as connection:
            # Keyed by the purchase type whose totals match the app's count: 1 if free, else 0.
            targets = {
                f"{row.appid}:{1 if row.is_free else 0}": row for row in connection.execute(query)
            }
        for key in self._stale(Kind.APP_REVIEWS, targets):
            row = targets[key]
            try:
                self._add(
                    await exact_review_answers(
                        self._transport,
                        row.appid,
                        is_free=bool(row.is_free),
                        review_count=row.review_count,
                    )
                )
            except RequestFailedError as error:
                self._failed(error)
        language = self._profile.settings.language
        for key in self._stale(Kind.REVIEW_HISTOGRAM, map(str, sorted(self._appids(_ACCOUNT)))):
            await self._one(review_histogram(self._transport, int(key), language=language))

    async def full_catalog(self) -> None:
        """Fetch a full entry for every app a store of the profile lists."""
        await self._entries(self._appids(select(App.appid).where(App.is_listed.is_(True))))


async def sync(  # the command line's options, each a keyword
    profile: OpenProfile,
    transport: Transport,
    *,
    steps: Collection[Step] = tuple(Step),
    force: bool = False,
    catalog_reviews: bool = False,
    now: Callable[[], datetime] = _now,
) -> SyncReport:
    """
    Fetch what is stale, archiving it as it arrives and loading it after each step.

    :param profile: The open profile.
    :param transport: Sends the requests.
    :param steps: The steps to run; they run in :class:`Step`'s order, whatever order this is.
    :param force: Whether to fetch fresh answers too.
    :param catalog_reviews: Whether to fetch exact review totals for every app with enough
        reviews, not only for the account apps.
    :param now: Tells the time staleness is measured from.
    :return: What the sync fetched, what failed, what its loads found, and why it stopped.
    """
    run = _Sync(profile, transport, force=force, now=now)
    actions: dict[Step, Callable[[], Awaitable[None]]] = {
        Step.LOOKUPS: run.lookups,
        Step.WISHLIST: run.wishlist,
        Step.FOLLOWED: run.followed,
        Step.CATALOG: run.catalog,
        Step.APPS: run.apps,
        Step.REVIEWS: partial(run.reviews, catalog=catalog_reviews),
    }
    return await run.run(action for step, action in actions.items() if step in steps)


async def fetch_full_catalog(
    profile: OpenProfile,
    transport: Transport,
    *,
    force: bool = False,
    now: Callable[[], datetime] = _now,
) -> SyncReport:
    """
    Fetch a full entry for every app a store of the profile lists, as the catalog last showed.

    It is resumable: a run stopped halfway fetches, when run again, only what is still stale.

    :param profile: The open profile, its catalog listed.
    :param transport: Sends the requests.
    :param force: Whether to fetch fresh full entries too.
    :param now: Tells the time staleness is measured from.
    :return: What it fetched, what failed, what its loads found, and why it stopped.
    """
    run = _Sync(profile, transport, force=force, now=now)
    return await run.run([run.full_catalog])
