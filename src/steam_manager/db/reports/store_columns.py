"""
The store columns the wishlist and followed reports share, as the notebook's sheet tabs have them.

Each column keeps its tab's name, dotted ones such as ``vr_support.vrhmd`` included, and lists
are JSON, blank when empty, as the CSVs the tabs came from had them. Prices show only for apps
the home store described, and only in its currency: an app another store described shows that
store's data and no price, even when its offer has a price at home.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from sqlalchemy import Integer, aggregate_order_by, and_, case, cast, func, join, select
from sqlalchemy.orm import aliased

from steam_manager.db.reports.scores import labelled, score_label
from steam_manager.db.schema.apps import App, AppText
from steam_manager.db.schema.classification import (
    AppCategory,
    AppContentDescriptor,
    AppDocument,
    AppGenre,
    AppInteractiveElement,
    AppManufacturer,
)
from steam_manager.db.schema.creators import AppCredit, Credit
from steam_manager.db.schema.lookups import Anticheat, Genre, RatingAgency, StoreCategory
from steam_manager.db.schema.offers import AppOffer, Offer, OfferPrice
from steam_manager.db.schema.relations import AppRelated
from steam_manager.db.schema.reviews import AppReviewSummary, AppReviewTotal
from steam_manager.db.schema.store_lists import AppSteamAward

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement, FromClause, SQLColumnExpression

    from steam_manager.db.reports.scores import Columns, Report
    from steam_manager.db.schema.account import FollowedApp, WishlistItem

__all__ = [
    "Store",
    "content_descriptors",
    "epoch",
    "genres",
    "json_rows",
    "related_ids",
    "store_columns",
]


# One field per table the notebook's store query joins, so ten is the query's own size.
@dataclass(frozen=True)
class Store:  # pylint: disable=too-many-instance-attributes
    """The tables a store report reads about each app it lists, under the notebook's aliases."""

    listed: type[App]
    """The app the list names (``n``), which always exists."""
    app: type[App]
    """The same app's store data (``a``)."""
    text: type[AppText]
    """Its long texts (``t``)."""
    filtered: type[AppReviewSummary]
    """Its review summary without the reviews Steam filters out (``f``)."""
    language: type[AppReviewSummary]
    """Its review summary in the profile's language (``l``)."""
    unfiltered: type[AppReviewSummary]
    """Its review summary over every review (``u``)."""
    best: type[AppOffer]
    """Its best offer (``o``)."""
    offer: type[Offer]
    """That offer (``x``)."""
    price: type[OfferPrice]
    """That offer's price in the home country (``p``)."""
    totals: type[AppReviewTotal]
    """Its review totals (``s``)."""

    @classmethod
    def aliases(cls) -> Self:
        """
        Make a fresh set of aliases for one report.

        :return: The aliases.
        """
        return cls(
            listed=aliased(App, name="n"),
            app=aliased(App, name="a"),
            text=aliased(AppText, name="t"),
            filtered=aliased(AppReviewSummary, name="f"),
            language=aliased(AppReviewSummary, name="l"),
            unfiltered=aliased(AppReviewSummary, name="u"),
            best=aliased(AppOffer, name="o"),
            offer=aliased(Offer, name="x"),
            price=aliased(OfferPrice, name="p"),
            totals=aliased(AppReviewTotal, name="s"),
        )

    def report(
        self,
        columns: Columns,
        listed: type[WishlistItem | FollowedApp],
        home_country: str,
    ) -> Report:
        """
        Select *columns* for every app on a list, joined to its store data.

        :param columns: The report's columns.
        :param listed: The list's alias (``w``).
        :param home_country: The profile's home country: prices join for apps it described.
        :return: The report's query.
        """
        app, best = self.app, self.best
        summaries = (
            (self.filtered, "filtered"),
            (self.language, "language"),
            (self.unfiltered, "unfiltered"),
        )
        query = (
            select(*labelled(columns))
            .select_from(listed)
            .join(self.listed, self.listed.appid == listed.appid)
            .outerjoin(app, app.appid == listed.appid)
            .outerjoin(self.text, self.text.appid == app.appid)
        )
        for summary, scope in summaries:
            query = query.outerjoin(
                summary, and_(summary.appid == app.appid, summary.scope == scope)
            )
        return (
            query.outerjoin(best, and_(best.appid == app.appid, best.is_best.is_(True)))
            .outerjoin(self.offer, and_(self.offer.kind == best.kind, self.offer.id == best.id))
            .outerjoin(
                self.price,
                and_(
                    self.price.kind == best.kind,
                    self.price.id == best.id,
                    self.price.country == home_country,
                    app.store_country == home_country,
                ),
            )
            .outerjoin(self.totals, self.totals.appid == self.listed.appid)
        )


