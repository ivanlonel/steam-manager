"""
The account's public lists: its wishlist and the apps it follows.

They come from archived answers like the rest of the Steam tables, so they are dropped,
recreated and rebuilt with them.
"""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT, SteamBase


class WishlistItem(SteamBase):
    """An app on the account's wishlist."""

    __tablename__ = "wishlist_item"
    __table_args__ = STRICT

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(unique=True)
    """Its place in the order Steam answered with."""
    priority: Mapped[int | None]
    """Its rank on the wishlist, or blank when unranked."""
    date_added: Mapped[str | None]
    """When it was added."""


class FollowedApp(SteamBase):
    """An app the account follows."""

    __tablename__ = "followed_app"
    __table_args__ = STRICT

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
