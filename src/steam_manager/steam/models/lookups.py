"""Payload models of the lookups: the names of store categories, tags and genres."""

from pydantic import ConfigDict, RootModel

from steam_manager.steam.models.base import SteamModel

# pydantic adds its parametrized RootModel to this module's names; the docs list only these.
__all__ = [
    "AppDetailsGenresAnswer",
    "AppGenres",
    "AppGenresData",
    "Genre",
    "StoreCategoriesAnswer",
    "StoreCategoriesResponse",
    "StoreCategory",
    "TagListAnswer",
    "TagListResponse",
    "TagName",
]


class StoreCategory(SteamModel):
    """A store category, such as single-player or full controller support."""

    categoryid: int | None = None
    """Its id."""
    type: int | None = None
    """Which list holds it: 1 player modes, 2 features, 3 controller support."""
    internal_name: str | None = None
    """Its name inside Steam."""
    display_name: str | None = None
    """Its name in the language asked for."""
    image_url: str | None = None
    """Its icon."""
    computed: bool | None = None
    """Whether Steam works it out rather than the developer choosing it."""
    edit_url: str | None = None
    """Where a developer sets it."""
    edit_sort_order: int | None = None
    """Its place on that page."""
    show_in_search: bool | None = None
    """Whether the store's search can filter by it."""


class StoreCategoriesResponse(SteamModel):
    """The ``response`` of ``GetStoreCategories``."""

    categories: tuple[StoreCategory, ...] = ()
    """Every store category."""


class StoreCategoriesAnswer(SteamModel):
    """The answer of ``GetStoreCategories``."""

    response: StoreCategoriesResponse | None = None
    """The categories."""


class TagName(SteamModel):
    """A tag's name."""

    tagid: int | None = None
    """Its id."""
    name: str | None = None
    """Its name in the language asked for."""


class TagListResponse(SteamModel):
    """The ``response`` of ``GetTagList``."""

    version_hash: str | None = None
    """Identifies this version of the list."""
    tags: tuple[TagName, ...] = ()
    """Every tag."""


class TagListAnswer(SteamModel):
    """The answer of ``GetTagList``."""

    response: TagListResponse | None = None
    """The tags."""


class Genre(SteamModel):
    """A genre, as ``appdetails`` names it."""

    id: str | None = None
    """Its id, which Steam sends as text."""
    description: str | None = None
    """Its name in the language asked for."""


class AppGenresData(SteamModel):
    """What ``appdetails`` returns with ``filters=genres``."""

    genres: tuple[Genre, ...] = ()
    """The app's genres."""


class AppGenres(SteamModel):
    """One app's part of an ``appdetails`` answer."""

    success: bool | None = None
    """Whether the store knows the app."""
    data: AppGenresData | None = None
    """Its genres."""


class AppDetailsGenresAnswer(RootModel[dict[str, AppGenres]]):
    """The answer of ``appdetails``: a part per appid asked, keyed by the appid as text."""

    model_config = ConfigDict(frozen=True)
