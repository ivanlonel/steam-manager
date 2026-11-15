"""The store page's other lists: links, licences, press quotes, sections, awards and notes."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase


class AppLink(SteamBase):
    """A link on an app's store page, such as a social network."""

    __tablename__ = "app_link"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    link_type: Mapped[int | None]
    """Steam's code for the kind of link."""
    url: Mapped[str | None]
    """The address."""
    link_text: Mapped[str | None]
    """Its text."""


class AppEula(SteamBase):
    """A licence agreement an app requires."""

    __tablename__ = "app_eula"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    name: Mapped[str | None]
    """Its name."""
    url: Mapped[str | None]
    """Where to read it."""


class AppPressReview(SteamBase):
    """A press quote on an app's store page."""

    __tablename__ = "app_press_review"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    quote: Mapped[str | None]
    """The quote."""
    score: Mapped[str | None]
    """The score the review gave, as text."""
    site: Mapped[str | None]
    """Who published it."""
    url: Mapped[str | None]
    """The review."""


class AppSection(SteamBase):
    """A section the developer added to an app's store page."""

    __tablename__ = "app_section"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place on the page."""
    label: Mapped[str | None]
    """Its heading."""
    banner: Mapped[int | None]
    """Steam's code for its banner."""
    content_bbcode: Mapped[str | None]
    """Its text, in BBCode."""


class AppSalePage(SteamBase):
    """A sale page an app appears on."""

    __tablename__ = "app_sale_page"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    clan_account_id: Mapped[int | None]
    """The group that owns the page."""
    event_gid: Mapped[str | None]
    """The page's event, an int64 Steam sends as text."""


class AppSteamAward(SteamBase):
    """A Steam Award an app was nominated for or won."""

    __tablename__ = "app_steam_award"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    voteid: Mapped[int | None]
    """The award category."""
    award_year: Mapped[int | None]
    """The year."""
    title: Mapped[str | None]
    """The category's name."""


class AppPurchaseNote(SteamBase):
    """A note shown next to an app's buy buttons."""

    __tablename__ = "app_purchase_note"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    type: Mapped[int | None]
    """Steam's code for the kind of note."""
    highlighted: Mapped[bool | None]
    """Whether it is highlighted."""
    text_bbcode: Mapped[str | None]
    """Its text, in BBCode."""


class AppOptinTag(SteamBase):
    """A value of a sign-up option on an app's store page."""

    __tablename__ = "app_optin_tag"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    optin_name: Mapped[str] = mapped_column(primary_key=True)
    """The option."""
    value: Mapped[str] = mapped_column(primary_key=True)
    """One of its values."""
