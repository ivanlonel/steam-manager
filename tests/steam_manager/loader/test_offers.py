"""Tests for turning offers and their prices into rows."""

import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steam_manager.loader.offers import included_offer, purchase_option, sql_round
from steam_manager.loader.rows import Findings, MalformedAnswerError, Rows
from steam_manager.steam.models.offers import PurchaseOption
from steam_manager.steam.models.store_item import IncludedOffer, StoreItem

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam" / "store_item"
"""The recorded full entries."""


def portal_2(country: str) -> StoreItem:
    """
    Read Portal 2's recorded full entry.

    :param country: The store it was recorded in.
    :return: The entry.
    """
    return StoreItem.model_validate_json((FIXTURES / f"620-{country}.json").read_bytes())


def option(**fields: object) -> PurchaseOption:
    r"""
    Build a purchase option of package 7.

    :param \*\*fields: Its other fields.
    :return: The option.
    """
    return PurchaseOption.model_validate({"packageid": 7, **fields})


def test_a_purchase_option_gives_its_offer_and_price() -> None:
    """The offer row holds what doesn't depend on the country, the price row the rest."""
    best = portal_2("BR").best_purchase_option
    assert best is not None
    rows, findings = Rows(), Findings()

    key = purchase_option(best, "best_purchase_option", "BR", rows, findings)

    assert key == ("package", best.packageid)
    assert rows.tables["offer"] == [
        {
            "kind": "package",
            "id": best.packageid,
            "name": best.purchase_option_name,
            "must_purchase_as_set": best.must_purchase_as_set,
            "is_free_license": best.is_free_license,
            "free_with_master_sub_appid": None,
            "billing_agreement_type": None,
            "renewal_time_unit": None,
            "renewal_time_period": None,
            "renewal_kind": None,
            "renewal_id": None,
        }
    ]
    [price] = rows.tables["offer_price"]
    assert price["country"] == "BR"
    assert price["final_price_in_cents"] == best.final_price_in_cents
    assert isinstance(price["final_price_in_cents"], int)
    assert price["formatted_final_price"] == best.formatted_final_price
    assert findings.unknown == Counter()
    assert not +findings.mismatches


def test_discounts_keep_their_order_and_end_dates() -> None:
    """Each running discount is a row, in Steam's order, with its end as the notebook's text."""
    rows = Rows()
    discounts = [
        {"discount_amount": "500", "discount_description": "Sale", "discount_end_date": 0},
        {"discount_amount": 100, "discount_end_date": 1302566400},
    ]

    purchase_option(option(active_discounts=discounts), "o", "BR", rows, Findings())

    assert rows.tables["offer_discount"] == [
        {
            "kind": "package",
            "id": 7,
            "country": "BR",
            "position": 0,
            "discount_amount": 500,
            "discount_description": "Sale",
            "discount_end_date": None,
        },
        {
            "kind": "package",
            "id": 7,
            "country": "BR",
            "position": 1,
            "discount_amount": 100,
            "discount_description": None,
            "discount_end_date": "2011-04-12 00:00:00",
        },
    ]


def test_a_subscription_names_the_package_that_renews() -> None:
    """A renewal is an offer of its own, and its price is quoted with the others."""
    rows, findings = Rows(), Findings()
    recurrence = {
        "packageid": 8,
        "billing_agreement_type": 1,
        "renewal_time_unit": 3,
        "renewal_time_period": 1,
        "renewal_price_in_cents": "1999",
        "formatted_renewal_price": "R$19,99",
    }

    purchase_option(option(recurrence_info=recurrence), "o", "BR", rows, findings)

    [offer] = rows.tables["offer"]
    assert (offer["renewal_kind"], offer["renewal_id"]) == ("package", 8)
    assert offer["billing_agreement_type"] == 1
    [price] = rows.tables["offer_price"]
    assert price["renewal_price_in_cents"] == 1999
    assert price["formatted_renewal_price"] == "R$19,99"
    assert findings.unknown == Counter()


def test_discount_pct_is_checked_as_sqlite_rounds() -> None:
    """-19.5% rounds away from zero, as the generated column does, not up as the notebook did."""
    agrees, differs = Findings(), Findings()
    prices = {"original_price_in_cents": 200, "final_price_in_cents": 239}

    purchase_option(option(**prices, discount_pct=-20), "o", "BR", Rows(), agrees)
    purchase_option(option(**prices, discount_pct=-19), "o", "BR", Rows(), differs)

    assert agrees.mismatches == Counter({"offer_price.discount_pct": 0})
    assert differs.mismatches == Counter({"offer_price.discount_pct": 1})


