"""The system requirement tables: what an app needs to run on each platform."""

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase


class AppPlatformRequirement(SteamBase):
    """What an app needs from a platform as a whole."""

    __tablename__ = "app_platform_requirement"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    platform: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the platform."""
    requires_64bit: Mapped[bool | None]
    """Whether it needs a 64-bit system."""
    requires_apple_silicon: Mapped[bool | None]
    """Whether it needs an Apple silicon Mac."""
    unsupported_os_note: Mapped[int | None]
    """Steam's code for a note about unsupported systems."""


class AppSystemRequirement(SteamBase):
    """The minimum or recommended system for an app on one platform."""

    __tablename__ = "app_system_requirement"
    __table_args__ = (
        CheckConstraint("tier IN ('minimum', 'recommended')"),
        ForeignKeyConstraint(
            ["appid", "platform"],
            [AppPlatformRequirement.appid, AppPlatformRequirement.platform],
        ),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(primary_key=True)
    """The app."""
    platform: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the platform."""
    tier: Mapped[str] = mapped_column(primary_key=True)
    """``minimum`` or ``recommended``."""
    os_version: Mapped[str | None]
    """The operating system."""
    os_version_unsupported: Mapped[bool | None]
    """Whether that operating system is no longer supported."""
    processor: Mapped[str | None]
    """The processor."""
    memory_amount: Mapped[str | None]
    """How much memory, as text."""
    memory_units: Mapped[str | None]
    """Its unit."""
    graphics: Mapped[str | None]
    """The graphics card."""
    directx: Mapped[str | None]
    """The DirectX version."""
    storage_amount: Mapped[str | None]
    """How much disk space, as text."""
    storage_units: Mapped[str | None]
    """Its unit."""
    storage_hq_amount: Mapped[str | None]
    """How much disk space the high-quality files take, as text."""
    storage_hq_units: Mapped[str | None]
    """Its unit."""
    sound_card: Mapped[str | None]
    """The sound card."""
    notes: Mapped[str | None]
    """The developer's notes."""
    legacy_bbcode: Mapped[str | None]
    """The requirements as one text, in BBCode, for apps that give them so."""
    broadband: Mapped[bool | None]
    """Whether it needs a broadband connection."""
    vr_support: Mapped[str | None]
    """The VR hardware."""
