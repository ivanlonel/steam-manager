"""The app tables: one row per app, and its long texts beside it."""

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.base import STRICT, SteamBase
from steam_manager.db.schema.lookups import AgeRating, Anticheat, RatingAgency


class App(SteamBase):
    """
    An app: a game, DLC, demo, soundtrack or anything else the store sells or lists.

    Dates are ISO 8601 text, as the notebook stores them.
    """

    __tablename__ = "app"
    __table_args__ = (
        ForeignKeyConstraint(["agency", "rating"], [AgeRating.agency, AgeRating.rating]),
        STRICT,
    )

    appid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it."""
    name: Mapped[str | None]
    """Its name."""
    type: Mapped[int | None]
    """0 game, 1 demo, 2 mod, 4 DLC, 6 software, 12 playtest, among others."""
    success: Mapped[int | None]
    """Steam's result code: 1 is success, 15 mostly means not sold in the country."""
    store_url_path: Mapped[str | None]
    """Its store page."""
    store_url_path_override: Mapped[str | None]
    """A store page that replaces the usual one."""
    store_country: Mapped[str | None]
    """The country whose store described it."""
    is_listed: Mapped[bool | None]
    """
    Whether the latest listing of one of the profile's stores holds it: blank for an app
    listings don't cover (anything but games, mods and software), and before any listing.
    """
    is_free: Mapped[bool | None]
    """Whether it is free."""
    unlisted: Mapped[bool | None]
    """Whether its store page is hidden."""
    unavailable_for_country_restriction: Mapped[bool | None]
    """Whether the country can't buy it."""
    parent_appid: Mapped[int | None] = mapped_column(ForeignKey("app.appid"))
    """The app a DLC, demo or soundtrack belongs to."""
    current_players: Mapped[int | None]
    """How many people play it now."""
    steam_release_date: Mapped[str | None]
    """Its release on Steam."""
    original_release_date: Mapped[str | None]
    """Its first release anywhere."""
    original_steam_release_date: Mapped[str | None]
    """Its first release on Steam, before any re-release."""
    mac_release_date: Mapped[str | None]
    """Its release on macOS."""
    linux_release_date: Mapped[str | None]
    """Its release on Linux."""
    release_from_early_access_date: Mapped[str | None]
    """When it left Early Access."""
    release_from_early_access_style: Mapped[int | None]
    """Steam's code for how that date is shown."""
    is_coming_soon: Mapped[bool | None]
    """Whether it is still to come."""
    is_early_access: Mapped[bool | None]
    """Whether it is in Early Access."""
    is_preload: Mapped[bool | None]
    """Whether it can be preloaded. Steam sends it only when true."""
    coming_soon_display: Mapped[str | None]
    """How a future date is shown, such as only the year."""
    custom_release_date_message: Mapped[str | None]
    """The developer's text instead of a date."""
    free_weekend_start: Mapped[str | None]
    """When a free weekend starts."""
    free_weekend_end: Mapped[str | None]
    """When it ends."""
    free_weekend_text: Mapped[str | None]
    """Its announcement."""
    free_weekend_appid: Mapped[int | None] = mapped_column(ForeignKey("app.appid"))
    """The app that is free, which can be another one."""
    windows: Mapped[bool | None]
    """Whether it runs on Windows."""
    mac: Mapped[bool | None]
    """Whether it runs on macOS."""
    steamos_linux: Mapped[bool | None]
    """Whether it runs on SteamOS and Linux."""
    steam_deck_compat_category: Mapped[int | None]
    """Steam's verdict on the Steam Deck."""
    steam_os_compat_category: Mapped[int | None]
    """Steam's verdict on SteamOS."""
    steam_frame_compat_category: Mapped[int | None]
    """Steam's verdict on the Steam Frame."""
    steam_machine_compat_category: Mapped[int | None]
    """Steam's verdict on the Steam Machine."""
    vr_vrhmd: Mapped[bool | None]
    """Whether it supports a VR headset."""
    vr_vrhmd_only: Mapped[bool | None]
    """Whether it needs one."""
    vr_htc_vive: Mapped[bool | None]
    """Whether it supports the HTC Vive."""
    vr_oculus_rift: Mapped[bool | None]
    """Whether it supports the Oculus Rift."""
    vr_windows_mr: Mapped[bool | None]
    """Whether it supports Windows Mixed Reality headsets."""
    vr_valve_index: Mapped[bool | None]
    """Whether it supports the Valve Index."""
    vr_show_optional_vr_mode_notice: Mapped[bool | None]
    """Whether the store notes that VR is optional."""
    agency: Mapped[int | None] = mapped_column(ForeignKey(RatingAgency.agency))
    """The agency that rated it."""
    rating: Mapped[str | None]
    """The rating, such as ``m``."""
    agency_rating: Mapped[int | None]
    """Steam's code for the rating."""
    required_age: Mapped[int | None]
    """The age the store asks for."""
    use_age_gate: Mapped[bool | None]
    """Whether the store asks for the visitor's age."""
    banned: Mapped[bool | None]
    """Whether it is banned in the country."""
    esrb_online_music_not_rated: Mapped[bool | None]
    """Whether its online music isn't rated."""
    esrb_online_interactions_not_rated: Mapped[bool | None]
    """Whether its online interactions aren't rated."""
    rating_interactive_elements: Mapped[str | None]
    """The rating's interactive elements, as text."""
    vetted: Mapped[bool | None]
    """Whether Steam has vetted it."""
    has_community_hub: Mapped[bool | None]
    """Whether it has a community hub."""
    points_shop_eligible: Mapped[bool | None]
    """Whether it has items in the points shop."""
    controller_wizard_complete: Mapped[bool | None]
    """Whether its developer filled in the controller survey."""
    item_store_eligible: Mapped[bool | None]
    """Whether it has an item store."""
    item_store_show_featured: Mapped[bool | None]
    """Whether its item store shows featured items."""
    no_mouse_keyboard_support: Mapped[bool | None]
    """Whether it can't be played with mouse and keyboard."""
    refund_checks_ea_playtime: Mapped[bool | None]
    """Whether refunds count Early Access playtime."""
    drm_third_party_type: Mapped[str | None]
    """Its third-party DRM."""
    user_account_third_party: Mapped[str | None]
    """The third-party account it requires."""
    user_account_third_party_link_to_steam: Mapped[bool | None]
    """Whether that account links to the Steam account."""
    website: Mapped[str | None]
    """Its website."""
    stats_url: Mapped[str | None]
    """Its statistics page."""
    online_manual_url: Mapped[str | None]
    """Its online manual."""
    privacy_policy_url: Mapped[str | None]
    """Its privacy policy."""
    health_warning_url: Mapped[str | None]
    """Its health warning."""
    achievements_visible: Mapped[bool | None]
    """Whether its achievements are shown."""
    achievement_count: Mapped[int | None]
    """How many achievements it has."""
    metacritic_score: Mapped[int | None]
    """Its Metacritic score, out of 100."""
    metacritic_url: Mapped[str | None]
    """The Metacritic review page."""
    metacritic_always_show: Mapped[bool | None]
    """Whether the store always shows the score."""
    anticheat_name: Mapped[str | None] = mapped_column(ForeignKey(Anticheat.name))
    """Its anti-cheat software."""
    anticheat_kernel_mode: Mapped[bool | None]
    """Whether that software runs in the operating system's kernel."""
    anticheat_uninstall_completely: Mapped[bool | None]
    """Whether uninstalling the app removes it too."""
    anticheat_boot_protection: Mapped[bool | None]
    """Whether it starts when the computer starts."""
    anticheat_boot_protection_name: Mapped[str | None]
    """The name of that boot protection."""
    ai_generation_service_name: Mapped[str | None]
    """The generative AI service it declares using."""
    ai_generation_service_url: Mapped[str | None]
    """That service's website."""
    assets_last_modified: Mapped[int | None]
    """When its images last changed, in epoch seconds."""
    assets_appid: Mapped[int | None] = mapped_column(ForeignKey("app.appid"))
    """The app its images belong to, when another one."""
    counts_all_purchases: Mapped[bool | None]
    """Whether its review counts include people who didn't buy it on Steam."""
    dlc_formatted_total_price: Mapped[str | None]
    """What all the DLC on sale for it cost, as the store shows it in :attr:`store_country`."""


