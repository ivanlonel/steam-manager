"""Raw answers: what a source returned for one key, as the raw archive keeps it."""

from dataclasses import dataclass
from enum import StrEnum
lazy from datetime import datetime


class Kind(StrEnum):
    """What an answer is about; the raw archive keeps the latest answer of each kind and key."""

    STORE_ITEM = "store_item"
    """A full entry: everything the store returns for one app."""
    STORE_ITEM_LIGHT = "store_item_light"
    """A light entry: one app's name, type and review summary, from a listing."""
    LISTING = "listing"
    """The appids a store lists, with the total it reported."""
    STORE_CATEGORIES = "store_categories"
    """The names of the store categories."""
    TAGS = "tags"
    """The names of the tags."""
    APP_GENRES = "app_genres"
    """One app's genres, with their names: no endpoint lists genres by id."""
    APP_REVIEWS = "app_reviews"
    """One app's exact review totals, for one purchase type."""
    REVIEW_HISTOGRAM = "review_histogram"
    """One app's reviews over time."""
    CURRENT_PLAYERS = "current_players"
    """How many people play one app now."""
    WISHLIST = "wishlist"
    """An account's wishlist."""
    FOLLOWED_APPS = "followed_apps"
    """The apps an account follows."""


@dataclass(frozen=True, slots=True)
class Answer:
    """What a source returned for one key, in one country when the answer depends on one."""

    source: str
    """Where the answer came from, such as ``steam``."""
    kind: Kind
    """What the answer is about."""
    key: str
    """What it is about within its kind: an appid, a SteamID, a language."""
    country: str
    """The store country it was asked in, or ``""`` when the answer doesn't depend on one."""
    body: str
    """The JSON text the source sent; a batched answer's item is its own share of it."""
    fetched_at: datetime
    """When it arrived, in UTC."""
