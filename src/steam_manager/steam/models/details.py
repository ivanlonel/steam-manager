"""Payload models of an app's extra details: links, ratings, requirements and more."""

from steam_manager.steam.models.base import SteamModel


class LinksAndInfo(SteamModel):
    """An app's links and facts."""

    genreids: tuple[int, ...] = ()
    """Its genres, by id, in the store's order."""
    available_documents: tuple[int, ...] = ()
    """Steam's codes for the documents it has, such as a manual."""
    manufacturers: tuple[str, ...] = ()
    """The makers of hardware it is about."""
    website: str | None = None
    """Its website."""
    stats_url: str | None = None
    """Its statistics page."""
    online_manual_url: str | None = None
    """Its online manual."""
    privacy_policy_url: str | None = None
    """Its privacy policy."""
    health_warning_url: str | None = None
    """Its health warning."""
    achievements_visible: bool | None = None
    """Whether its achievements are shown."""
    achievement_count: int | None = None
    """How many achievements it has."""


class Metacritic(SteamModel):
    """An app's Metacritic score."""

    score: int | None = None
    """The score, out of 100."""
    url: str | None = None
    """The review page."""
    always_show: bool | None = None
    """Whether the store always shows it."""


class Anticheat(SteamModel):
    """The anti-cheat software an app uses."""

    name: str | None = None
    """Its name."""
    name_loc: str | None = None
    """Its name in the language asked for."""
    kernel_mode: bool | None = None
    """Whether it runs in the operating system's kernel."""
    uninstall_completely: bool | None = None
    """Whether uninstalling the app removes it too."""
    boot_protection: bool | None = None
    """Whether it starts when the computer starts."""
    boot_protection_name: str | None = None
    """The name of that boot protection."""


class AiGenerationService(SteamModel):
    """A generative AI service an app declares using."""

    name: str | None = None
    """Its name."""
    url: str | None = None
    """Its website."""


class EarlyAccess(SteamModel):
    """The developer's answers about an Early Access app, in BBCode."""

    description_bbcode: str | None = None
    """The overview."""
    why_bbcode: str | None = None
    """Why it is in Early Access."""
    how_long_bbcode: str | None = None
    """How long it will stay there."""
    full_version_bbcode: str | None = None
    """How the full version will differ."""
    current_state_bbcode: str | None = None
    """What state it is in now."""
    pricing_bbcode: str | None = None
    """Whether the price will change."""
    community_bbcode: str | None = None
    """How the community takes part."""


class Eula(SteamModel):
    """A licence agreement an app requires."""

    name: str | None = None
    """Its name."""
    url: str | None = None
    """Where to read it."""


class PressReview(SteamModel):
    """A press quote on the store page."""

    quote: str | None = None
    """The quote."""
    score: str | None = None
    """The score given, as text."""
    site: str | None = None
    """The publication."""
    url: str | None = None
    """The review."""


class Section(SteamModel):
    """A section of the store page the developer wrote."""

    label: str | None = None
    """Its heading."""
    banner: int | None = None
    """Steam's code for its banner."""
    content_bbcode: str | None = None
    """Its text, in BBCode."""


class SalePage(SteamModel):
    """A sale page the app appears on."""

    clan_account_id: int | None = None
    """The group that owns the page."""
    event_gid: str | None = None
    """
    The page's event, as the text Steam sends.

    A uint64, kept as text since it can exceed SQLite's INTEGER.
    """


class AwardLocalization(SteamModel):
    """An award's name in the language asked for."""

    title: str | None = None
    """The award's name."""


class SteamAward(SteamModel):
    """A Steam Award the app won or was nominated for."""

    voteid: int | None = None
    """The award category."""
    award_year: int | None = None
    """The year."""
    localization: AwardLocalization | None = None
    """Its name."""


class LocalizedString(SteamModel):
    """A text in one language."""

    language: int | None = None
    """Steam's ELanguage number."""
    localized_string: str | None = None
    """The text."""


