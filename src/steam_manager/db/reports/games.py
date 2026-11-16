"""The games report: every app with review totals, with its scores, price and account flags."""

from typing import TYPE_CHECKING

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import aliased

from steam_manager.db.reports.scores import labelled, scores
from steam_manager.db.schema.account import FollowedApp, WishlistItem
from steam_manager.db.schema.apps import App
from steam_manager.db.schema.offers import AppOffer, OfferPrice
from steam_manager.db.schema.reviews import AppReviewSummary, AppReviewTotal

if TYPE_CHECKING:
    from steam_manager.db.reports.scores import Columns, Report

__all__ = ["games"]


def games(home_country: str) -> Report:
    """
    Build the games report: one row per app with review totals, ordered by appid.

    The price shows only for apps the home store described, in its currency, as the notebook
    showed only Brazilian prices. The account's columns arrive with sign-in: owned, ignored and
    the tracking status.

    :param home_country: The profile's home country.
    :return: The query behind ``v_games``.
    """
    totals = aliased(AppReviewTotal, name="s")
    app = aliased(App, name="a")
    summary = aliased(AppReviewSummary, name="f")
    best = aliased(AppOffer, name="o")
    price = aliased(OfferPrice, name="p")
    columns: Columns = {
        "appid": totals.appid,
        "name": app.name,
        "type": app.type,
        "is_listed": app.is_listed,
        "review_count": func.coalesce(summary.review_count, 0),
        "percent_positive": case((summary.review_count > 0, summary.percent_positive)),
        "positive": totals.positive,
        "negative": totals.negative,
        "counts_exact": totals.counts_exact,
        **scores(totals),
        "price": func.coalesce(price.original_price_in_cents, price.final_price_in_cents) / 100.0,
        "steam_release_date": func.substr(app.steam_release_date, 1, 10),
        "wishlist": exists().where(WishlistItem.appid == totals.appid),
        "followed": exists().where(FollowedApp.appid == totals.appid),
    }
    return (
        select(*labelled(columns))
        .select_from(totals)
        .join(app, app.appid == totals.appid)
        .outerjoin(summary, and_(summary.appid == totals.appid, summary.scope == "filtered"))
        .outerjoin(best, and_(best.appid == totals.appid, best.is_best.is_(True)))
        .outerjoin(
            price,
            and_(
                price.kind == best.kind,
                price.id == best.id,
                price.country == home_country,
                app.store_country == home_country,
            ),
        )
        .order_by(totals.appid)
    )
