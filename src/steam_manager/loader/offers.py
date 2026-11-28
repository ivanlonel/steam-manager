"""Turn offers, the packages and bundles an app is sold in, and their prices into rows."""

import math
from typing import TYPE_CHECKING, Final, Literal

from steam_manager.db.schema.offers import (
    Offer,
    OfferApp,
    OfferCategory,
    OfferContentDescriptor,
    OfferDiscount,
    OfferPrice,
)
from steam_manager.loader.rows import iso
from steam_manager.steam.models.offers import RecurrenceInfo

if TYPE_CHECKING:
    from steam_manager.loader.rows import Findings, Rows
    from steam_manager.steam.models.offers import PurchaseOption
    from steam_manager.steam.models.store_item import Categories, IncludedOffer

COUNTRY_DEPENDENT: Final = frozenset(
    {"success", "unavailable_for_country_restriction", "best_kind", "best_id"}
)
"""The offer columns whose value depends on the store country that sent them."""

CATEGORY_LISTS: Final = (
    "supported_player_categoryids",
    "feature_categoryids",
    "controller_categoryids",
)
"""The lists Steam keeps store categories in, in the order of their ``store_category.type``."""

SHORT_RECORD_FIELDS: Final = (
    "id",
    "item_type",
    "visible",
    "success",
    "name",
    "store_url_path",
    "store_url_slug",
)
"""The fields the short record of an offer or a creator page starts with."""

_ITEM_TYPES: Final = {"package": 1, "bundle": 2}

type OfferKey = tuple[str, int]
"""An offer's kind and id."""


def sql_round(value: float) -> int:
    """
    Round half away from zero, as SQLite's ``ROUND`` does.

    :param value: The number.
    :return: The nearest integer, a half going away from zero.
    """
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def _discount_pct(original: int | None, final: int | None) -> int | None:
    """
    Work out a discount as the generated ``offer_price.discount_pct`` does.

    :param original: The price without a discount, in cents.
    :param final: The price now, in cents.
    :return: The discount in percent, or ``None`` without an original price to take it from.
    """
    if not original or final is None:
        return None
    return sql_round(100.0 * (original - final) / original)


def category_ids(categories: Categories | None, path: str, findings: Findings) -> list[int]:
    """
    List the store categories of an app or offer, from Steam's three lists.

    :param categories: The lists, or ``None``.
    :param path: Where they sit in the answer.
    :param findings: Where a list nothing knows is reported.
    :return: The category ids, list after list.
    """
    findings.rest(categories, path, CATEGORY_LISTS)
    if categories is None:
        return []
    return [categoryid for name in CATEGORY_LISTS for categoryid in getattr(categories, name)]


