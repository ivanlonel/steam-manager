"""
The loader's progress: which archived answers, ranked for which countries, the tables reflect.

It is a Steam table itself, so a schema change drops it with the tables it describes, and the
next load fills them again from the whole archive.
"""

from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase


class LoadedAnswer(SteamBase):
    """An archived answer the Steam tables reflect, with the time it was fetched."""

    __tablename__ = "loaded_answer"
    __table_args__ = STRICT_WITHOUT_ROWID

    source: Mapped[str] = mapped_column(primary_key=True)
    """Where the answer came from, such as ``steam``."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """What it is about."""
    key: Mapped[str] = mapped_column(primary_key=True)
    """What it is about within its kind."""
    country: Mapped[str] = mapped_column(primary_key=True)
    """The store country it was asked in, or ``""``."""
    fetched_at: Mapped[str]
    """When it was fetched, as ISO 8601 text to the microsecond: an answer fetched since is new."""


class LoadedCountry(SteamBase):
    """A country the Steam tables were ranked for, in the profile's order: home first."""

    __tablename__ = "loaded_country"
    __table_args__ = STRICT_WITHOUT_ROWID

    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in the profile's list; 0 is the home country."""
    country: Mapped[str]
    """The store country."""