def epoch(column: SQLColumnExpression[str | None]) -> ColumnElement[Any]:
    """
    Turn a stored date back into the epoch seconds Steam sent.

    :param column: The date, as ISO 8601 text.
    :return: The seconds, as an integer.
    """
    return cast(func.strftime("%s", column), Integer)


def json_rows(
    item: SQLColumnExpression[Any],
    order: SQLColumnExpression[Any],
    source: FromClause | type[Any],
    where: ColumnElement[bool],
) -> ColumnElement[Any]:
    """
    Gather a list as one JSON array, blank when it is empty, as the notebook's CSVs have it.

    :param item: Each element, as JSON or as a value JSON can hold.
    :param order: What orders the elements.
    :param source: The table or join the elements come from.
    :param where: What selects the app's elements.
    :return: The array.
    """
    gathered = aggregate_order_by(func.json_group_array(func.json(item)), order)
    return select(func.nullif(gathered, "[]")).select_from(source).where(where).scalar_subquery()


def _json_true(column: SQLColumnExpression[bool | None]) -> ColumnElement[Any]:
    """
    Write a flag as a JSON boolean, blank counting as false, as the notebook does.

    :param column: The flag.
    :return: ``true`` or ``false``, as JSON.
    """
    return func.json(case((column.is_(True), "true"), else_="false"))


def related_ids(app: type[App], kind: str) -> ColumnElement[Any]:
    """
    List the apps of one kind an app points at, as JSON.

    :param app: The app's alias.
    :param kind: The kind of link, such as ``demo``.
    :return: Their appids, in order.
    """
    return json_rows(
        AppRelated.related_appid,
        AppRelated.related_appid,
        AppRelated,
        and_(AppRelated.appid == app.appid, AppRelated.kind == kind),
    )


def _demos(app: type[App], kind: str) -> ColumnElement[Any]:
    """
    List an app's demos of one kind, as the store item writes them.

    :param app: The app's alias.
    :param kind: ``demo`` or ``standalone_demo``.
    :return: One JSON object per demo.
    """
    show = _json_true(AppRelated.show_above_purchase)
    item = case(
        (
            AppRelated.label.is_(None),
            func.json_object("appid", AppRelated.related_appid, "show_above_purchase", show),
        ),
        else_=func.json_object(
            "appid",
            AppRelated.related_appid,
            "label",
            AppRelated.label,
            "show_above_purchase",
            show,
        ),
    )
    return json_rows(
        item,
        AppRelated.related_appid,
        AppRelated,
        and_(AppRelated.appid == app.appid, AppRelated.kind == kind),
    )


def _playtests(app: type[App]) -> ColumnElement[Any]:
    """
    List an app's playtests, as the store item writes them.

    :param app: The app's alias.
    :return: One JSON object per playtest.
    """
    item = case(
        (AppRelated.is_open.is_(None), func.json_object("appid", AppRelated.related_appid)),
        else_=func.json_object(
            "appid", AppRelated.related_appid, "is_open", _json_true(AppRelated.is_open)
        ),
    )
    return json_rows(
        item,
        AppRelated.related_appid,
        AppRelated,
        and_(AppRelated.appid == app.appid, AppRelated.kind == "playtest"),
    )