def purchase_option(
    option: PurchaseOption, path: str, country: str, rows: Rows, findings: Findings
) -> OfferKey:
    """
    Turn a way to buy an app into its offer, its price in *country* and its discounts.

    ``package_group`` and ``is_edition`` describe the option on one app's page, so the caller
    stores them with that app.

    :param option: The option.
    :param path: Where it sits in the answer, such as ``purchase_options[]``.
    :param country: The store country that quoted it.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :return: The offer's kind and id.
    :raise ValueError: When the option names neither a package nor a bundle.
    """
    if option.packageid is not None:
        key: OfferKey = ("package", option.packageid)
    elif option.bundleid is not None:
        key = ("bundle", option.bundleid)
    else:
        message = f"{path} names neither a package nor a bundle"
        raise ValueError(message)
    kind, id_ = key
    findings.same(
        "offer_price.discount_pct",
        option.discount_pct,
        _discount_pct(option.original_price_in_cents, option.final_price_in_cents),
    )
    recurrence = option.recurrence_info or RecurrenceInfo()
    findings.rest(
        recurrence,
        f"{path}.recurrence_info",
        {
            "packageid",
            "billing_agreement_type",
            "renewal_time_unit",
            "renewal_time_period",
            "renewal_price_in_cents",
            "formatted_renewal_price",
        },
    )
    rows.add(
        Offer,
        kind=kind,
        id=id_,
        name=option.purchase_option_name,
        must_purchase_as_set=option.must_purchase_as_set,
        is_free_license=option.is_free_license,
        free_with_master_sub_appid=option.free_with_master_sub_appid,
        billing_agreement_type=recurrence.billing_agreement_type,
        renewal_time_unit=recurrence.renewal_time_unit,
        renewal_time_period=recurrence.renewal_time_period,
        renewal_kind="package" if recurrence.packageid else None,
        renewal_id=recurrence.packageid,
    )
    rows.add(
        OfferPrice,
        kind=kind,
        id=id_,
        country=country,
        included_game_count=option.included_game_count,
        final_price_in_cents=option.final_price_in_cents,
        original_price_in_cents=option.original_price_in_cents,
        price_before_bundle_discount=option.price_before_bundle_discount,
        bundle_discount_pct=option.bundle_discount_pct,
        combined_discount_pct=option.combined_discount_pct,
        renewal_price_in_cents=recurrence.renewal_price_in_cents,
        user_can_purchase_as_gift=option.user_can_purchase_as_gift,
        hide_discount_pct_for_compliance=option.hide_discount_pct_for_compliance,
        price_cannot_be_displayed_as_discount=option.price_cannot_be_displayed_as_discount,
        formatted_final_price=option.formatted_final_price,
        formatted_original_price=option.formatted_original_price,
        formatted_price_before_bundle_discount=option.formatted_price_before_bundle_discount,
        formatted_renewal_price=recurrence.formatted_renewal_price,
    )
    for position, discount in enumerate(option.active_discounts):
        findings.rest(
            discount,
            f"{path}.active_discounts[]",
            {"discount_amount", "discount_description", "discount_end_date"},
        )
        rows.add(
            OfferDiscount,
            kind=kind,
            id=id_,
            country=country,
            position=position,
            discount_amount=discount.discount_amount,
            discount_description=discount.discount_description,
            discount_end_date=iso(discount.discount_end_date),
        )
    findings.rest(
        option,
        path,
        {
            "packageid",
            "bundleid",
            "purchase_option_name",
            "package_group",  # the caller's
            "is_edition",  # the caller's
            "must_purchase_as_set",
            "included_game_count",
            "is_free_license",
            "free_with_master_sub_appid",
            "final_price_in_cents",
            "original_price_in_cents",
            "price_before_bundle_discount",
            "discount_pct",  # checked above
            "bundle_discount_pct",
            "combined_discount_pct",
            "formatted_final_price",
            "formatted_original_price",
            "formatted_price_before_bundle_discount",
            "user_can_purchase_as_gift",
            "hide_discount_pct_for_compliance",
            "price_cannot_be_displayed_as_discount",
            "active_discounts",
            "recurrence_info",
        },
    )
    return key


def included_offer(
    item: IncludedOffer,
    path: str,
    country: str,
    rows: Rows,
    findings: Findings,
    *,
    kind: Literal["package", "bundle"],
) -> None:
    """
    Turn the short record of a package or bundle into its offer, apps, categories and prices.

    :param item: The short record.
    :param path: Where it sits in the answer, such as ``included_items.included_bundles[]``.
    :param country: The store country that sent it: the apps it holds can differ by country.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :param kind: ``package`` or ``bundle``.
    :raise ValueError: When the record has no id.
    """
    if item.id is None:
        message = f"{path} has no id"
        raise ValueError(message)
    findings.same("offer.item_type", item.item_type, _ITEM_TYPES[kind])
    findings.same("offer.visible", item.visible, item.success == 1)
    for appid in item.included_appids:
        rows.add(OfferApp, kind=kind, id=item.id, country=country, appid=appid)
    for categoryid in category_ids(item.categories, f"{path}.categories", findings):
        rows.add(OfferCategory, kind=kind, id=item.id, categoryid=categoryid)
    for descriptor in item.content_descriptorids:
        rows.add(OfferContentDescriptor, kind=kind, id=item.id, descriptorid=descriptor)
    best = item.best_purchase_option
    best_kind, best_id = (
        purchase_option(best, f"{path}.best_purchase_option", country, rows, findings)
        if best
        else (None, None)
    )
    if item.self_purchase_option:
        purchase_option(
            item.self_purchase_option, f"{path}.self_purchase_option", country, rows, findings
        )
    rows.add(
        Offer,
        kind=kind,
        id=item.id,
        name=item.name or None,
        success=item.success,
        store_url_path=item.store_url_path or None,
        store_url_slug=item.store_url_slug or None,
        primary_appid=item.appid or None,
        type=item.type,
        purchase_description_bbcode=item.purchase_description_bbcode,
        unavailable_for_country_restriction=item.unvailable_for_country_restriction,
        best_kind=best_kind,
        best_id=best_id,
    )
    # item_type and visible are checked above. included_types are the distinct types of the
    # apps it holds, in all 72,920 packages checked on 2026-11-06: the apps' own rows say it.
    findings.rest(
        item,
        path,
        {
            *SHORT_RECORD_FIELDS,
            "appid",
            "type",
            "purchase_description_bbcode",
            "unvailable_for_country_restriction",
            "included_types",
            "included_appids",
            "categories",
            "content_descriptorids",
            "best_purchase_option",
            "self_purchase_option",
        },
    )
