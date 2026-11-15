"""Tests for the offer and price tables, compared with the notebook's."""

from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import exc, insert, select

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.offers import AppOffer, Offer, OfferApp, OfferDiscount, OfferPrice
from tests.steam_manager.db.schema._notebook import differences

if TYPE_CHECKING:
    from sqlalchemy import Engine

OFFER_TABLES: Final = (
    "offer",
    "offer_app",
    "offer_category",
    "offer_content_descriptor",
    "offer_price",
    "offer_discount",
    "app_package_group",
    "app_offer",
)
"""The tables of the ways to buy an app."""

_COUNTRIES: Final = "check (country IN ('BR', 'US'))"
_FORMATTED: Final = (
    "formatted_final_price",
    "formatted_original_price",
    "formatted_price_before_bundle_discount",
    "formatted_renewal_price",
)
CHANGED_FROM_THE_NOTEBOOK: Final = {
    "offer_app": [f"only in the notebook: offer_app {_COUNTRIES}"],
    "offer_price": [
        f"only in the notebook: offer_price {_COUNTRIES}",
        *(
            f"only declared: offer_price.{name} #{14 + index}: TEXT notnull=0 pk=0 default=None"
            " hidden=0"
            for index, name in enumerate(_FORMATTED)
        ),
    ],
}
"""What the spec changes: any country, and Steam's own price strings, stored."""


@pytest.mark.parametrize("table", OFFER_TABLES)
def test_an_offer_table_matches_the_notebook(table: str) -> None:
    """Each has the notebook's columns, keys, references and generated discount."""
    assert differences(table) == CHANGED_FROM_THE_NOTEBOOK.get(table, [])


def test_the_discount_follows_the_prices(steam_tables: Engine) -> None:
    """A discount is worked out from the prices, and a free or unpriced offer has none."""
    prices = [
        {"country": "BR", "final_price_in_cents": 1999, "original_price_in_cents": 3999},
        {"country": "JP", "final_price_in_cents": 500, "original_price_in_cents": None},
        {"country": "US", "final_price_in_cents": 0, "original_price_in_cents": 0},
    ]
    with steam_tables.begin() as connection:
        connection.execute(insert(Offer), [{"kind": "package", "id": 1}])
        connection.execute(
            insert(OfferPrice), [{"kind": "package", "id": 1, **price} for price in prices]
        )

        discounts = connection.scalars(
            select(OfferPrice.discount_pct).order_by(OfferPrice.country)
        ).all()

    assert discounts == [50, None, None]


def test_an_app_has_one_best_offer(steam_tables: Engine) -> None:
    """Any number of offers can be listed under an app, and only one of them is the best."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        connection.execute(insert(Offer), [{"kind": "package", "id": id_} for id_ in (1, 2, 3)])
        connection.execute(
            insert(AppOffer),
            [
                {"appid": 620, "kind": "package", "id": id_, "is_best": id_ == 1}
                for id_ in (1, 2, 3)
            ],
        )

    with (
        pytest.raises(exc.IntegrityError, match=r"UNIQUE constraint failed: app_offer\.appid"),
        steam_tables.begin() as connection,
    ):
        connection.execute(
            insert(AppOffer), [{"appid": 620, "kind": "bundle", "id": 1, "is_best": True}]
        )


def test_any_country_is_accepted(steam_tables: Engine) -> None:
    """The notebook allowed only BR and US; a profile can be anywhere."""
    with steam_tables.begin() as connection:
        connection.execute(insert(App), [{"appid": 620}])
        connection.execute(insert(Offer), [{"kind": "bundle", "id": 5}])
        connection.execute(
            insert(OfferApp), [{"kind": "bundle", "id": 5, "country": "JP", "appid": 620}]
        )
        connection.execute(
            insert(OfferPrice),
            [{"kind": "bundle", "id": 5, "country": "JP", "formatted_final_price": "¥ 1,200"}],
        )

        assert connection.scalar(select(OfferPrice.formatted_final_price)) == "¥ 1,200"


def test_a_discount_needs_its_price(steam_tables: Engine) -> None:
    """A discount belongs to a price in one country, which must be there."""
    with steam_tables.begin() as connection:
        connection.execute(insert(Offer), [{"kind": "bundle", "id": 5}])

    with (
        pytest.raises(exc.IntegrityError, match="FOREIGN KEY constraint failed"),
        steam_tables.begin() as connection,
    ):
        connection.execute(
            insert(OfferDiscount), [{"kind": "bundle", "id": 5, "country": "BR", "position": 0}]
        )