def _related_field(
    app: type[App], kind: str, column: SQLColumnExpression[Any]
) -> ColumnElement[Any]:
    """
    Read one field of the single app of one kind an app points at.

    :param app: The app's alias.
    :param kind: ``related_f2p`` or ``season_pass``.
    :param column: The field of ``app_related``.
    :return: Its value.
    """
    return (
        select(column)
        .where(AppRelated.appid == app.appid, AppRelated.kind == kind)
        .scalar_subquery()
    )


def _credits(app: type[App], role: str) -> ColumnElement[Any]:
    """
    List an app's credits in one role, as the store item writes them.

    :param app: The app's alias.
    :param role: ``developer``, ``publisher`` or ``franchise``.
    :return: One JSON object per credit, with its creator page when there is one.
    """
    item = case(
        (Credit.creator_id.is_(None), func.json_object("name", Credit.name)),
        else_=func.json_object("name", Credit.name, "creator_clan_account_id", Credit.creator_id),
    )
    return json_rows(
        item,
        AppCredit.position,
        join(AppCredit, Credit, AppCredit.credit_id == Credit.credit_id),
        and_(AppCredit.appid == app.appid, AppCredit.role == role),
    )


def _interactive_elements(app: type[App]) -> ColumnElement[Any]:
    """
    List an app's interactive elements.

    :param app: The app's alias.
    :return: Steam's codes, in order.
    """
    return json_rows(
        AppInteractiveElement.element,
        AppInteractiveElement.element,
        AppInteractiveElement,
        AppInteractiveElement.appid == app.appid,
    )


def content_descriptors(app: type[App]) -> ColumnElement[Any]:
    """
    List an app's content descriptors.

    :param app: The app's alias.
    :return: Steam's codes, in order.
    """
    return json_rows(
        AppContentDescriptor.descriptorid,
        AppContentDescriptor.descriptorid,
        AppContentDescriptor,
        AppContentDescriptor.appid == app.appid,
    )


def genres(app: type[App]) -> ColumnElement[Any]:
    """
    Name an app's genres in Steam's order, an unnamed one by its id.

    :param app: The app's alias.
    :return: The names, comma-separated.
    """
    name = aggregate_order_by(
        func.group_concat(func.coalesce(Genre.name, AppGenre.genreid), ", "), AppGenre.position
    )
    return (
        select(name)
        .select_from(join(AppGenre, Genre, AppGenre.genreid == Genre.genreid))
        .where(AppGenre.appid == app.appid)
        .scalar_subquery()
    )


def _store_categories(app: type[App]) -> ColumnElement[Any]:
    """
    List an app's store categories by their internal names, in id order.

    :param app: The app's alias.
    :return: One JSON array, blank when the app has none.
    """
    names = aggregate_order_by(
        func.json_group_array(StoreCategory.internal_name), StoreCategory.categoryid
    )
    return (
        select(func.nullif(names, "[]"))
        .select_from(join(AppCategory, StoreCategory))
        .where(AppCategory.appid == app.appid)
        .scalar_subquery()
    )


def _slug(path: SQLColumnExpression[str | None]) -> ColumnElement[Any]:
    """
    Take the last part of a store path, as Steam's ``store_url_slug`` has it.

    :param path: The store path.
    :return: What follows its last slash.
    """
    return func.replace(path, func.rtrim(path, func.replace(path, "/", "")), "")


