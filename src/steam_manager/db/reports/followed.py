"""
The followed apps report: every app the account follows, with its catalog and store columns.

The catalog columns come first, as the notebook's Followed tab has them. Reviews and flags read
as 0 rather than blank for apps the catalog holds totals for.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import Text, and_, case, cast, func
from sqlalchemy.orm import aliased

from steam_manager.db.reports.scores import scores
from steam_manager.db.reports.store_columns import (
    Store,
    content_descriptors,
    epoch,
    genres,
    json_rows,
    related_ids,
    store_columns,
)
from steam_manager.db.schema.account import FollowedApp
from steam_manager.db.schema.classification import AppRatingDescriptor
from steam_manager.db.schema.offers import OfferDiscount

if TYPE_CHECKING:
    from sqlalchemy import SQLColumnExpression

    from steam_manager.db.reports.scores import Columns, Report

__all__ = ["catalog_columns", "followed"]


def catalog_columns(store: Store, home_country: str) -> dict[str, SQLColumnExpression[Any]]:
    """
    Build the catalog columns the notebook shows before the store columns.

    :param store: The report's aliases.
    :param home_country: The profile's home country, the only one whose discounts show.
    :return: The columns, in the tab's order.
    """
    a, f, s, o, x, p = (
        store.app,
        store.filtered,
        store.totals,
        store.best,
        store.offer,
        store.price,
    )
    in_catalog = s.appid.is_not(None)
    discount = func.json_object(
        "discount_amount",
        cast(OfferDiscount.discount_amount, Text),
        "discount_description",
        OfferDiscount.discount_description,
        "discount_end_date",
        epoch(OfferDiscount.discount_end_date),
    )
    return {
        "type": a.type,
        "is_listed": a.is_listed,
        "is_free": case((in_catalog, func.coalesce(a.is_free, 0)), else_=a.is_free),
        "is_early_access": case(
            (in_catalog, func.coalesce(a.is_early_access, 0)), else_=a.is_early_access
        ),
        "is_coming_soon": case(
            (in_catalog, func.coalesce(a.is_coming_soon, 0)), else_=a.is_coming_soon
        ),
        "review_count": case((in_catalog, func.coalesce(f.review_count, 0)), else_=f.review_count),
        "percent_positive": case((f.review_count > 0, f.percent_positive)),
        "positive": s.positive,
        "negative": s.negative,
        "counts_exact": s.counts_exact,
        **scores(s),
        "item_type": case((a.success.is_not(None), 0)),
        "success": a.success,
        "visible": case((a.success.is_not(None), a.success == 1)),
        "store_country": a.store_country,
        "content_descriptorids": content_descriptors(store.listed),
        "demo_appid": related_ids(a, "demo"),
        "standalone_demo_appid": related_ids(a, "standalone_demo"),
        "descriptors": json_rows(
            func.json_quote(AppRatingDescriptor.descriptor),
            AppRatingDescriptor.position,
            AppRatingDescriptor,
            AppRatingDescriptor.appid == a.appid,
        ),
        "interactive_elements": a.rating_interactive_elements,
        "active_discounts": json_rows(
            discount,
            OfferDiscount.position,
            OfferDiscount,
            and_(
                OfferDiscount.kind == o.kind,
                OfferDiscount.id == o.id,
                OfferDiscount.country == home_country,
                a.store_country == home_country,
            ),
        ),
        "recurrence_info.packageid": x.renewal_id,
        "recurrence_info.billing_agreement_type": x.billing_agreement_type,
        "recurrence_info.renewal_time_unit": x.renewal_time_unit,
        "recurrence_info.renewal_time_period": x.renewal_time_period,
        "recurrence_info.renewal_price_in_cents": p.renewal_price_in_cents,
        "recurrence_info.formatted_renewal_price": p.formatted_renewal_price,
        "genres": genres(a),
    }


def followed(home_country: str) -> Report:
    """
    Build the followed apps report.

    :param home_country: The profile's home country.
    :return: The query behind ``v_followed``.
    """
    listed = aliased(FollowedApp, name="w")
    store = Store.aliases()
    catalog = catalog_columns(store, home_country)
    columns: Columns = {
        "appid": listed.appid,
        "name": store.listed.name,
        **catalog,
        **{
            name: column
            for name, column in store_columns(store, home_country).items()
            if name not in catalog
        },
    }
    return store.report(columns, listed, home_country)
