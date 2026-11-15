"""Tests for the community endpoints: profiles, and an account's public lists."""

import asyncio

import pytest

from steam_manager.answers import Kind
from steam_manager.steam.community import (
    ProfileNotFoundError,
    followed_apps,
    resolve_steamid,
    wishlist,
)
from tests._fakes import FakeClock, recorder, transport_for

GABEN = 76561197960287930
"""A public SteamID64, of Steam's best-known account."""
PROFILE_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<profile><steamID64>{GABEN}</steamID64><steamID><![CDATA[Rabscuttle]]></steamID></profile>"""
"""What steamcommunity.com sends for a vanity URL's ``?xml=1``."""
MISSING_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<response><error><![CDATA[The specified profile could not be found.]]></error></response>"""
"""What it sends, with a 200, for a vanity nobody has."""


@pytest.mark.parametrize("profile", [str(GABEN), f"  {GABEN}\n"])
def test_a_steamid_is_returned_without_a_request(profile: str) -> None:
    """A SteamID64 needs no lookup."""
    handler, requests = recorder(text=PROFILE_XML)

    found = asyncio.run(resolve_steamid(transport_for(handler, FakeClock()), profile))

    assert found == GABEN
    assert not requests


@pytest.mark.parametrize(
    "profile",
    [
        f"https://steamcommunity.com/profiles/{GABEN}",
        f"https://steamcommunity.com/profiles/{GABEN}/",
        f"steamcommunity.com/profiles/{GABEN}/games/?tab=all",
        f"http://www.steamcommunity.com/profiles/{GABEN}",
    ],
)
def test_a_profiles_url_is_read_without_a_request(profile: str) -> None:
    """A /profiles/ URL holds the SteamID64 itself."""
    handler, requests = recorder(text=PROFILE_XML)

    found = asyncio.run(resolve_steamid(transport_for(handler, FakeClock()), profile))

    assert found == GABEN
    assert not requests


@pytest.mark.parametrize(
    "profile",
    [
        "https://steamcommunity.com/id/gabelogannewell",
        "https://steamcommunity.com/id/gabelogannewell/",
        "steamcommunity.com/id/gabelogannewell",
    ],
)
def test_a_vanity_url_is_resolved_through_the_xml_profile(profile: str) -> None:
    """A vanity URL is looked up in the profile's XML, which needs no key."""
    handler, requests = recorder(text=PROFILE_XML)

    found = asyncio.run(resolve_steamid(transport_for(handler, FakeClock()), profile))

    assert found == GABEN
    assert requests[0].url.host == "steamcommunity.com"
    assert requests[0].url.path == "/id/gabelogannewell"
    assert dict(requests[0].url.params) == {"xml": "1"}


def test_a_missing_vanity_raises_profile_not_found() -> None:
    """steamcommunity.com answers a missing vanity with a 200 and an error element."""
    handler, _ = recorder(text=MISSING_XML)
    profile = "https://steamcommunity.com/id/nobody-has-this"

    with pytest.raises(ProfileNotFoundError, match="nobody-has-this") as caught:
        asyncio.run(resolve_steamid(transport_for(handler, FakeClock()), profile))

    assert caught.value.profile == profile


@pytest.mark.parametrize(
    "profile",
    [
        "",
        "123",
        "76561190000000000",  # 17 digits, but not in the range of individual accounts
        "765611979602879300",  # 18 digits
        "https://example.com/id/gabelogannewell",
        "https://steamcommunity.com/profiles/123",
        "https://steamcommunity.com/groups/valve",
        "https://steamcommunity.com/id/",
        "https://steamcommunity.com/id/name with spaces",
    ],
)
def test_anything_else_is_not_a_profile(profile: str) -> None:
    """Input that names no profile is refused before any request."""
    handler, requests = recorder(text=PROFILE_XML)

    with pytest.raises(ProfileNotFoundError):
        asyncio.run(resolve_steamid(transport_for(handler, FakeClock()), profile))

    assert not requests


def test_the_wishlist_is_asked_by_steamid() -> None:
    """GetWishlist needs no login for a public profile."""
    handler, requests = recorder(json={"response": {"items": []}})

    answer = asyncio.run(wishlist(transport_for(handler, FakeClock()), GABEN))

    assert requests[0].url.path == "/IWishlistService/GetWishlist/v1/"
    assert dict(requests[0].url.params) == {"steamid": str(GABEN)}
    assert (answer.kind, answer.key, answer.country) == (Kind.WISHLIST, str(GABEN), "")


def test_followed_apps_are_asked_by_steamid() -> None:
    """GetGamesFollowed needs no login either."""
    handler, requests = recorder(json={"response": {"appids": [620]}})

    answer = asyncio.run(followed_apps(transport_for(handler, FakeClock()), GABEN))

    assert requests[0].url.path == "/IStoreService/GetGamesFollowed/v1/"
    assert dict(requests[0].url.params) == {"steamid": str(GABEN)}
    assert (answer.kind, answer.key) == (Kind.FOLLOWED_APPS, str(GABEN))
