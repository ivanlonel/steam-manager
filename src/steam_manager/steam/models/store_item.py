"""The payload model of a store item: everything ``GetItems`` and ``Query`` say about an app."""

from steam_manager.steam.models.base import SteamModel
from steam_manager.steam.models.details import ExtraDetails
from steam_manager.steam.models.media import Assets, Screenshots, Trailers
from steam_manager.steam.models.offers import PurchaseOption


class Categories(SteamModel):
    """An app's store categories, by id, in the three lists Steam keeps them in."""

    supported_player_categoryids: tuple[int, ...] = ()
    """Player modes, such as single-player."""
    feature_categoryids: tuple[int, ...] = ()
    """Features, such as achievements."""
    controller_categoryids: tuple[int, ...] = ()
    """Controller support."""


class Tag(SteamModel):
    """A tag on an app, with the weight of the votes for it."""

    tagid: int | None = None
    """The tag."""
    weight: int | None = None
    """How strongly users tagged it."""


class SupportedLanguage(SteamModel):
    """A language an app supports, and how."""

    elanguage: int | None = None
    """Steam's ELanguage number."""
    eadditionallanguage: int | None = None
    """Steam's number for a language outside ELanguage."""
    supported: bool | None = None
    """Whether the interface is translated."""
    full_audio: bool | None = None
    """Whether the speech is."""
    subtitles: bool | None = None
    """Whether it has subtitles."""


class ReviewSummary(SteamModel):
    """A review summary, as the store page shows it."""

    review_count: int | None = None
    """How many reviews count."""
    percent_positive: int | None = None
    """The share of positive ones, truncated to a whole percent."""
    review_score: int | None = None
    """Steam's score, from 0 to 9."""
    review_score_label: str | None = None
    """The score's label, such as "Very Positive"."""


class Reviews(SteamModel):
    """An app's review summaries."""

    summary_filtered: ReviewSummary | None = None
    """Without the reviews Steam filters out, such as off-topic review bombs."""
    summary_language_specific: ReviewSummary | None = None
    """In the language asked for."""
    summary_unfiltered: ReviewSummary | None = None
    """Every review."""
    counts_all_purchases: bool | None = None
    """Whether the counts include reviews by people who didn't buy it on Steam (seen first on
    2026-11-15)."""


class Credit(SteamModel):
    """A developer, publisher or franchise of an app."""

    name: str | None = None
    """Its name."""
    creator_clan_account_id: int | None = None
    """Its creator page, or 0."""


class BasicInfo(SteamModel):
    """An app's description and credits."""

    short_description: str | None = None
    """The short description."""
    capsule_headline: str | None = None
    """The headline shown on its capsule."""
    developers: tuple[Credit, ...] = ()
    """Its developers."""
    publishers: tuple[Credit, ...] = ()
    """Its publishers."""
    franchises: tuple[Credit, ...] = ()
    """Its franchises."""
    featured_creator_home_clan_account_ids: tuple[int, ...] = ()
    """The creator pages its store page features (seen first on 2026-11-28)."""
    first_franchise_clan_account_id: int | None = None
    """The creator page of its first franchise (seen first on 2026-11-28)."""


class Release(SteamModel):
    """When an app came out, or will. Dates are epoch seconds, and 0 means none."""

    steam_release_date: int | None = None
    """Its release on Steam."""
    original_release_date: int | None = None
    """Its first release anywhere."""
    original_steam_release_date: int | None = None
    """Its first release on Steam, before any re-release."""
    mac_release_date: int | None = None
    """Its release on macOS."""
    linux_release_date: int | None = None
    """Its release on Linux."""
    release_from_early_access_date: int | None = None
    """When it left Early Access."""
    release_from_early_access_style: int | None = None
    """Steam's code for how that date is shown."""
    coming_soon_display: str | None = None
    """How a future date is shown, such as only the year."""
    custom_release_date_message: str | None = None
    """The developer's text instead of a date."""
    is_preload: bool | None = None
    """Whether it can be preloaded."""
    is_early_access: bool | None = None
    """Whether it is in Early Access."""
    is_coming_soon: bool | None = None
    """Whether it is still to come."""


class FreeWeekend(SteamModel):
    """A free weekend running on an app."""

    start_time: int | None = None
    """When it starts, in epoch seconds."""
    end_time: int | None = None
    """When it ends, in epoch seconds."""
    text: str | None = None
    """Its announcement."""
    appid: int | None = None
    """The app that is free."""


class VrSupport(SteamModel):
    """The VR hardware an app supports."""

    vrhmd: bool | None = None
    """Whether it supports a VR headset."""
    vrhmd_only: bool | None = None
    """Whether it needs one."""
    htc_vive: bool | None = None
    """The HTC Vive."""
    oculus_rift: bool | None = None
    """The Oculus Rift."""
    windows_mr: bool | None = None
    """Windows Mixed Reality headsets."""
    valve_index: bool | None = None
    """The Valve Index."""
    show_optional_vr_mode_notice: bool | None = None
    """Whether the store notes that VR is optional."""


