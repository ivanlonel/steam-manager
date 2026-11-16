"""Sample rows the store reports' tests share: a full Brazilian entry and a US-only app."""

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from tests.steam_manager.db.reports._parity import Sample

_RELATED: Final = (621, 622, 623, 624, 625, 626)
"""Apps Portal 2 points at: a demo, a standalone demo, a playtest, its DLC parent, a free
version and its season pass."""

LOOKUPS: Final[Sample] = {
    "review_score": [
        {"review_score": 0},
        {"review_score": 8, "label": "Very Positive"},
        {"review_score": 9, "label": "Overwhelmingly Positive"},
    ],
    "rating_agency": [{"agency": 1, "rating_type": "esrb"}],
    "age_rating": [{"agency": 1, "rating": "e10"}],
    "anticheat": [{"name": "VAC", "name_loc": "Valve Anti-Cheat"}],
    "store_category": [
        {"categoryid": 2, "internal_name": "SinglePlayer"},
        {"categoryid": 28, "internal_name": "FullControllerSupport"},
    ],
    "genre": [{"genreid": 1, "name": "Action"}, {"genreid": 25, "name": "Adventure"}],
}
"""The lookups the store columns name."""

_PORTAL_2: Final = {
    "appid": 620,
    "name": "Portal 2",
    "type": 0,
    "success": 1,
    "store_url_path": "app/620/Portal_2/",
    "store_url_path_override": "app/620/Portal_2_Override/",
    "store_country": "BR",
    "is_listed": 1,
    "is_free": 0,
    "unlisted": 0,
    "unavailable_for_country_restriction": 0,
    "parent_appid": 624,
    "current_players": 4321,
    "steam_release_date": "2011-04-18 17:00:00",
    "original_release_date": "2011-04-19 00:00:00",
    "original_steam_release_date": "2011-04-18 00:00:00",
    "mac_release_date": "2011-04-20 00:00:00",
    "linux_release_date": "2014-03-01 00:00:00",
    "release_from_early_access_date": "2012-01-01 00:00:00",
    "release_from_early_access_style": 2,
    "is_coming_soon": 0,
    "is_early_access": 0,
    "is_preload": 1,
    "coming_soon_display": "date_full",
    "custom_release_date_message": "Out now",
    "free_weekend_start": "2026-11-20 18:00:00",
    "free_weekend_end": "2026-11-23 18:00:00",
    "free_weekend_text": "Play free this weekend",
    "free_weekend_appid": 620,
    "windows": 1,
    "mac": 0,
    "steamos_linux": 1,
    "steam_deck_compat_category": 3,
    "steam_os_compat_category": 4,
    "steam_frame_compat_category": 1,
    "steam_machine_compat_category": 2,
    "vr_vrhmd": 0,
    "vr_vrhmd_only": 1,
    "vr_htc_vive": 0,
    "vr_oculus_rift": 1,
    "vr_windows_mr": 0,
    "vr_valve_index": 1,
    "vr_show_optional_vr_mode_notice": 0,
    "agency": 1,
    "rating": "e10",
    "agency_rating": 17,
    "required_age": 0,
    "use_age_gate": 1,
    "banned": 0,
    "esrb_online_music_not_rated": 1,
    "esrb_online_interactions_not_rated": 0,
    "rating_interactive_elements": "Users Interact",
    "vetted": 1,
    "has_community_hub": 0,
    "points_shop_eligible": 1,
    "controller_wizard_complete": 0,
    "item_store_eligible": 1,
    "item_store_show_featured": 0,
    "no_mouse_keyboard_support": 0,
    "refund_checks_ea_playtime": 1,
    "drm_third_party_type": "Third-party DRM",
    "user_account_third_party": "Third-party account",
    "user_account_third_party_link_to_steam": 1,
    "website": "https://www.thinkwithportals.com/",
    "stats_url": "https://example.org/stats",
    "online_manual_url": "https://example.org/manual",
    "privacy_policy_url": "https://example.org/privacy",
    "health_warning_url": "https://example.org/health",
    "achievements_visible": 1,
    "achievement_count": 51,
    "metacritic_score": 95,
    "metacritic_url": "https://example.org/metacritic",
    "metacritic_always_show": 0,
    "anticheat_name": "VAC",
    "anticheat_kernel_mode": 0,
    "anticheat_uninstall_completely": 1,
    "anticheat_boot_protection": 0,
    "anticheat_boot_protection_name": "Boot guard",
    "ai_generation_service_name": "Helper",
    "ai_generation_service_url": "https://example.org/ai",
}
"""Portal 2 with every app column the store columns read, each one distinct where it can be."""

