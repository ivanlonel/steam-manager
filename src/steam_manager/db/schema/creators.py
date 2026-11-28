"""
The tables that say who made an app.

The name an app credits isn't always its creator's own name, and many credits have no creator
page, so a credit is a name with an optional creator.
"""

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT, STRICT_WITHOUT_ROWID, SteamBase


class Creator(SteamBase):
    """A creator page on the store: a developer's, a publisher's or a franchise's."""

    __tablename__ = "creator"
    __table_args__ = STRICT

    creator_id: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    name: Mapped[str | None]
    """Its name."""
    store_url_path: Mapped[str | None]
    """Its store page."""
    store_url_slug: Mapped[str | None]
    """The end of that path."""
    game_count: Mapped[int | None]
    """How many apps it has."""


class Credit(SteamBase):
    """A name apps credit, tied to a creator page when Steam names one."""

    __tablename__ = "credit"
    __table_args__ = (
        UniqueConstraint("name", "creator_id"),
        # UNIQUE counts no two NULLs as equal, so the credits without a creator need their own.
        Index(
            "credit_without_creator", "name", unique=True, sqlite_where=text("creator_id IS NULL")
        ),
        STRICT,
    )

    credit_id: Mapped[int] = mapped_column(primary_key=True)
    """This project's id for it."""
    name: Mapped[str]
    """The name, as apps show it."""
    creator_id: Mapped[int | None] = mapped_column(ForeignKey(Creator.creator_id))
    """The creator page, when there is one."""


class AppCredit(SteamBase):
    """A credit on an app, in the order the store lists it."""

    __tablename__ = "app_credit"
    __table_args__ = (
        CheckConstraint("role IN ('developer', 'publisher', 'franchise')"),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    role: Mapped[str] = mapped_column(primary_key=True)
    """``developer``, ``publisher`` or ``franchise``."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place among the app's credits in that role."""
    credit_id: Mapped[int] = mapped_column(ForeignKey(Credit.credit_id))
    """The credit."""


class AppFeaturedCreator(SteamBase):
    """A creator home an app's store page features, in the store's order."""

    __tablename__ = "app_featured_creator"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in the store's list."""
    creator_id: Mapped[int] = mapped_column(ForeignKey(Creator.creator_id))
    """The creator."""
