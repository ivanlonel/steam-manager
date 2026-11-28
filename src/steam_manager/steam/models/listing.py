"""The payload model of a listing: the appids one store lists, as ``list_apps`` archives them."""

from steam_manager.steam.models.base import SteamModel


class ListingAnswer(SteamModel):
    """A ``listing`` answer, built from the pages of ``Query`` rather than sent whole by Steam."""

    total_matching_records: int | None = None
    """How many apps Steam said the store lists."""
    appids: tuple[int, ...] = ()
    """The apps the pages held, in ascending order."""