class MilestoneDate(SteamModel):
    """When a season pass milestone ships, as the store shows it."""

    coming_soon_display_type: str | None = None
    """How the date is shown."""
    rtime: int | None = None
    """The date, in epoch seconds."""


class Milestone(SteamModel):
    """A part of a season pass."""

    milestone_id: int | None = None
    """Its id."""
    appid: int | None = None
    """The app it delivers, once it ships."""
    coming_soon_appid: int | None = None
    """The app it will deliver."""
    event_gid: str | None = None
    """
    Its announcement event, as the text Steam sends.

    A uint64, kept as text since it can exceed SQLite's INTEGER.
    """
    rtime_complete: int | None = None
    """When it shipped, in epoch seconds."""
    shipped: bool | None = None
    """Whether it has shipped."""
    dates: tuple[MilestoneDate, ...] = ()
    """When it ships."""
    title: tuple[LocalizedString, ...] = ()
    """Its name, per language."""
    milestone_desc: tuple[LocalizedString, ...] = ()
    """Its description, per language."""
    backfilled_release: bool | None = None
    """Whether it shipped as a backfilled release (seen first on 2026-11-28)."""


class SeasonPass(SteamModel):
    """An app's season pass."""

    appid: int | None = None
    """The season pass's own app."""
    milestones: tuple[Milestone, ...] = ()
    """What it delivers."""


class Amount(SteamModel):
    """A quantity with its unit, such as 8 GB."""

    amount: str | None = None
    """The number, as text."""
    units: str | None = None
    """The unit."""


class Requirements(SteamModel):
    """The minimum or recommended requirements on one platform."""

    os_version: str | None = None
    """The operating system."""
    os_version_unsupported: bool | None = None
    """Whether that operating system is no longer supported."""
    processor: str | None = None
    """The processor."""
    memory: Amount | None = None
    """The memory."""
    graphics: str | None = None
    """The graphics card."""
    directx: str | None = None
    """The DirectX version."""
    storage: Amount | None = None
    """The disk space."""
    storage_hq: Amount | None = None
    """The disk space with high-quality assets."""
    sound_card: str | None = None
    """The sound card."""
    notes: str | None = None
    """Anything else."""
    legacy_bbcode: str | None = None
    """The requirements as the developer wrote them, in BBCode."""
    broadband: bool | None = None
    """Whether a broadband connection is needed."""
    vr_support: str | None = None
    """The VR hardware."""


class PlatformRequirements(SteamModel):
    """An app's requirements on one platform."""

    platform: int | None = None
    """Steam's code for the platform."""
    requires_64bit: bool | None = None
    """Whether it needs a 64-bit system."""
    requires_apple_silicon: bool | None = None
    """Whether it needs an Apple silicon Mac."""
    unsupported_os_note: int | bool | None = None
    """Steam's code for a note about unsupported systems."""
    minimum: Requirements | None = None
    """The minimum requirements."""
    recommended: Requirements | None = None
    """The recommended requirements."""


class SystemRequirements(SteamModel):
    """An app's requirements on each platform."""

    platforms: tuple[PlatformRequirements, ...] = ()
    """One entry per platform."""


class HardwareTest(SteamModel):
    """One result of Steam's compatibility review on a device."""

    display_type: int | None = None
    """Steam's code for how the result reads, from unsupported to fully working."""
    loc_token: str | None = None
    """The result's text, as a localization token."""


class HardwareCompatibility(SteamModel):
    """The results of Steam's compatibility reviews, per device (seen first on 2026-11-15)."""

    steam_deck_tests: tuple[HardwareTest, ...] = ()
    """On the Steam Deck."""
    steam_os_tests: tuple[HardwareTest, ...] = ()
    """On SteamOS."""
    steam_machine_tests: tuple[HardwareTest, ...] = ()
    """On the Steam Machine."""
    steam_frame_tests: tuple[HardwareTest, ...] = ()
    """On the Steam Frame."""


class DlcOffer(SteamModel):
    """A DLC the store page offers next to the app."""

    appid: int | None = None
    """The DLC."""
    packageid: int | None = None
    """The package it is sold in."""
    highlight_reason: int | None = None
    """Steam's code for why it is highlighted."""
    content_descriptorids: tuple[int, ...] = ()
    """Its content descriptors, such as violence."""