class AppText(SteamBase):
    """An app's long texts, kept apart so that queries on apps stay small."""

    __tablename__ = "app_text"
    __table_args__ = STRICT

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    short_description: Mapped[str | None]
    """Its short description."""
    capsule_headline: Mapped[str | None]
    """The headline on its capsule image."""
    full_description_bbcode: Mapped[str | None]
    """The store page's description, in BBCode."""
    legal_notice_bbcode: Mapped[str | None]
    """Its legal notice, in BBCode."""
    partner_awards_bbcode: Mapped[str | None]
    """The awards its developer lists, in BBCode."""
    content_survey_notes: Mapped[str | None]
    """The developer's notes on its content."""
    content_survey_ai_notes: Mapped[str | None]
    """The developer's notes on its use of generative AI."""
    early_access_description_bbcode: Mapped[str | None]
    """The developer's overview of its Early Access."""
    early_access_why_bbcode: Mapped[str | None]
    """Why it is in Early Access."""
    early_access_how_long_bbcode: Mapped[str | None]
    """How long it will stay there."""
    early_access_full_version_bbcode: Mapped[str | None]
    """How the full version will differ."""
    early_access_current_state_bbcode: Mapped[str | None]
    """Its current state."""
    early_access_pricing_bbcode: Mapped[str | None]
    """Whether its price will change."""
    early_access_community_bbcode: Mapped[str | None]
    """How the community takes part."""
