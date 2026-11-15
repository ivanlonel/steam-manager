"""The Steam tables, as the notebooks have them. Importing this declares every one."""

from steam_manager.db.schema import (
    apps,
    classification,
    creators,
    lookups,
    media,
    offers,
    relations,
    requirements,
    reviews,
    store_lists,
)
from steam_manager.db.schema.base import STRICT, STRICT_WITHOUT_ROWID, Flag, SteamBase

__all__ = [
    "STRICT",
    "STRICT_WITHOUT_ROWID",
    "Flag",
    "SteamBase",
    "apps",
    "classification",
    "creators",
    "lookups",
    "media",
    "offers",
    "relations",
    "requirements",
    "reviews",
    "store_lists",
]
