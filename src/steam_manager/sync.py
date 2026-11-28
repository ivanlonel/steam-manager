"""
The sync: fetch what is stale, archive it as it arrives, and load it after each step.

Steps run in a fixed order, since each reads what the earlier ones loaded. A request that fails
skips its unit of work and is reported; a host that keeps failing stops the sync, which then
loads what it archived and returns. A sync run again continues from what the archive holds.
"""

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from steam_manager.answers import Kind
from steam_manager.loader import LoadReport, load
from steam_manager.steam.community import followed_apps, wishlist
from steam_manager.steam.store import API_LANGUAGES, store_categories, tag_list
from steam_manager.steam.webapi import STEAM
from steam_manager.transport import FailureStreakError, RequestFailedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Iterable
    from datetime import timedelta

    from steam_manager.answers import Answer
    from steam_manager.archive import Archive
    from steam_manager.profiles import OpenProfile
    from steam_manager.transport import Transport

ARCHIVE_CHUNK: Final = 100
"""Answers asked one app at a time that are archived together, so a stop loses few."""


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

    def _add(self, answers: Iterable[Answer]) -> None:
        """
        Queue answers for the archive, archiving the queue once it holds a chunk.

        :param answers: The answers.
        """
        self._pending.extend(answers)
        if len(self._pending) >= ARCHIVE_CHUNK:
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
    del catalog_reviews
    run = _Sync(profile, transport, force=force, now=now)
    actions = {Step.LOOKUPS: run.lookups, Step.WISHLIST: run.wishlist, Step.FOLLOWED: run.followed}
    return await run.run(action for step, action in actions.items() if step in steps)
