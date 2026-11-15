"""The tables that say what an app is: its store categories, tags, genres, languages and more."""

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase
from steam_manager.db.schema.lookups import Genre, Language, StoreCategory, Tag


class AppCategory(SteamBase):
    """A store category an app is in."""

    __tablename__ = "app_category"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    categoryid: Mapped[int] = mapped_column(ForeignKey(StoreCategory.categoryid), primary_key=True)
    """The store category."""


class AppTag(SteamBase):
    """A tag players gave an app."""

    __tablename__ = "app_tag"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    tagid: Mapped[int] = mapped_column(ForeignKey(Tag.tagid), primary_key=True)
    """The tag."""
    weight: Mapped[int | None]
    """How strongly players tagged it."""


class AppGenre(SteamBase):
    """A genre the developer gave an app."""

    __tablename__ = "app_genre"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    genreid: Mapped[int] = mapped_column(ForeignKey(Genre.genreid), primary_key=True)
    """The genre."""
    position: Mapped[int]
    """Its place in Steam's order, which isn't by id."""


class AppLanguage(SteamBase):
    """A language an app supports, and how."""

    __tablename__ = "app_language"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    elanguage: Mapped[int] = mapped_column(ForeignKey(Language.elanguage), primary_key=True)
    """The language."""
    eadditionallanguage: Mapped[int] = mapped_column(primary_key=True)
    """Steam's number for a language outside its own list, or 0."""
    supported: Mapped[bool | None]
    """Whether the interface is in it."""
    full_audio: Mapped[bool | None]
    """Whether the audio is."""
    subtitles: Mapped[bool | None]
    """Whether there are subtitles in it."""


class AppContentDescriptor(SteamBase):
    """A content descriptor the developer declared for an app, such as violence."""

    __tablename__ = "app_content_descriptor"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    descriptorid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the descriptor."""


class AppInteractiveElement(SteamBase):
    """An interactive element an app has, such as in-game purchases."""

    __tablename__ = "app_interactive_element"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    element: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the element."""


class AppRatingDescriptor(SteamBase):
    """A content descriptor of an app's age rating."""

    __tablename__ = "app_rating_descriptor"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in the rating's list."""
    descriptor: Mapped[str]
    """The descriptor, as the rating states it."""


class AppDocument(SteamBase):
    """A document an app comes with, such as a manual."""

    __tablename__ = "app_document"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    document: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the document."""


class AppManufacturer(SteamBase):
    """A maker of the hardware an app is about."""

    __tablename__ = "app_manufacturer"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    name: Mapped[str]
    """The maker."""


class AppCompatibilityTest(SteamBase):
    """One result of Steam's review of an app on a device. The notebook has no such table."""

    __tablename__ = "app_compatibility_test"
    __table_args__ = (
        CheckConstraint("device IN ('steam_deck', 'steam_os', 'steam_machine', 'steam_frame')"),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    device: Mapped[str] = mapped_column(primary_key=True)
    """``steam_deck``, ``steam_os``, ``steam_machine`` or ``steam_frame``."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list for that device."""
    display_type: Mapped[int | None]
    """Steam's code for how the result reads, from unsupported to fully working."""
    loc_token: Mapped[str | None]
    """The result's text, as a localization token."""