class Platforms(SteamModel):
    """The systems an app runs on."""

    windows: bool | None = None
    """Windows."""
    mac: bool | None = None
    """macOS."""
    steamos_linux: bool | None = None
    """SteamOS and Linux."""
    steam_deck_compat_category: int | None = None
    """Steam's verdict on the Steam Deck."""
    steam_machine_compat_category: int | None = None
    """Steam's verdict on the Steam Machine."""
    steam_os_compat_category: int | None = None
    """Steam's verdict on SteamOS."""
    steam_frame_compat_category: int | None = None
    """Steam's verdict on the Steam Frame."""
    vr_support: VrSupport | None = None
    """The VR hardware it supports."""


class GameRating(SteamModel):
    """An app's age rating."""

    type: str | None = None
    """The rating system, such as ``esrb``."""
    agency: int | None = None
    """Steam's code for the rating agency."""
    rating: str | None = None
    """The rating, such as ``m``."""
    agency_rating: int | None = None
    """Steam's code for the rating."""
    required_age: int | None = None
    """The age the store asks for."""
    use_age_gate: bool | None = None
    """Whether the store asks for the visitor's age."""
    banned: bool | None = None
    """Whether the app is banned in the country asked."""
    esrb_online_music_not_rated: bool | None = None
    """Whether its online music isn't rated."""
    esrb_online_interactions_not_rated: bool | None = None
    """Whether its online interactions aren't rated."""
    interactive_elements: str | None = None
    """The rating's interactive elements, as text."""
    descriptors: tuple[str, ...] = ()
    """The rating's content descriptors."""
    image_url: str | None = None
    """The rating's image."""
    survey_interactive_elements: tuple[int, ...] = ()
    """Steam's codes for the interactive elements the developer declared."""
    content_survey_notes: str | None = None
    """The developer's notes on its content."""


class Link(SteamModel):
    """A link on the store page, such as a social network."""

    link_type: int | None = None
    """Steam's code for the kind of link."""
    url: str | None = None
    """The address."""
    text: str | None = None
    """Its text."""


class PurchaseNote(SteamModel):
    """A note shown next to the buy buttons."""

    type: int | None = None
    """Steam's code for the kind of note."""
    highlighted: bool | None = None
    """Whether it is highlighted."""
    text_bbcode: str | None = None
    """Its text, in BBCode."""


class OptinTag(SteamModel):
    """A sign-up option on the store page."""

    optin_name: str | None = None
    """Its name."""
    values: tuple[str, ...] = ()
    """Its values."""


class PackageGroup(SteamModel):
    """A group of buy options on the store page."""

    name: str | None = None
    """Its name."""
    display_type: int | None = None
    """Steam's code for how it is shown."""
    heading: str | None = None
    """Its heading."""
    dropdown_title: str | None = None
    """The title of its drop-down."""
    dropdown_description_bbcode: str | None = None
    """The description of its drop-down, in BBCode."""


class IncludedOffer(SteamModel):
    """A package or bundle that holds an app, in its short form."""

    id: int | None = None
    """The package or bundle id."""
    item_type: int | None = None
    """1 for a package, 2 for a bundle."""
    visible: bool | None = None
    """Whether the store shows it."""
    success: int | None = None
    """Steam's result code; 1 is success."""
    name: str | None = None
    """Its name."""
    store_url_path: str | None = None
    """Its store page."""
    store_url_slug: str | None = None
    """The end of that path."""
    appid: int | None = None
    """An app it is tied to."""
    type: int | None = None
    """Steam's code for its kind."""
    purchase_description_bbcode: str | None = None
    """Its description next to the buy button, in BBCode."""
    unvailable_for_country_restriction: bool | None = None
    """Whether the country can't buy it (Steam's spelling)."""
    included_types: tuple[int, ...] = ()
    """The kinds of the apps it holds."""
    included_appids: tuple[int, ...] = ()
    """The apps it holds."""
    categories: Categories | None = None
    """Its store categories."""
    content_descriptorids: tuple[int, ...] = ()
    """Its content descriptors."""
    best_purchase_option: PurchaseOption | None = None
    """The cheapest way to buy it."""
    self_purchase_option: PurchaseOption | None = None
    """Buying it on its own."""


class IncludedCreator(SteamModel):
    """A creator page tied to an app."""

    id: int | None = None
    """Its id."""
    item_type: int | None = None
    """5 for a creator."""
    visible: bool | None = None
    """Whether the store shows it."""
    success: int | None = None
    """Steam's result code; 1 is success."""
    name: str | None = None
    """Its name."""
    store_url_path: str | None = None
    """Its store page."""
    store_url_slug: str | None = None
    """The end of that path."""
    game_count: int | None = None
    """How many apps it has."""


