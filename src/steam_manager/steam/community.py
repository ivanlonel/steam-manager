"""Ask the Steam community: who a profile is, and the public lists of an account."""

import re
from typing import TYPE_CHECKING, Final

from steam_manager.answers import Answer, Kind
from steam_manager.steam.webapi import call, response_answer

if TYPE_CHECKING:
    from steam_manager.transport import Transport

COMMUNITY: Final = "https://steamcommunity.com"
"""The host of community profiles."""
PROFILE_INTERVAL: Final = 1.0
"""Seconds before a profile lookup, done once per profile."""
LIST_INTERVAL: Final = 1.0
"""Seconds before an account's list, asked once per sync."""

INDIVIDUAL_BASE: Final = 76561197960265728
"""The SteamID64 of account 0 of an individual: every person's ID adds a 32-bit account id."""

_PROFILE_URL: Final = re.compile(
    r"(?:https?://)?(?:www\.)?steamcommunity\.com/(profiles|id)/([A-Za-z0-9_-]+)(?:[/?#].*)?",
    re.IGNORECASE,
)
# Read with a regular expression, not an XML parser: the answer comes from the network.
_STEAMID_ELEMENT: Final = re.compile(r"<steamID64>(\d{17})</steamID64>")


def _steamid(text: str) -> int | None:
    """
    Read *text* as an individual's SteamID64.

    :param text: Candidate digits.
    :return: The SteamID64, or ``None`` when *text* isn't one.
    """
    if not (len(text) == 17 and text.isascii() and text.isdigit()):  # noqa: PLR2004  # SteamID64s have 17 digits
        return None
    steamid = int(text)
    return steamid if INDIVIDUAL_BASE < steamid < INDIVIDUAL_BASE + 2**32 else None


class ProfileNotFoundError(ValueError):
    """The text given names no Steam profile."""

    def __init__(self, profile: str) -> None:
        """
        Name the text that matched no profile.

        :param profile: The SteamID64 or profile URL given.
        """
        # The message never shows a query string or fragment: a pasted URL can carry a token.
        shown = re.split(r"[?#]", profile, maxsplit=1)[0]
        super().__init__(f"no Steam profile matches {shown!r}")
        self.profile: str = profile
        """The SteamID64 or profile URL given."""


async def resolve_steamid(transport: Transport, profile: str) -> int:
    """
    Find the SteamID64 of a profile, given that ID or the profile's URL.

    :param transport: Sends the lookup a vanity URL needs.
    :param profile: A SteamID64, a ``steamcommunity.com/profiles/<id>`` URL, or a
        ``steamcommunity.com/id/<name>`` vanity URL.
    :return: The SteamID64.
    :raise ProfileNotFoundError: When *profile* is none of those, or no profile has the vanity.
    """
    text = profile.strip()
    if (steamid := _steamid(text)) is not None:
        return steamid
    url = _PROFILE_URL.fullmatch(text)
    if url is None:
        raise ProfileNotFoundError(profile)
    kind, name = url.groups()
    if kind.lower() == "profiles":
        if (steamid := _steamid(name)) is not None:
            return steamid
        raise ProfileNotFoundError(profile)
    response = await transport.get(
        f"{COMMUNITY}/id/{name}", interval=PROFILE_INTERVAL, params={"xml": "1"}
    )
    # A vanity nobody has comes back as a 200 holding an <error> element.
    found = _STEAMID_ELEMENT.search(response.text)
    if found is None or (steamid := _steamid(found.group(1))) is None:
        raise ProfileNotFoundError(profile)
    return steamid


async def wishlist(transport: Transport, steamid: int) -> Answer:
    """
    Fetch an account's wishlist, which needs no login when the profile is public.

    :param transport: Sends the request.
    :param steamid: The account's SteamID64.
    :return: The answer, keyed by *steamid*.
    """
    response = await call(
        transport,
        "IWishlistService",
        "GetWishlist",
        interval=LIST_INTERVAL,
        params={"steamid": str(steamid)},
    )
    return response_answer(Kind.WISHLIST, response, key=str(steamid))


async def followed_apps(transport: Transport, steamid: int) -> Answer:
    """
    Fetch the apps an account follows, which needs no login.

    :param transport: Sends the request.
    :param steamid: The account's SteamID64.
    :return: The answer, keyed by *steamid*.
    """
    response = await call(
        transport,
        "IStoreService",
        "GetGamesFollowed",
        interval=LIST_INTERVAL,
        params={"steamid": str(steamid)},
    )
    return response_answer(Kind.FOLLOWED_APPS, response, key=str(steamid))