def store_columns(store: Store, home_country: str) -> dict[str, SQLColumnExpression[Any]]:
    """
    Build every store column, in the order of the notebook's sheet tabs.

    :param store: The report's aliases.
    :param home_country: The profile's home country.
    :return: The columns, the store categories last, where the tabs had one per store category.
    """
    a, t, o, x, p = store.app, store.text, store.best, store.offer, store.price
    f, lang, u = store.filtered, store.language, store.unfiltered
    free_weekend = case(
        (
            a.free_weekend_start.is_not(None),
            func.json_patch(
                func.json_object(
                    "start_time",
                    epoch(a.free_weekend_start),
                    "end_time",
                    epoch(a.free_weekend_end),
                ),
                func.json_object("text", a.free_weekend_text, "appid", a.free_weekend_appid),
            ),
        )
    )
    awards = json_rows(
        func.json_object(
            "voteid",
            AppSteamAward.voteid,
            "award_year",
            AppSteamAward.award_year,
            "localization",
            func.json_object("title", AppSteamAward.title),
        ),
        AppSteamAward.position,
        AppSteamAward,
        AppSteamAward.appid == a.appid,
    )
    return {
        "store_url_path": store.listed.store_url_path,
        "store_url_slug": _slug(store.listed.store_url_path),
        "type": a.type,
        "store_url_path_override": a.store_url_path_override,
        "unlisted": a.unlisted,
        "is_free": a.is_free,
        # Steam's spelling. Not sold at home, when another store described the app.
        "unvailable_for_country_restriction": case(
            (a.store_country != home_country, 1), else_=a.unavailable_for_country_restriction
        ),
        "free_weekend": free_weekend,
        "review_count": f.review_count,
        "percent_positive": f.percent_positive,
        "review_score": f.review_score,
        "review_score_label": score_label(f),
        "language_review_count": lang.review_count,
        "language_percent_positive": lang.percent_positive,
        "language_review_score": lang.review_score,
        "language_review_score_label": score_label(lang),
        "unfiltered_review_count": u.review_count,
        "unfiltered_percent_positive": u.percent_positive,
        "unfiltered_review_score": u.review_score,
        "unfiltered_review_score_label": score_label(u),
        "packageid": case((o.kind == "package", o.id)),
        "purchase_option_name": x.name,
        "final_price_in_cents": p.final_price_in_cents,
        "formatted_final_price": p.formatted_final_price,
        "user_can_purchase_as_gift": p.user_can_purchase_as_gift,
        "hide_discount_pct_for_compliance": p.hide_discount_pct_for_compliance,
        "included_game_count": p.included_game_count,
        "must_purchase_as_set": x.must_purchase_as_set,
        "package_group": o.package_group,
        "price_cannot_be_displayed_as_discount": p.price_cannot_be_displayed_as_discount,
        "free_with_master_sub_appid": x.free_with_master_sub_appid,
        "original_price_in_cents": p.original_price_in_cents,
        "formatted_original_price": p.formatted_original_price,
        "discount_pct": p.discount_pct,
        "bundleid": case((o.kind == "bundle", o.id)),
        "bundle_discount_pct": p.bundle_discount_pct,
        "price_before_bundle_discount": p.price_before_bundle_discount,
        "formatted_price_before_bundle_discount": p.formatted_price_before_bundle_discount,
        "combined_discount_pct": p.combined_discount_pct,
        "steam_release_date": a.steam_release_date,
        "original_release_date": a.original_release_date,
        "original_steam_release_date": a.original_steam_release_date,
        "is_coming_soon": a.is_coming_soon,
        "is_early_access": a.is_early_access,
        "custom_release_date_message": a.custom_release_date_message,
        "coming_soon_display": a.coming_soon_display,
        "mac_release_date": a.mac_release_date,
        "release_from_early_access_date": epoch(a.release_from_early_access_date),
        "release_from_early_access_style": a.release_from_early_access_style,
        "linux_release_date": a.linux_release_date,
        "is_preload": a.is_preload,
        "short_description": t.short_description,
        "publishers": _credits(a, "publisher"),
        "developers": _credits(a, "developer"),
        "franchises": _credits(a, "franchise"),
        "capsule_headline": t.capsule_headline,
        "windows": a.windows,
        "steam_deck_compat_category": a.steam_deck_compat_category,
        "steam_os_compat_category": a.steam_os_compat_category,
        "steam_frame_compat_category": a.steam_frame_compat_category,
        "steam_machine_compat_category": a.steam_machine_compat_category,
        "mac": a.mac,
        "steamos_linux": a.steamos_linux,
        "vr_support.vrhmd": a.vr_vrhmd,
        "vr_support.htc_vive": a.vr_htc_vive,
        "vr_support.oculus_rift": a.vr_oculus_rift,
        "vr_support.windows_mr": a.vr_windows_mr,
        "vr_support.valve_index": a.vr_valve_index,
        "vr_support.show_optional_vr_mode_notice": a.vr_show_optional_vr_mode_notice,
        "vr_support.vrhmd_only": a.vr_vrhmd_only,
        "demos": _demos(a, "demo"),
        "parent_appid": a.parent_appid,
        "dlc_parent_appids": related_ids(a, "dlc_parent"),
        "standalone_demos": _demos(a, "standalone_demo"),
        "playtests": _playtests(a),
        "related_f2p.appid": _related_field(a, "related_f2p", AppRelated.related_appid),
        "related_f2p.header_text": _related_field(a, "related_f2p", AppRelated.header_text),
        "related_f2p.description_text": _related_field(
            a, "related_f2p", AppRelated.description_text
        ),
        "rating": a.rating,
        "agency": a.agency,
        "banned": a.banned,
        "esrb_online_music_not_rated": a.esrb_online_music_not_rated,
        "esrb_online_interactions_not_rated": a.esrb_online_interactions_not_rated,
        "survey_interactive_elements": _interactive_elements(a),
        "required_age": a.required_age,
        "use_age_gate": a.use_age_gate,
        "agency_rating": a.agency_rating,
        "rating_type": select(RatingAgency.rating_type)
        .where(RatingAgency.agency == a.agency)
        .scalar_subquery(),
        "extra.vetted": a.vetted,
        "extra.has_community_hub": a.has_community_hub,
        "website": a.website,
        "extra.links_and_info.available_documents": json_rows(
            AppDocument.document, AppDocument.document, AppDocument, AppDocument.appid == a.appid
        ),
        "extra.links_and_info.genreids": json_rows(
            AppGenre.genreid, AppGenre.position, AppGenre, AppGenre.appid == a.appid
        ),
        "metacritic_score": a.metacritic_score,
        "metacritic_url": a.metacritic_url,
        "extra.metacritic.always_show": a.metacritic_always_show,
        "extra.interactive_elements": _interactive_elements(a),
        "extra.drm_third_party_type": a.drm_third_party_type,
        "extra.links_and_info.achievements_visible": a.achievements_visible,
        "achievement_count": a.achievement_count,
        "extra.points_shop_eligible": a.points_shop_eligible,
        "extra.controller_wizard_complete": a.controller_wizard_complete,
        "extra.anticheat.kernel_mode": a.anticheat_kernel_mode,
        "extra.anticheat.name": a.anticheat_name,
        "extra.anticheat.name_loc": select(Anticheat.name_loc)
        .where(Anticheat.name == a.anticheat_name)
        .scalar_subquery(),
        "extra.links_and_info.stats_url": a.stats_url,
        "extra.links_and_info.online_manual_url": a.online_manual_url,
        "extra.links_and_info.privacy_policy_url": a.privacy_policy_url,
        "extra.item_store_eligible": a.item_store_eligible,
        "extra.item_store_show_featured": a.item_store_show_featured,
        "extra.user_account_third_party": a.user_account_third_party,
        "extra.user_account_third_party_link_to_steam": a.user_account_third_party_link_to_steam,
        "extra.links_and_info.manufacturers": json_rows(
            func.json_quote(AppManufacturer.name),
            AppManufacturer.position,
            AppManufacturer,
            AppManufacturer.appid == a.appid,
        ),
        "extra.links_and_info.health_warning_url": a.health_warning_url,
        "extra.anticheat.uninstall_completely": a.anticheat_uninstall_completely,
        "extra.steam_award": awards,
        "extra.ai_generation_service.name": a.ai_generation_service_name,
        "extra.ai_generation_service.url": a.ai_generation_service_url,
        "extra.no_mouse_keyboard_support": a.no_mouse_keyboard_support,
        "extra.refund_checks_ea_playtime": a.refund_checks_ea_playtime,
        "extra.anticheat.boot_protection": a.anticheat_boot_protection,
        "extra.anticheat.boot_protection_name": a.anticheat_boot_protection_name,
        "extra.season_pass.appid": _related_field(a, "season_pass", AppRelated.related_appid),
        "store_categories": _store_categories(a),
    }