class IncludedItems(SteamModel):
    """The short records of what a store item refers to."""

    included_apps: tuple[StoreItem, ...] = ()
    """Apps, such as the DLC's parent, in the store item's own short form."""
    included_packages: tuple[IncludedOffer, ...] = ()
    """Packages."""
    included_bundles: tuple[IncludedOffer, ...] = ()
    """Bundles."""
    included_creators: tuple[IncludedCreator, ...] = ()
    """Creator pages."""


class Demo(SteamModel):
    """A demo of an app."""

    appid: int | None = None
    """The demo."""
    label: str | None = None
    """Its label on the store page."""
    show_above_purchase: bool | None = None
    """Whether it is shown above the buy options."""


class Playtest(SteamModel):
    """A playtest of an app."""

    appid: int | None = None
    """The playtest."""
    is_open: bool | None = None
    """Whether anyone may join."""


class RelatedF2p(SteamModel):
    """A free-to-play version of an app."""

    appid: int | None = None
    """The free app."""
    header_text: str | None = None
    """Its heading on the store page."""
    description_text: str | None = None
    """Its description there."""


class RelatedItems(SteamModel):
    """The apps an app is related to."""

    parent_appid: int | None = None
    """The app a DLC, demo or soundtrack belongs to."""
    demos: tuple[Demo, ...] = ()
    """Its demos."""
    standalone_demos: tuple[Demo, ...] = ()
    """Its demos with their own store pages."""
    demo_appid: tuple[int, ...] = ()
    """Its demos, by appid only."""
    standalone_demo_appid: tuple[int, ...] = ()
    """Its standalone demos, by appid only."""
    playtests: tuple[Playtest, ...] = ()
    """Its playtests."""
    dlc_parent_appids: tuple[int, ...] = ()
    """The apps a DLC extends."""
    related_f2p: RelatedF2p | None = None
    """A free-to-play version."""
    provides_engine_appid: tuple[int, ...] = ()
    """The apps that provide its engine, itself included (seen first on 2026-11-28)."""


class StoreItem(SteamModel):
    """Everything the store says about one app: a full entry, a light one, or a short record."""

    id: int
    """The appid. Always present, unlike :attr:`appid`."""
    appid: int | None = None
    """The appid, or 0 on delisted apps: use :attr:`id`."""
    item_type: int | None = None
    """0 for an app."""
    visible: bool | None = None
    """Whether the store shows it."""
    success: int | None = None
    """Steam's result code: 1 is success, 15 mostly means not sold in the country."""
    name: str | None = None
    """Its name."""
    type: int | None = None
    """0 game, 1 demo, 2 mod, 4 DLC, 6 software, 12 playtest, among others."""
    store_url_path: str | None = None
    """Its store page."""
    store_url_slug: str | None = None
    """The end of that path."""
    store_url_path_override: str | None = None
    """A store page that replaces the usual one."""
    is_free: bool | None = None
    """Whether it is free; absent unless true, and absent on delisted apps."""
    unlisted: bool | None = None
    """Whether its store page is hidden."""
    unvailable_for_country_restriction: bool | None = None
    """Whether the country can't buy it (Steam's spelling)."""
    is_early_access: bool | None = None
    """Whether it is in Early Access."""
    is_coming_soon: bool | None = None
    """Whether it is still to come."""
    full_description_bbcode: str | None = None
    """The store page's description, in BBCode."""
    tagids: tuple[int, ...] = ()
    """Its tags, by id."""
    content_descriptorids: tuple[int, ...] = ()
    """Its content descriptors, such as violence."""
    categories: Categories | None = None
    """Its store categories."""
    tags: tuple[Tag, ...] = ()
    """Its tags, with weights."""
    supported_languages: tuple[SupportedLanguage, ...] = ()
    """The languages it supports."""
    reviews: Reviews | None = None
    """Its review summaries."""
    basic_info: BasicInfo | None = None
    """Its description and credits."""
    release: Release | None = None
    """Its release dates."""
    free_weekend: FreeWeekend | None = None
    """A free weekend running on it."""
    platforms: Platforms | None = None
    """The systems it runs on."""
    game_rating: GameRating | None = None
    """Its age rating."""
    links: tuple[Link, ...] = ()
    """The links on its store page."""
    purchase_notes: tuple[PurchaseNote, ...] = ()
    """The notes by its buy buttons."""
    optin_registration_tags: tuple[OptinTag, ...] = ()
    """Its sign-up options."""
    package_groups: tuple[PackageGroup, ...] = ()
    """The groups of its buy options."""
    purchase_options: tuple[PurchaseOption, ...] = ()
    """Every way to buy it."""
    best_purchase_option: PurchaseOption | None = None
    """The cheapest way to buy it."""
    included_items: IncludedItems | None = None
    """The short records of what it refers to."""
    related_items: RelatedItems | None = None
    """The apps it is related to."""
    assets: Assets | None = None
    """Its images, as the store shows them."""
    assets_without_overrides: Assets | None = None
    """Its images, before any seasonal override."""
    screenshots: Screenshots | None = None
    """Its screenshots."""
    trailers: Trailers | None = None
    """Its trailers."""
    extra_details: ExtraDetails | None = None
    """Its extra details."""
