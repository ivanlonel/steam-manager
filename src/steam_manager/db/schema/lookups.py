"""The lookup tables: the names Steam gives the ids that describe apps."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.base import STRICT, STRICT_WITHOUT_ROWID, SteamBase


class StoreCategory(SteamBase):
    """A store category, such as single-player or full controller support."""

    __tablename__ = "store_category"
    __table_args__ = STRICT

    categoryid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    type: Mapped[int | None]
    """1 for players, 2 for features, 3 for controller support, 0 for anything else."""
    internal_name: Mapped[str | None]
    """Steam's name for it in code."""
    display_name: Mapped[str | None]
    """Its name on the store."""
    image_url: Mapped[str | None]
    """Its icon."""
    computed: Mapped[bool | None]
    """Whether Steam works it out rather than the developer choosing it."""
    edit_url: Mapped[str | None]
    """The developer's page for choosing it."""
    edit_sort_order: Mapped[int | None]
    """Its place on that page."""
    show_in_search: Mapped[bool | None]
    """Whether the store's search can filter by it."""


class Tag(SteamBase):
    """A tag players give apps, such as roguelike."""

    __tablename__ = "tag"
    __table_args__ = STRICT

    tagid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    name: Mapped[str | None]
    """Its name."""


class Genre(SteamBase):
    """A genre the developer gives an app, such as strategy."""

    __tablename__ = "genre"
    __table_args__ = STRICT

    genreid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    name: Mapped[str | None]
    """Its name."""


class Language(SteamBase):
    """A language an app can support."""

    __tablename__ = "language"
    __table_args__ = STRICT

    elanguage: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    name: Mapped[str | None]
    """Its name."""


class ReviewScore(SteamBase):
    """A review score and its label, such as 9 for Overwhelmingly Positive."""

    __tablename__ = "review_score"
    __table_args__ = STRICT

    review_score: Mapped[int] = mapped_column(primary_key=True)
    """The score, from 0 to 9."""
    label: Mapped[str | None]
    """Its label. The one for 0 depends on how many reviews there are."""


class RatingAgency(SteamBase):
    """An age rating agency, such as the ESRB."""

    __tablename__ = "rating_agency"
    __table_args__ = STRICT

    agency: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    rating_type: Mapped[str | None]
    """Its name, such as ``esrb``."""


class AgeRating(SteamBase):
    """A rating an agency gives, such as the ESRB's M."""

    __tablename__ = "age_rating"
    __table_args__ = STRICT_WITHOUT_ROWID

    agency: Mapped[int] = mapped_column(ForeignKey(RatingAgency.agency), primary_key=True)
    """The agency."""
    rating: Mapped[str] = mapped_column(primary_key=True)
    """The rating."""
    image_url: Mapped[str | None]
    """Its badge."""


class Anticheat(SteamBase):
    """An anti-cheat system an app uses."""

    __tablename__ = "anticheat"
    __table_args__ = STRICT_WITHOUT_ROWID

    name: Mapped[str] = mapped_column(primary_key=True)
    """Its name."""
    name_loc: Mapped[str | None]
    """Its name as the store shows it."""