class DlcForPurchase(SteamModel):
    """The DLC on sale for an app (seen first on 2026-11-15)."""

    dlc: tuple[DlcOffer, ...] = ()
    """The DLC."""
    dlc_count: int | None = None
    """How many there are."""
    formatted_total_price: str | None = None
    """What they all cost, as the store shows it."""


class Track(SteamModel):
    """A track of a soundtrack (seen first on 2026-11-28)."""

    disc_number: int | None = None
    """The disc it is on."""
    track_number: int | None = None
    """Its number on that disc."""
    name: str | None = None
    """Its title."""
    other_name: str | None = None
    """Its title in a second language."""
    duration_seconds: int | None = None
    """How long it lasts, in seconds."""


class MusicAlbum(SteamModel):
    """A soundtrack's credits and tracks, the credits as free text (seen first on 2026-11-28)."""

    artist: str | None = None
    """Its artist."""
    composer: str | None = None
    """Its composer."""
    label: str | None = None
    """Its record label."""
    other_credits: str | None = None
    """Everyone else it credits."""
    tracks: tuple[Track, ...] = ()
    """Its tracks, in the store's order."""


class ExtraDetails(SteamModel):
    """Everything ``include_extra_details`` adds to a store item."""

    vetted: bool | None = None
    """Whether Steam has vetted the app."""
    has_community_hub: bool | None = None
    """Whether it has a community hub."""
    points_shop_eligible: bool | None = None
    """Whether it has items in the points shop."""
    controller_wizard_complete: bool | None = None
    """Whether its developer filled in the controller survey."""
    item_store_eligible: bool | None = None
    """Whether it has an item store."""
    item_store_show_featured: bool | None = None
    """Whether its item store shows featured items."""
    no_mouse_keyboard_support: bool | None = None
    """Whether it can't be played with mouse and keyboard."""
    refund_checks_ea_playtime: bool | None = None
    """Whether refunds count Early Access playtime."""
    user_account_third_party_link_to_steam: bool | None = None
    """Whether its third-party account links to the Steam account."""
    drm_third_party_type: str | None = None
    """Its third-party DRM."""
    user_account_third_party: str | None = None
    """The third-party account it requires."""
    legal_notice_bbcode: str | None = None
    """Its legal notice, in BBCode."""
    partner_awards_bbcode: str | None = None
    """The awards its developer lists, in BBCode."""
    content_survey_notes: str | None = None
    """The developer's notes on its content."""
    content_survey_ai_notes: str | None = None
    """The developer's notes on its use of generative AI."""
    interactive_elements: tuple[int, ...] = ()
    """Steam's codes for its interactive elements, such as purchases."""
    links_and_info: LinksAndInfo | None = None
    """Its links and facts."""
    metacritic: Metacritic | None = None
    """Its Metacritic score."""
    anticheat: Anticheat | None = None
    """Its anti-cheat software."""
    ai_generation_service: AiGenerationService | None = None
    """The generative AI service it uses."""
    early_access: EarlyAccess | None = None
    """The developer's answers about Early Access."""
    eula: tuple[Eula, ...] = ()
    """The licence agreements it requires."""
    press_review: tuple[PressReview, ...] = ()
    """Press quotes."""
    section: tuple[Section, ...] = ()
    """Store page sections."""
    sale_pages: tuple[SalePage, ...] = ()
    """Sale pages it appears on."""
    steam_award: tuple[SteamAward, ...] = ()
    """Steam Awards."""
    season_pass: SeasonPass | None = None
    """Its season pass."""
    system_requirements: SystemRequirements | None = None
    """Its requirements."""
    hardware_compatibility: HardwareCompatibility | None = None
    """Steam's compatibility reviews, per device."""
    dlc_for_purchase: DlcForPurchase | None = None
    """The DLC on sale for it."""
    music_album: MusicAlbum | None = None
    """A soundtrack's credits and tracks."""
