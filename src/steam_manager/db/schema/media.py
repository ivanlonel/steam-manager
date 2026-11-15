"""The media tables: an app's images, screenshots and trailers."""

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT, STRICT_WITHOUT_ROWID, SteamBase


class AppAsset(SteamBase):
    """One of an app's store images, such as its header or capsule."""

    __tablename__ = "app_asset"
    __table_args__ = (
        CheckConstraint("is_override OR base_filename IS NULL"),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """Which image it is, such as ``header``."""
    filename: Mapped[str]
    """The file the store shows."""
    is_override: Mapped[bool]
    """Whether Steam shows this file instead of :attr:`base_filename`, which can be blank."""
    base_filename: Mapped[str | None]
    """The file it replaces."""


class AppScreenshot(SteamBase):
    """A screenshot on an app's store page."""

    __tablename__ = "app_screenshot"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    is_mature: Mapped[bool] = mapped_column(primary_key=True)
    """Whether it is one of the screenshots shown only to adults."""
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    """Its place among those."""
    filename: Mapped[str]
    """Its file."""
    alt_text: Mapped[str | None]
    """Its description, for screen readers."""
    category: Mapped[int | None]
    """Steam's code for what it shows."""


class Trailer(SteamBase):
    """A trailer, which several apps can share."""

    __tablename__ = "trailer"
    __table_args__ = STRICT

    trailer_base_id: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    trailer_id: Mapped[int | None]
    """Steam's other id for it, which a few unrelated trailers share."""
    name: Mapped[str | None]
    """Its name."""
    url_format: Mapped[str | None]
    """The pattern of its files' addresses."""
    category: Mapped[int | None]
    """Steam's code for its kind."""
    all_ages: Mapped[bool | None]
    """Whether anyone may watch it."""
    screenshot_small: Mapped[str | None]
    """Its small still."""
    screenshot_medium: Mapped[str | None]
    """Its medium still."""
    screenshot_full: Mapped[str | None]
    """Its full-size still."""
    captions_manifest: Mapped[str | None]
    """Its captions."""


class AppTrailer(SteamBase):
    """A trailer on an app's store page."""

    __tablename__ = "app_trailer"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    trailer_base_id: Mapped[int] = mapped_column(
        ForeignKey(Trailer.trailer_base_id), primary_key=True
    )
    """The trailer."""
    is_highlight: Mapped[bool]
    """Whether the store page shows it first."""
    position: Mapped[int]
    """Its place among the app's trailers."""


class TrailerFile(SteamBase):
    """A video file of a trailer, per app, since apps sharing a trailer can each have their own."""

    __tablename__ = "trailer_file"
    __table_args__ = (
        CheckConstraint("kind IN ('microtrailer', 'adaptive')"),
        ForeignKeyConstraint(
            ["appid", "trailer_base_id"], [AppTrailer.appid, AppTrailer.trailer_base_id]
        ),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(primary_key=True)
    """The app."""
    trailer_base_id: Mapped[int] = mapped_column(primary_key=True)
    """The trailer."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """``microtrailer`` or ``adaptive``."""
    path: Mapped[str] = mapped_column(primary_key=True)
    """Where the file is, within the trailer's address pattern."""
    format: Mapped[str] = mapped_column(primary_key=True)
    """Its video format."""