FULL_GAME: Final[Sample] = {
    **LOOKUPS,
    "app": [
        *({"appid": appid, "name": f"Related {appid}"} for appid in _RELATED),
        {"appid": 70, "name": "Half-Life", "type": 0, "store_country": "BR", "success": 1},
        _PORTAL_2,
    ],
    "app_text": [
        {"appid": 620, "short_description": "The sequel.", "capsule_headline": "Now with co-op"},
    ],
    "app_category": [{"appid": 620, "categoryid": 28}, {"appid": 620, "categoryid": 2}],
    "app_genre": [
        {"appid": 620, "genreid": 25, "position": 0},
        {"appid": 620, "genreid": 1, "position": 1},
    ],
    "creator": [{"creator_id": 1, "name": "Valve"}],
    "credit": [
        {"credit_id": 1, "name": "Valve", "creator_id": 1},
        {"credit_id": 2, "name": "Valve Corporation"},
        {"credit_id": 3, "name": "Portal"},
    ],
    "app_credit": [
        {"appid": 620, "role": "developer", "position": 0, "credit_id": 1},
        {"appid": 620, "role": "publisher", "position": 0, "credit_id": 2},
        {"appid": 620, "role": "franchise", "position": 0, "credit_id": 3},
    ],
    "app_related": [
        {
            "appid": 620,
            "kind": "demo",
            "related_appid": 621,
            "label": "Demo",
            "show_above_purchase": 1,
        },
        {"appid": 620, "kind": "standalone_demo", "related_appid": 622, "show_above_purchase": 0},
        {"appid": 620, "kind": "playtest", "related_appid": 623, "is_open": 1},
        {"appid": 620, "kind": "dlc_parent", "related_appid": 624},
        {
            "appid": 620,
            "kind": "related_f2p",
            "related_appid": 625,
            "header_text": "Free",
            "description_text": "Try it",
        },
        {"appid": 620, "kind": "season_pass", "related_appid": 626},
    ],
    "app_content_descriptor": [{"appid": 620, "descriptorid": 5}],
    "app_interactive_element": [{"appid": 620, "element": 3}, {"appid": 620, "element": 1}],
    "app_rating_descriptor": [{"appid": 620, "position": 0, "descriptor": "Fantasy Violence"}],
    "app_document": [{"appid": 620, "document": 2}],
    "app_manufacturer": [{"appid": 620, "position": 0, "name": "Valve"}],
    "app_steam_award": [
        {"appid": 620, "position": 0, "voteid": 7, "award_year": 2020, "title": "Labor of Love"},
    ],
    "app_review_summary": [
        {
            "appid": 620,
            "scope": scope,
            "review_count": count,
            "percent_positive": percent,
            "review_score": 9,
        }
        for scope, count, percent in (
            ("filtered", 410000, 98),
            ("language", 300000, 97),
            ("unfiltered", 420000, 96),
        )
    ],
    "app_review_total": [{"appid": 620, "positive": 400000, "negative": 10000, "counts_exact": 1}],
    "offer": [
        {"kind": "package", "id": 8, "name": "Portal 2 renewal"},
        {
            "kind": "package",
            "id": 7,
            "name": "Portal 2",
            "must_purchase_as_set": 0,
            "free_with_master_sub_appid": 625,
            "billing_agreement_type": 2,
            "renewal_time_unit": 3,
            "renewal_time_period": 12,
            "renewal_kind": "package",
            "renewal_id": 8,
        },
        {"kind": "bundle", "id": 9, "name": "Half-Life Complete", "must_purchase_as_set": 1},
    ],
    "offer_price": [
        {
            "kind": "package",
            "id": 7,
            "country": "BR",
            "included_game_count": 3,
            "final_price_in_cents": 3699,
            "original_price_in_cents": 7399,
            "price_before_bundle_discount": 12000,
            "bundle_discount_pct": 15,
            "combined_discount_pct": 55,
            "renewal_price_in_cents": 1999,
            "user_can_purchase_as_gift": 1,
            "hide_discount_pct_for_compliance": 0,
            "price_cannot_be_displayed_as_discount": 1,
            "formatted_final_price": "R$36,99",
            "formatted_original_price": "R$73,99",
            "formatted_price_before_bundle_discount": "R$120,00",
            "formatted_renewal_price": "R$19,99",
        },
        {
            "kind": "bundle",
            "id": 9,
            "country": "BR",
            "final_price_in_cents": 4999,
            "original_price_in_cents": 9999,
            "formatted_final_price": "R$49,99",
            "formatted_original_price": "R$99,99",
        },
    ],
    "offer_discount": [
        {
            "kind": "package",
            "id": 7,
            "country": "BR",
            "position": 0,
            "discount_amount": 3700,
            "discount_description": "Autumn Sale",
            "discount_end_date": "2026-12-01 18:00:00",
        },
    ],
    "app_package_group": [{"appid": 620, "name": "default"}],
    "app_offer": [
        {"appid": 620, "kind": "package", "id": 7, "package_group": "default", "is_best": 1},
        {"appid": 70, "kind": "bundle", "id": 9, "is_best": 1},
    ],
    "followed_app": [{"appid": 70}, {"appid": 620}],
}
"""A Brazilian full entry with every store column filled, and an app sold as a bundle."""

