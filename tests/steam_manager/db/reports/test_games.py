"""Tests for the games report, compared with the notebook's view."""

from typing import TYPE_CHECKING, Final

from sqlalchemy import insert, text

from steam_manager.db.engine import open_database
from steam_manager.db.reports import create_views
from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.offers import AppOffer, Offer, OfferPrice
from steam_manager.db.schema.reviews import AppReviewTotal
from tests.steam_manager.db.reports._parity import mismatches, notebook_view, report_view

if TYPE_CHECKING:
    from pathlib import Path

    from tests.steam_manager.db.reports._parity import Sample

ACCOUNT_COLUMNS: Final = ("owned", "ignored", "status", "on_notion")
"""The notebook's columns that need sign-in or are the owner's own; they come later or never."""


def _priced(appid: int, store_country: str, prices: dict[str, tuple[int, int]]) -> Sample:
    """
    Describe one rated app with one best offer, priced in some countries.

    :param appid: The app.
    :param store_country: The store that described it.
    :param prices: Final and original price in cents, by country.
    :return: The rows.
    """
    return {
        "app": [{"appid": appid, "name": f"App {appid}", "store_country": store_country}],
        "app_review_total": [
            {"appid": appid, "positive": 90, "negative": 10, "counts_exact": 1},
        ],
        "offer": [{"kind": "package", "id": appid}],
        "app_offer": [{"appid": appid, "kind": "package", "id": appid, "is_best": 1}],
        "offer_price": [
            {
                "kind": "package",
                "id": appid,
                "country": country,
                "final_price_in_cents": final,
                "original_price_in_cents": original,
            }
            for country, (final, original) in prices.items()
        ],
    }


GAMES: Final[Sample] = {
    "review_score": [{"review_score": 0}, {"review_score": 9}],
    "app": [
        {
            "appid": 70,
            "name": "Half-Life",
            "type": 0,
            "is_listed": 1,
            "store_country": "BR",
            "steam_release_date": "1998-11-08 00:00:00",
        },
        {
            "appid": 400,
            "name": "Portal",
            "type": 0,
            "is_listed": 1,
            "store_country": "BR",
            "is_free": 1,
            "steam_release_date": "2007-10-10 00:00:00",
        },
        {
            "appid": 620,
            "name": "Portal 2",
            "type": 0,
            "is_listed": 1,
            "store_country": "BR",
            "steam_release_date": "2011-04-18 17:00:00",
        },
    ],
    "app_review_summary": [
        {
            "appid": 70,
            "scope": "filtered",
            "review_count": 0,
            "percent_positive": 0,
            "review_score": 0,
        },
        {
            "appid": 620,
            "scope": "filtered",
            "review_count": 410000,
            "percent_positive": 97,
            "review_score": 9,
        },
    ],
    "app_review_total": [
        {"appid": 70, "positive": 0, "negative": 0, "counts_exact": 1},
        {"appid": 400, "positive": 147000, "negative": 3000, "counts_exact": 0},
        {"appid": 620, "positive": 398000, "negative": 12000, "counts_exact": 1},
    ],
    "offer": [{"kind": "package", "id": 1}, {"kind": "package", "id": 2}],
    "app_offer": [
        {"appid": 70, "kind": "package", "id": 1, "is_best": 1},
        {"appid": 620, "kind": "package", "id": 2, "is_best": 1},
    ],
    "offer_price": [
        {
            "kind": "package",
            "id": 1,
            "country": "BR",
            "final_price_in_cents": 1499,
            "original_price_in_cents": 2999,
        },
        {
            "kind": "package",
            "id": 2,
            "country": "BR",
            "final_price_in_cents": 3699,
            "original_price_in_cents": None,
        },
    ],
    "wishlist_item": [{"appid": 70, "position": 1}],
    "followed_app": [{"appid": 620}],
}
"""Three apps the Brazilian store described: one on sale, one free, one at full price."""


def test_games_has_the_notebooks_columns_less_the_account_ones(tmp_path: Path) -> None:
    """The notebook's columns, in order, except those that need sign-in or are the owner's."""
    notebooks = notebook_view("v_games", {}).columns

    assert report_view(tmp_path, "v_games", {}).columns == [
        column for column in notebooks if column not in ACCOUNT_COLUMNS
    ]


def test_games_matches_the_notebook_on_the_same_rows(tmp_path: Path) -> None:
    """Counts, scores, price, release day and the wishlist and followed flags agree."""
    expected = notebook_view("v_games", GAMES).rows

    assert mismatches(expected, report_view(tmp_path, "v_games", GAMES).rows) == []
    assert [row["price"] for row in expected] == [29.99, None, 36.99]


def test_a_free_app_has_no_price(tmp_path: Path) -> None:
    """An app with no offer stays in the report, with a blank price rather than 0."""
    rows = {row["appid"]: row for row in report_view(tmp_path, "v_games", GAMES).rows}

    assert rows[400]["price"] is None


def test_a_price_from_another_country_never_shows(tmp_path: Path) -> None:
    """An app only the US store priced shows no price to a Brazilian profile."""
    sample = _priced(10, "US", {"US": (999, 999)})

    (row,) = report_view(tmp_path, "v_games", sample).rows

    assert row["price"] is None


def test_a_new_home_country_replaces_the_views(tmp_path: Path) -> None:
    """Writing the views again for another home country shows that country's price."""
    engine = open_database(tmp_path / "steam.sqlite")
    SteamBase.metadata.create_all(engine)
    sample = _priced(620, "BR", {"BR": (3699, 3699), "US": (999, 999)})
    with engine.begin() as connection:
        for model in (App, AppReviewTotal, Offer, AppOffer, OfferPrice):
            connection.execute(insert(model), list(sample[model.__tablename__]))

    prices = []
    for country in ("BR", "US"):
        create_views(engine, home_country=country)
        with engine.connect() as connection:
            prices.append(connection.scalar(text("SELECT price FROM v_games")))
    engine.dispose()

    assert prices == [36.99, 9.99]
