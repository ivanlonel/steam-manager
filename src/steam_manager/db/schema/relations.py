"""The tables that link apps: demos, DLC, playtests, and what a season pass delivers."""

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase
from steam_manager.db.schema.lookups import Language


class AppRelated(SteamBase):
    """Another app an app points at, such as its demo, its parent or its season pass."""

    __tablename__ = "app_related"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('demo', 'standalone_demo', 'playtest', 'dlc_parent', 'included_app',"
            " 'related_f2p', 'season_pass', 'engine')"
        ),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """
    How the other app relates to it, such as ``demo`` or ``dlc_parent``.

    ``engine`` is an app that provides its engine, which can be the app itself.
    """
    related_appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The other app."""
    label: Mapped[str | None]
    """A demo's label on the store page."""
    show_above_purchase: Mapped[bool | None]
    """Whether a demo is shown above the buy options."""
    is_open: Mapped[bool | None]
    """Whether anyone may join a playtest."""
    header_text: Mapped[str | None]
    """A free-to-play version's heading on the store page."""
    description_text: Mapped[str | None]
    """Its description there."""


class SeasonPassMilestone(SteamBase):
    """A part of a season pass."""

    __tablename__ = "season_pass_milestone"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app the season pass belongs to."""
    milestone_id: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for the part."""
    milestone_appid: Mapped[int | None] = mapped_column(ForeignKey(App.appid))
    """The app it delivers, once it ships."""
    coming_soon_appid: Mapped[int | None] = mapped_column(ForeignKey(App.appid))
    """The app it will deliver."""
    event_gid: Mapped[str | None]
    """Its announcement event, a uint64 Steam sends as text."""
    rtime_complete: Mapped[str | None]
    """When it shipped."""
    shipped: Mapped[bool | None]
    """Whether it has shipped."""
    backfilled_release: Mapped[bool | None]
    """Whether it shipped as a backfilled release."""


class SeasonPassMilestoneDate(SteamBase):
    """When a part of a season pass ships, as the store shows it."""

    __tablename__ = "season_pass_milestone_date"
    __table_args__ = (
        ForeignKeyConstraint(
            ["appid", "milestone_id"],
            [SeasonPassMilestone.appid, SeasonPassMilestone.milestone_id],
        ),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(primary_key=True)
    """The app the season pass belongs to."""
    milestone_id: Mapped[int] = mapped_column(primary_key=True)
    """The part."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list of dates."""
    coming_soon_display_type: Mapped[str | None]
    """How the date is shown, such as only the quarter."""
    rtime: Mapped[str | None]
    """The date."""


class SeasonPassMilestoneText(SteamBase):
    """The name or the description of a part of a season pass, in one language."""

    __tablename__ = "season_pass_milestone_text"
    __table_args__ = (
        CheckConstraint("kind IN ('title', 'description')"),
        ForeignKeyConstraint(
            ["appid", "milestone_id"],
            [SeasonPassMilestone.appid, SeasonPassMilestone.milestone_id],
        ),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(primary_key=True)
    """The app the season pass belongs to."""
    milestone_id: Mapped[int] = mapped_column(primary_key=True)
    """The part."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """``title`` or ``description``."""
    language: Mapped[int] = mapped_column(ForeignKey(Language.elanguage), primary_key=True)
    """The language."""
    localized_string: Mapped[str | None]
    """The text."""


class AppDlc(SteamBase):
    """A DLC the store page offers next to an app, in the store's order."""

    __tablename__ = "app_dlc"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    dlc_appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The DLC."""
    position: Mapped[int]
    """Its place in the store's list."""
    packageid: Mapped[int | None]
    """The package it is sold in, which isn't always among the app's offers."""
    highlight_reason: Mapped[int | None]
    """Steam's code for why the store highlights it."""
