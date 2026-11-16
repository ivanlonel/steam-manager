"""
The wishlist report: every wishlisted app, in Steam's order, with its store columns.

An app the home store didn't describe shows the store that did, named in ``store_country``,
with no price, and counts as not sold at home.
"""

from typing import TYPE_CHECKING

from sqlalchemy import case, exists, func, literal
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import coalesce

from steam_manager.db.reports.scores import history_total, scores
from steam_manager.db.reports.store_columns import Store, genres, store_columns
from steam_manager.db.schema.account import FollowedApp, WishlistItem
from steam_manager.db.schema.reviews import ReviewHistory

if TYPE_CHECKING:
    from steam_manager.db.reports.scores import Columns, Report

__all__ = ["wishlist"]


def wishlist(home_country: str) -> Report:
    """
    Build the wishlist report, ordered as Steam lists the wishlist: by priority, then position.

    :param home_country: The profile's home country.
    :return: The query behind ``v_wishlist``.
    """
    listed = aliased(WishlistItem, name="w")
    store = Store.aliases()
    app, named = store.app, store.listed
    success = coalesce(app.success, 15)
    order = (listed.priority.asc().nulls_last(), listed.position)
    ranked = scores(store.totals)
    columns: Columns = {
        "appid": listed.appid,
        "priority": listed.priority,
        "date_added": listed.date_added,
        "item_type": literal(0),
        "success": success,
        "visible": success == 1,
        "store_country": app.store_country,
        "original_sort_order": func.row_number().over(order_by=order),
        "name": named.name,
        "bayes_avg": ranked["bayes_avg"],
        "wilson_score": ranked["wilson_score"],
        **store_columns(store, home_country),
        # Steam's spelling. Not sold at home, unless the home store described the app.
        "unvailable_for_country_restriction": case(
            (app.store_country == home_country, app.unavailable_for_country_restriction),
            else_=1,
        ),
        "genres": genres(app),
        "is_followed": exists().where(FollowedApp.appid == named.appid),
        "hist_positive": history_total(ReviewHistory.recommendations_up, named.appid),
        "hist_negative": history_total(ReviewHistory.recommendations_down, named.appid),
        "current_players": named.current_players,
    }
    return store.report(columns, listed, home_country).order_by(*order)