def test_a_free_offer_derives_no_discount() -> None:
    """Without an original price there is nothing to take a discount from."""
    findings = Findings()

    purchase_option(option(original_price_in_cents=0), "o", "BR", Rows(), findings)
    purchase_option(option(final_price_in_cents=0), "o", "BR", Rows(), findings)

    assert not +findings.mismatches


@given(st.integers(-200_000, 200_000).map(lambda tenths: tenths / 10))
def test_sql_round_rounds_as_sqlite(value: float) -> None:
    """The check derives what the generated column holds, halves included."""
    with closing(sqlite3.connect(":memory:")) as connection:
        expected = connection.execute("SELECT CAST(ROUND(?) AS INTEGER)", (value,)).fetchone()[0]

    assert sql_round(value) == expected


def test_a_new_field_in_an_option_is_reported_at_its_path() -> None:
    """A field Steam adds to purchase options names where it was found."""
    findings = Findings()

    purchase_option(option(new_field=1), "purchase_options[]", "BR", Rows(), findings)

    assert findings.unknown == Counter({"purchase_options[].new_field": 1})


def test_an_option_without_an_offer_is_refused() -> None:
    """An option naming neither a package nor a bundle can't be stored."""
    with pytest.raises(MalformedAnswerError, match="neither a package nor a bundle"):
        purchase_option(PurchaseOption(), "o", "BR", Rows(), Findings())


def test_an_included_offer_gives_its_apps_categories_and_options() -> None:
    """A bundle's short record holds its apps in that country, its categories and its prices."""
    included = portal_2("BR").included_items
    assert included is not None
    bundle = included.included_bundles[0]
    rows, findings = Rows(), Findings()

    included_offer(bundle, "included_bundles[]", "BR", rows, findings, kind="bundle")

    assert [row["appid"] for row in rows.tables["offer_app"]] == list(bundle.included_appids)
    assert {row["country"] for row in rows.tables["offer_app"]} == {"BR"}
    assert rows.tables["offer_category"]
    offers = [row for row in rows.tables["offer"] if row["kind"] == "bundle"]
    assert offers[-1]["id"] == bundle.id
    assert offers[-1]["unavailable_for_country_restriction"] == (
        bundle.unvailable_for_country_restriction
    )
    assert bundle.best_purchase_option is not None
    assert (offers[-1]["best_kind"], offers[-1]["best_id"]) == ("bundle", bundle.id)
    assert any(row["id"] == bundle.id for row in rows.tables["offer_price"])
    assert findings.unknown == Counter()
    assert not +findings.mismatches


def test_yen_prices_are_in_hundredths() -> None:
    """Steam's cents are hundredths even in a currency without decimals, as v_games assumes."""
    answer = json.loads((FIXTURES / "546560-JP.json").read_bytes())

    for purchase in answer["purchase_options"]:
        whole = int(re.sub(r"\D", "", purchase["formatted_final_price"]))
        assert int(purchase["final_price_in_cents"]) == 100 * whole


def test_an_included_package_keeps_its_descriptors_and_own_price() -> None:
    """A package sold apart has a price of its own besides its best option's."""
    package = IncludedOffer.model_validate(
        {
            "id": 7,
            "item_type": 1,
            "visible": True,
            "success": 1,
            "content_descriptorids": [2, 5],
            "self_purchase_option": {"packageid": 7, "final_price_in_cents": "999"},
        }
    )
    rows, findings = Rows(), Findings()

    included_offer(package, "included_packages[]", "BR", rows, findings, kind="package")

    assert [row["descriptorid"] for row in rows.tables["offer_content_descriptor"]] == [2, 5]
    assert "offer_category" not in rows.tables
    assert [row["final_price_in_cents"] for row in rows.tables["offer_price"]] == [999]
    assert findings.unknown == Counter()
    assert not +findings.mismatches


def test_an_included_offer_without_an_id_is_refused() -> None:
    """A short record naming no offer can't be stored."""
    with pytest.raises(MalformedAnswerError, match=r"included_packages\[\] has no id"):
        included_offer(
            IncludedOffer(), "included_packages[]", "BR", Rows(), Findings(), kind="package"
        )


def test_an_included_offers_option_reports_what_no_page_stores() -> None:
    """A short record's option belongs to no app's page: an edition flag there is reported."""
    package = IncludedOffer.model_validate(
        {
            "id": 7,
            "item_type": 1,
            "visible": True,
            "success": 1,
            "best_purchase_option": {"packageid": 7, "is_edition": True, "package_group": "x"},
        }
    )
    findings = Findings()

    included_offer(package, "included_packages[]", "BR", Rows(), findings, kind="package")

    assert findings.unknown == Counter({"included_packages[].best_purchase_option.is_edition": 1})
    assert findings.mismatches["included_offer.package_group"] == 1
