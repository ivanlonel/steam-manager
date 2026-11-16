"""Tests for the followed apps report, compared with the notebook's view."""

from typing import TYPE_CHECKING, Final

from tests.steam_manager.db.reports._parity import mismatches, notebook_view, report_view

if TYPE_CHECKING:
    from pathlib import Path

    from tests.steam_manager.db.reports._parity import Sample

_RELATED: Final = (621, 622, 623, 624, 625, 626)
"""Apps Portal 2 points at: a demo, a standalone demo, a playtest, its DLC parent, a free
version and its season pass."""

_LOOKUPS: Final[Sample] = {
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

FULL_GAME: Final[Sample] = {
    **_LOOKUPS,
    "app": [
        *({"appid": appid, "name": f"Related {appid}"} for appid in _RELATED),
        {"appid": 70, "name": "Half-Life", "type": 0, "store_country": "BR", "success": 1},
        {
            "appid": 620,
            "name": "Portal 2",
            "type": 0,
            "success": 1,
            "store_url_path": "app/620/Portal_2/",
            "store_country": "BR",
            "is_listed": 1,
            "is_free": 0,
            "unlisted": 0,
            "unavailable_for_country_restriction": 0,
            "parent_appid": 624,
            "steam_release_date": "2011-04-18 17:00:00",
            "original_release_date": "2011-04-19 00:00:00",
            "release_from_early_access_date": "2012-01-01 00:00:00",
            "is_coming_soon": 0,
            "is_early_access": 0,
            "free_weekend_start": "2026-11-20 18:00:00",
            "free_weekend_end": "2026-11-23 18:00:00",
            "free_weekend_text": "Play free this weekend",
            "free_weekend_appid": 620,
            "windows": 1,
            "mac": 1,
            "steamos_linux": 1,
            "steam_deck_compat_category": 3,
            "vr_vrhmd": 0,
            "agency": 1,
            "rating": "e10",
            "required_age": 0,
            "vetted": 1,
            "has_community_hub": 1,
            "website": "https://www.thinkwithportals.com/",
            "achievements_visible": 1,
            "achievement_count": 51,
            "metacritic_score": 95,
            "anticheat_name": "VAC",
            "anticheat_kernel_mode": 0,
        },
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
    ],
    "app_credit": [
        {"appid": 620, "role": "developer", "position": 0, "credit_id": 1},
        {"appid": 620, "role": "publisher", "position": 0, "credit_id": 2},
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
            "percent_positive": 98,
            "review_score": 9,
        }
        for scope, count in (("filtered", 410000), ("language", 300000), ("unfiltered", 420000))
    ],
    "app_review_total": [{"appid": 620, "positive": 400000, "negative": 10000, "counts_exact": 1}],
    "offer": [{"kind": "package", "id": 7, "name": "Portal 2", "must_purchase_as_set": 0}],
    "offer_price": [
        {
            "kind": "package",
            "id": 7,
            "country": "BR",
            "final_price_in_cents": 3699,
            "original_price_in_cents": 7399,
            "user_can_purchase_as_gift": 1,
            "formatted_final_price": "R$36,99",
            "formatted_original_price": "R$73,99",
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
    ],
    "followed_app": [{"appid": 70}, {"appid": 620}],
}
"""A Brazilian full entry with every list the store columns read, and a bare one."""

FALLBACK_ONLY: Final[Sample] = {
    **_LOOKUPS,
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
}
"""An app only the US store described, followed by a Brazilian profile."""


def test_followed_has_the_notebooks_columns_plus_store_categories(tmp_path: Path) -> None:
    """The notebook's columns in order, with the store categories as one list at the end."""
    notebooks = notebook_view("v_followed", {}).columns

    assert report_view(tmp_path, "v_followed", {}).columns == [*notebooks, "store_categories"]


def test_followed_matches_the_notebook_on_the_same_rows(tmp_path: Path) -> None:
    """Every store column agrees, the JSON lists, the free weekend and the prices included."""
    expected = notebook_view("v_followed", FULL_GAME).rows

    assert mismatches(expected, report_view(tmp_path, "v_followed", FULL_GAME).rows) == []
    assert expected[1]["demos"] is not None
    assert expected[1]["formatted_final_price"] == "R$36,99"


def test_store_categories_lists_internal_names(tmp_path: Path) -> None:
    """An app's store categories are one JSON list of their internal names, in id order."""
    rows = report_view(tmp_path, "v_followed", FULL_GAME).rows

    assert [row["store_categories"] for row in rows] == [
        None,
        '["SinglePlayer","FullControllerSupport"]',
    ]


def test_a_fallback_app_shows_its_store_but_no_price(tmp_path: Path) -> None:
    """The US store's reviews and description show; its dollar prices never do."""
    (row,) = report_view(tmp_path, "v_followed", FALLBACK_ONLY).rows

    assert (row["store_country"], row["review_count"], row["short_description"]) == (
        "US",
        900,
        "The original.",
    )
    assert row["genres"] == "Action"
    prices = (
        "final_price_in_cents",
        "formatted_final_price",
        "original_price_in_cents",
        "discount_pct",
        "active_discounts",
    )
    assert [row[column] for column in prices] == [None] * len(prices)
    assert row["unvailable_for_country_restriction"] == 1
