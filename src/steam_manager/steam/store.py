"""Ask the Steam store: the catalog listing, the store items, and the names they refer to."""

import itertools
import logging
from typing import TYPE_CHECKING, Final

from pydantic import JsonValue, TypeAdapter

from steam_manager.answers import Answer, Kind
from steam_manager.steam.webapi import call, item_answer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Mapping, Sequence

    import httpx

    from steam_manager.transport import Transport

FULL_DATA_REQUEST: Final[Mapping[str, bool | int]] = {
    "include_all_purchase_options": True,
    "include_assets": True,
    "include_assets_without_overrides": True,
    "include_basic_info": True,
    "include_extra_details": True,
    "include_full_description": True,
    "include_included_items": True,
    "include_links": True,
    "include_optin_registration_tags": True,
    "include_platforms": True,
    "include_ratings": True,
    "include_release": True,
    "include_reviews": True,
    "include_screenshots": True,
    "include_supported_languages": True,
    "include_tag_count": 100,
    "include_trailers": True,
}
"""What a full entry asks for: every data flag the notebooks set."""
LIGHT_DATA_REQUEST: Final[Mapping[str, bool]] = {"include_reviews": True}
"""What a light entry asks for; the name, type and a few more fields come anyway."""

PAGE_SIZE: Final = 1000
"""Apps per listing page: ``Query`` returns 1,000 at most, whatever it is asked for."""
BATCH_SIZE: Final = 100
"""Apps per ``GetItems`` batch with the full data request; 300 fails."""
LISTING_TOLERANCE: Final = 0.001
"""How far a listing's count may stray from its total while apps appear and vanish."""
QUERY_INTERVAL: Final = 0.5
"""Seconds between listing pages, as the notebooks paused."""
ITEMS_INTERVAL: Final = 1.0
"""Seconds between ``GetItems`` batches."""

_LOGGER: Final = logging.getLogger(__name__)
_ITEMS: Final = TypeAdapter(list[dict[str, JsonValue]])
_INT: Final = TypeAdapter(int)


class ListingMismatchError(ValueError):
    """A listing's count strayed too far from the total Steam reported: the paging broke."""

    def __init__(self, country: str, unique: int, total: int) -> None:
        """
        Describe the mismatch.

        :param country: The store country listed.
        :param unique: How many different apps the pages held.
        :param total: How many Steam said there are.
        """
        super().__init__(f"the {country} listing held {unique} apps of the {total} reported")
        self.country: str = country
        """The store country listed."""
        self.unique: int = unique
        """How many different apps the pages held."""
        self.total: int = total
        """How many Steam said there are."""


def _requires(keys: Sequence[str]) -> Callable[[httpx.Response], str | None]:
    """
    Make a check that rejects a Web API answer whose response object lacks one of *keys*.

    :param keys: The keys the response object must hold.
    :return: The check.
    """

    def check(response: httpx.Response) -> str | None:
        found = response.json()["response"]
        return next((f"no {key}" for key in keys if key not in found), None)

    return check


def _store_items(response: httpx.Response) -> list[dict[str, JsonValue]]:
    """
    Read the store items of an answer that the ``store_items`` check accepted.

    :param response: The answer.
    :return: The items, as Steam sent them.
    """
    return _ITEMS.validate_python(response.json()["response"]["store_items"])


async def list_apps(
    transport: Transport, *, country: str, language: str = "english"
) -> AsyncIterator[Answer]:
    """
    List every game, mod and software a store sells, as light entries and then the listing.

    :param transport: Sends the requests.
    :param country: The store country, such as ``BR``.
    :param language: Steam's name for the language of the answers, such as ``english``.
    :yield: A light entry per app as the pages arrive, then the ``listing`` answer.
    :raise ListingMismatchError: After the last page, when the apps listed stray more than
        :data:`LISTING_TOLERANCE` from the total Steam reported.
    """
    seen: set[int] = set()
    start, total = 0, 1
    while start < total:
        response = await call(
            transport,
            "IStoreQueryService",
            "Query",
            interval=QUERY_INTERVAL,
            input_json={
                # sort 2 is ascending appid: the default sort repeats and skips apps when paged.
                "query": {
                    "start": start,
                    "count": PAGE_SIZE,
                    "sort": 2,
                    "filters": {
                        "type_filters": {
                            "include_games": True,
                            "include_mods": True,
                            "include_software": True,
                        }
                    },
                },
                "context": {"language": language, "country_code": country},
                "data_request": LIGHT_DATA_REQUEST,
            },
            check=_requires(["metadata", "store_items"]),
        )
        total = _INT.validate_python(
            response.json()["response"]["metadata"]["total_matching_records"]
        )
        for item in _store_items(response):
            appid = _INT.validate_python(item["id"])
            if appid not in seen:
                seen.add(appid)
                yield item_answer(Kind.STORE_ITEM_LIGHT, item, key=str(appid), country=country)
        start += PAGE_SIZE
    if abs(len(seen) - total) > total * LISTING_TOLERANCE:
        raise ListingMismatchError(country, len(seen), total)
    listing = {"total_matching_records": total, "appids": sorted(seen)}
    yield item_answer(Kind.LISTING, listing, key="", country=country)


async def get_items(
    transport: Transport, appids: Iterable[int], *, country: str, language: str = "english"
) -> AsyncIterator[Answer]:
    """
    Fetch full entries, 100 apps per request, keyed by each app's id.

    :param transport: Sends the requests.
    :param appids: The apps to fetch; repeats are asked once.
    :param country: The store country, such as ``BR``.
    :param language: Steam's name for the language of the answers, such as ``english``.
    :yield: A full entry per app Steam answered for, as the batches arrive. An app the country
        doesn't sell comes back with ``success`` 15, and is an answer too.
    """
    for batch in itertools.batched(sorted(set(appids)), BATCH_SIZE, strict=False):
        response = await call(
            transport,
            "IStoreBrowseService",
            "GetItems",
            interval=ITEMS_INTERVAL,
            input_json={
                "ids": [{"appid": appid} for appid in batch],
                "context": {"language": language, "country_code": country},
                "data_request": FULL_DATA_REQUEST,
            },
            check=_requires(["store_items"]),
        )
        answered: set[int] = set()
        for item in _store_items(response):
            # Never `appid`: delisted apps come back with 0 there.
            appid = _INT.validate_python(item["id"])
            answered.add(appid)
            yield item_answer(Kind.STORE_ITEM, item, key=str(appid), country=country)
        if missing := set(batch) - answered:
            _LOGGER.warning(
                "GetItems in %s left out %d of %d apps asked", country, len(missing), len(batch)
            )
