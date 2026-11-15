"""Payload models of an app's images and videos."""

from steam_manager.steam.models.base import SteamModel


class Assets(SteamModel):
    """An app's images: file names to put into ``asset_url_format``."""

    asset_url_format: str | None = None
    """The URL pattern the file names go into, as ``${FILENAME}``."""
    page_background_path: str | None = None
    """The path of the store page's background."""
    last_modified: int | None = None
    """When the images last changed, in epoch seconds."""
    community_icon: str | None = None
    """The community icon."""
    edition_comparison: str | None = None
    """The image comparing the app's editions."""
    header: str | None = None
    """The header image."""
    header_2x: str | None = None
    """The header image at twice the size."""
    hero_capsule: str | None = None
    """The hero capsule."""
    hero_capsule_2x: str | None = None
    """The hero capsule at twice the size."""
    library_capsule: str | None = None
    """The library capsule."""
    library_capsule_2x: str | None = None
    """The library capsule at twice the size."""
    library_hero: str | None = None
    """The library hero image."""
    library_hero_2x: str | None = None
    """The library hero image at twice the size."""
    main_capsule: str | None = None
    """The main capsule."""
    main_capsule_2x: str | None = None
    """The main capsule at twice the size."""
    page_background: str | None = None
    """The store page's background."""
    raw_page_background: str | None = None
    """The store page's background before the store's processing."""
    small_capsule: str | None = None
    """The small capsule."""
    small_capsule_2x: str | None = None
    """The small capsule at twice the size."""


class Screenshot(SteamModel):
    """One screenshot."""

    filename: str | None = None
    """Its file name."""
    ordinal: int | None = None
    """Its place in the store page's order."""
    alt_text: str | None = None
    """Its description for screen readers."""
    category: int | None = None
    """Steam's code for what it shows."""


class Screenshots(SteamModel):
    """An app's screenshots, split by audience."""

    all_ages_screenshots: tuple[Screenshot, ...] = ()
    """Screenshots anyone may see."""
    mature_content_screenshots: tuple[Screenshot, ...] = ()
    """Screenshots shown only to adults who asked to see them."""


class TrailerFile(SteamModel):
    """One file of a trailer."""

    filename: str | None = None
    """Its file name."""
    type: str | None = None
    """Its media type."""


class AdaptiveTrailer(SteamModel):
    """A trailer stream that adapts to the connection."""

    cdn_path: str | None = None
    """Its path on Steam's content network."""
    encoding: str | None = None
    """Its encoding."""


class Trailer(SteamModel):
    """One trailer."""

    trailer_base_id: int | None = None
    """Its id across apps: what identifies a trailer."""
    trailer_id: int | None = None
    """Another id, not unique across trailers."""
    trailer_name: str | None = None
    """Its name."""
    trailer_url_format: str | None = None
    """The URL pattern of its files."""
    trailer_category: int | None = None
    """Steam's code for its kind."""
    all_ages: bool | None = None
    """Whether anyone may see it."""
    screenshot_small: str | None = None
    """Its small preview image."""
    screenshot_medium: str | None = None
    """Its medium preview image."""
    screenshot_full: str | None = None
    """Its full-size preview image."""
    captions_manifest: str | None = None
    """The manifest of its captions."""
    microtrailer: tuple[TrailerFile, ...] = ()
    """Its short looping versions."""
    adaptive_trailers: tuple[AdaptiveTrailer, ...] = ()
    """Its adaptive streams."""


class Trailers(SteamModel):
    """An app's trailers."""

    highlights: tuple[Trailer, ...] = ()
    """The trailers the store page leads with."""
    other_trailers: tuple[Trailer, ...] = ()
    """The rest."""
