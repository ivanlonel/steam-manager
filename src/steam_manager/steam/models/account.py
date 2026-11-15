"""Payload models of an account's public lists: its wishlist and the apps it follows."""

from steam_manager.steam.models.base import SteamModel


class WishlistItem(SteamModel):
    """An app on a wishlist."""

    appid: int | None = None
    """The app."""
    priority: int | None = None
    """Its rank on the wishlist; 0 means unranked."""
    date_added: int | None = None
    """When it was added, in epoch seconds."""


class WishlistResponse(SteamModel):
    """The ``response`` of ``GetWishlist``."""

    items: tuple[WishlistItem, ...] = ()
    """The apps on the wishlist."""


class WishlistAnswer(SteamModel):
    """The answer of ``GetWishlist``."""

    response: WishlistResponse | None = None
    """The wishlist."""


class FollowedAppsResponse(SteamModel):
    """The ``response`` of ``GetGamesFollowed``."""

    appids: tuple[int, ...] = ()
    """The apps the account follows."""


class FollowedAppsAnswer(SteamModel):
    """The answer of ``GetGamesFollowed``."""

    response: FollowedAppsResponse | None = None
    """The followed apps."""
