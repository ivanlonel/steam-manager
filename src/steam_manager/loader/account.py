"""Turn an account's public lists, its wishlist and the apps it follows, into rows."""

from typing import TYPE_CHECKING

from steam_manager.db.schema.account import FollowedApp, WishlistItem
from steam_manager.loader.rows import iso

if TYPE_CHECKING:
    from steam_manager.loader.rows import Findings, Rows
    from steam_manager.steam.models.account import FollowedAppsAnswer, WishlistAnswer


def wishlist(answer: WishlistAnswer, rows: Rows, findings: Findings) -> None:
    """
    Turn the ``GetWishlist`` answer into a row per app, in Steam's order.

    :param answer: The answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    response = answer.response
    findings.rest(answer, "wishlist", {"response"})
    findings.rest(response, "wishlist.response", {"items"})
    # Positions count from 1, as the notebook's line numbers did.
    for position, item in enumerate(response.items if response else (), 1):
        findings.rest(item, "wishlist.response.items[]", {"appid", "priority", "date_added"})
        rows.add(
            WishlistItem,
            appid=item.appid,
            position=position,
            priority=item.priority or None,  # 0 means unranked
            date_added=iso(item.date_added),
        )


def followed(answer: FollowedAppsAnswer, rows: Rows, findings: Findings) -> None:
    """
    Turn the ``GetGamesFollowed`` answer into a row per app.

    :param answer: The answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    response = answer.response
    findings.rest(answer, "followed_apps", {"response"})
    findings.rest(response, "followed_apps.response", {"appids"})
    for appid in response.appids if response else ():
        rows.add(FollowedApp, appid=appid)