FALLBACK_ONLY: Final[Sample] = {
    **LOOKUPS,
    "app": [{"appid": 10, "name": "Counter-Strike", "store_country": "US", "success": 1}],
    "app_text": [{"appid": 10, "short_description": "The original."}],
    "app_genre": [{"appid": 10, "genreid": 1, "position": 0}],
    "app_review_summary": [
        {
            "appid": 10,
            "scope": "filtered",
            "review_count": 900,
            "percent_positive": 88,
            "review_score": 8,
        },
    ],
    "app_review_total": [{"appid": 10, "positive": 800, "negative": 100, "counts_exact": 0}],
    "offer": [{"kind": "package", "id": 1}],
    "offer_price": [
        {
            "kind": "package",
            "id": 1,
            "country": "US",
            "final_price_in_cents": 999,
            "original_price_in_cents": 999,
            "formatted_final_price": "$9.99",
        },
    ],
    "offer_discount": [
        {"kind": "package", "id": 1, "country": "US", "position": 0, "discount_amount": 100},
    ],
    "app_offer": [{"appid": 10, "kind": "package", "id": 1, "is_best": 1}],
    "followed_app": [{"appid": 10}],
    "wishlist_item": [{"appid": 10, "position": 1}],
}
"""An app only the US store described, followed and wishlisted by a Brazilian profile."""

FALLBACK_WITH_HOME_PRICE: Final[Sample] = {
    **FALLBACK_ONLY,
    "offer_price": [
        *FALLBACK_ONLY["offer_price"],
        {
            "kind": "package",
            "id": 1,
            "country": "BR",
            "final_price_in_cents": 3399,
            "original_price_in_cents": 3399,
            "formatted_final_price": "R$33,99",
        },
    ],
    "offer_discount": [
        *FALLBACK_ONLY["offer_discount"],
        {"kind": "package", "id": 1, "country": "BR", "position": 0, "discount_amount": 500},
    ],
}
"""The same app, whose best offer the Brazilian store also quotes: a bundle's price can belong
to an offer that doesn't hold the app at home."""
