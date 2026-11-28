"""
Turn a store item, a full entry, a light one or a short record, into rows.

This is the notebook's ``load_app`` (``steam-database.ipynb``, cell 4) on the typed models.
Every field is stored, checked against what the database derives in its place, or skipped
with a reason; whatever is left is reported, so a field Steam adds is never lost unnoticed.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal

from steam_manager.db.schema.apps import App, AppText
from steam_manager.db.schema.classification import (
    AppCategory,
    AppCompatibilityTest,
    AppContentDescriptor,
    AppDocument,
    AppGenre,
    AppInteractiveElement,
    AppLanguage,
    AppManufacturer,
    AppRatingDescriptor,
    AppTag,
)
from steam_manager.db.schema.creators import AppCredit, AppFeaturedCreator, Creator
from steam_manager.db.schema.lookups import AgeRating, Anticheat, RatingAgency, ReviewScore
from steam_manager.db.schema.media import AppAsset, AppScreenshot, AppTrailer, Trailer, TrailerFile
from steam_manager.db.schema.offers import (
    AppOffer,
    AppPackageGroup,
    Offer,
    OfferApp,
    OfferCategory,
    OfferContentDescriptor,
    OfferDiscount,
    OfferPrice,
)
from steam_manager.db.schema.relations import (
    AppDlc,
    AppRelated,
    SeasonPassMilestone,
    SeasonPassMilestoneDate,
    SeasonPassMilestoneText,
)
from steam_manager.db.schema.requirements import AppPlatformRequirement, AppSystemRequirement
from steam_manager.db.schema.reviews import AppReviewSummary
from steam_manager.db.schema.store_lists import (
    AppEula,
    AppLink,
    AppOptinTag,
    AppPressReview,
    AppPurchaseNote,
    AppSalePage,
    AppSection,
    AppSteamAward,
)
from steam_manager.loader.details import extra_details
from steam_manager.loader.media import assets, screenshots, trailers
from steam_manager.loader.offers import (
    CATEGORY_LISTS,
    SHORT_RECORD_FIELDS,
    included_offer,
    purchase_option,
)
from steam_manager.loader.rows import Findings, Rows, iso, join, positioned, read_columns

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from steam_manager.db.schema import SteamBase
    from steam_manager.loader.rows import Columns
    from steam_manager.steam.models.details import (
        ExtraDetails,
    )
    from steam_manager.steam.models.store_item import (
        BasicInfo,
        GameRating,
        IncludedCreator,
        IncludedItems,
        IncludedOffer,
        Platforms,
        RelatedItems,
        Reviews,
        StoreItem,
    )

STORE_ITEM_TABLES: Final[tuple[type[SteamBase], ...]] = (
    App,
    AppText,
    AppCategory,
    AppTag,
    AppLanguage,
    AppContentDescriptor,
    AppReviewSummary,
    AppCredit,
    AppFeaturedCreator,
    AppGenre,
    AppDocument,
    AppManufacturer,
    AppInteractiveElement,
    AppRatingDescriptor,
    AppCompatibilityTest,
    AppLink,
    AppPurchaseNote,
    AppEula,
    AppPressReview,
    AppSection,
    AppSalePage,
    AppSteamAward,
    AppOptinTag,
    AppPackageGroup,
    AppOffer,
    AppRelated,
    AppDlc,
    SeasonPassMilestone,
    SeasonPassMilestoneDate,
    SeasonPassMilestoneText,
    AppAsset,
    AppScreenshot,
    AppTrailer,
    TrailerFile,
    AppPlatformRequirement,
    AppSystemRequirement,
)
"""The tables one app owns: its rows there are replaced whenever the app is loaded again."""

SHARED_TABLES: Final[tuple[type[SteamBase], ...]] = (
    Offer,
    OfferPrice,
    OfferDiscount,
    OfferApp,
    OfferCategory,
    OfferContentDescriptor,
    Creator,
    Trailer,
    ReviewScore,
    RatingAgency,
    AgeRating,
    Anticheat,
)
"""The tables whose rows many apps' store items describe, merged rather than replaced."""

DATE_COLUMNS: Final = (
    "steam_release_date",
    "original_release_date",
    "original_steam_release_date",
    "mac_release_date",
    "linux_release_date",
    "release_from_early_access_date",
)
"""The release fields that are dates, stored as the notebook's text."""

_ROLES: Final = (
    ("developers", "developer"),
    ("publishers", "publisher"),
    ("franchises", "franchise"),
)
_REVIEW_SCOPES: Final = (
    ("summary_filtered", "filtered"),
    ("summary_language_specific", "language"),
    ("summary_unfiltered", "unfiltered"),
)


@dataclass(frozen=True, slots=True)
class CreditRef:
    """A credit as a store item names it; the writer gives it its id."""

    role: str
    """``developer``, ``publisher`` or ``franchise``."""
    position: int
    """Its place among the app's credits in that role."""
    name: str
    """The name credited."""
    creator_id: int | None
    """The creator page, when the credit has one."""


@dataclass(slots=True)
class Described:
    """What a store item becomes: its rows, its findings, its credits and the records it nests."""

    item: StoreItem
    """The store item."""
    rows: Rows = field(default_factory=Rows)
    """Its rows, by table."""
    findings: Findings = field(default_factory=Findings)
    """Fields nothing stores, and derived values that didn't follow."""
    credits: list[CreditRef] = field(default_factory=list)
    """Its developers, publishers and franchises."""
    nested: list[StoreItem] = field(default_factory=list)
    """The short records of other apps it holds, which fill gaps."""


def describe(
    item: StoreItem, *, country: str, category_types: Mapping[int, int], path: str = ""
) -> Described:
    """
    Turn a store item into rows; ``is_listed`` and ``current_players`` are left to the writer.

    :param item: The store item.
    :param country: The store country that sent it, under which its prices are kept.
    :param category_types: Each store category's list, by id, to check the item's lists.
    :param path: Where the item sits in its answer: ``""``, or the place of a short record.
    :return: Its rows and findings, its credits and the short records it holds.
    :raise ValueError: When the item lacks a value a row needs, such as a credit's name: the
        answer is malformed.
    """
    appid = item.id
    found = Described(item)
    rows, findings = found.rows, found.findings
    findings.same("item_type", item.item_type, 0)
    findings.same("visible", item.visible, item.success == 1)
    findings.same(
        "store_url_slug",
        item.store_url_slug or None,
        (item.store_url_path or "").rsplit("/", 1)[-1] or None,
    )
    app: Columns = {
        "appid": appid,
        "name": item.name or None,  # blank when Steam has nothing, not a name
        "type": item.type,
        "success": item.success,
        "store_url_path": item.store_url_path or None,
        "store_url_path_override": item.store_url_path_override,
        "store_country": country,
        "is_free": item.is_free,
        "unlisted": item.unlisted,
        "unavailable_for_country_restriction": item.unvailable_for_country_restriction,
    }
    _classification(appid, item, path, rows, findings, category_types=category_types)
    app["counts_all_purchases"] = _reviews(
        appid, item.reviews, join(path, "reviews"), rows, findings
    )
    text: Columns = {"full_description_bbcode": item.full_description_bbcode}
    text |= _basic_info(appid, item.basic_info, join(path, "basic_info"), found)
    app |= _release(item, path, findings)
    app |= read_columns(
        item.free_weekend,
        join(path, "free_weekend"),
        ("text", "appid"),
        findings,
        prefix="free_weekend_",
        used=("start_time", "end_time"),
    )
    if item.free_weekend is not None:
        app["free_weekend_start"] = iso(item.free_weekend.start_time)
        app["free_weekend_end"] = iso(item.free_weekend.end_time)
    app |= _platforms(item.platforms, join(path, "platforms"), findings)
    app |= _rating(
        appid,
        item.game_rating,
        join(path, "game_rating"),
        rows,
        findings,
        extra=item.extra_details,
    )
    nested = item.included_items.included_apps if item.included_items else ()
    columns, texts = extra_details(
        appid, item.extra_details, join(path, "extra_details"), rows, findings, nested=nested
    )
    app |= columns
    text |= texts
    _store_lists(appid, item, path, rows, findings)
    _offers(appid, item, path, rows, findings, country=country)
    found.nested.extend(
        _included(appid, item.included_items, join(path, "included_items"), country, found)
    )
    app["parent_appid"] = _related(
        appid, item.related_items, join(path, "related_items"), rows, findings
    )
    app |= assets(appid, item.assets, item.assets_without_overrides, rows, findings)
    screenshots(appid, item.screenshots, rows, findings)
    trailers(appid, item.trailers, rows, findings)
    if any(text.values()):
        rows.add(AppText, appid=appid, **text)
    rows.add(App, **app)
    findings.rest(
        item,
        path,
        {
            "id",
            "appid",  # 0 on delisted apps, so id is the one to trust
            "item_type",  # checked
            "visible",  # checked
            "success",
            "name",
            "type",
            "store_url_path",
            "store_url_slug",  # checked
            "store_url_path_override",
            "is_free",
            "unlisted",
            "unvailable_for_country_restriction",
            "is_early_access",
            "is_coming_soon",
            "full_description_bbcode",
            "tagids",
            "content_descriptorids",
            "categories",
            "tags",
            "supported_languages",
            "reviews",
            "basic_info",
            "release",
            "free_weekend",
            "platforms",
            "game_rating",
            "links",
            "purchase_notes",
            "optin_registration_tags",
            "package_groups",
            "purchase_options",
            "best_purchase_option",
            "included_items",
            "related_items",
            "assets",
            "assets_without_overrides",
            "screenshots",
            "trailers",
            "extra_details",
        },
    )
    return found


def _classification(
    appid: int,
    item: StoreItem,
    path: str,
    rows: Rows,
    findings: Findings,
    *,
    category_types: Mapping[int, int],
) -> None:
    """
    Turn an app's store categories, tags, languages and content descriptors into rows.

    :param appid: The app.
    :param item: Its store item.
    :param path: Where the item sits in its answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and lists that disagree are counted.
    :param category_types: Each store category's list, by id.
    """
    categories = item.categories
    for list_type, key in enumerate(CATEGORY_LISTS, 1):
        for categoryid in getattr(categories, key) if categories else ():
            findings.same(
                "store_category.type", category_types.get(categoryid, list_type), list_type
            )
            rows.add(AppCategory, appid=appid, categoryid=categoryid)
    findings.rest(categories, join(path, "categories"), CATEGORY_LISTS)
    for tag in item.tags:
        findings.rest(tag, join(path, "tags[]"), {"tagid", "weight"})
        rows.add(AppTag, appid=appid, tagid=tag.tagid, weight=tag.weight)
    findings.same(
        "tagids",
        sorted(item.tagids),
        sorted(tag.tagid for tag in item.tags if tag.tagid is not None),
    )
    for language in item.supported_languages:
        names = ("elanguage", "eadditionallanguage", "supported", "full_audio", "subtitles")
        findings.rest(language, join(path, "supported_languages[]"), names)
        rows.add(AppLanguage, appid=appid, **{name: getattr(language, name) for name in names})
    for descriptor in item.content_descriptorids:
        rows.add(AppContentDescriptor, appid=appid, descriptorid=descriptor)


def _reviews(
    appid: int, reviews: Reviews | None, at: str, rows: Rows, findings: Findings
) -> bool | None:
    """
    Turn an app's review summaries into rows.

    :param appid: The app.
    :param reviews: Its summaries.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and labels that don't follow are counted.
    :return: Whether the counts include people who didn't buy the app on Steam.
    """
    if reviews is None:
        return None
    for key, scope in _REVIEW_SCOPES:
        summary = getattr(reviews, key)
        if summary is None:
            continue
        findings.rest(
            summary,
            join(at, key),
            {"review_count", "percent_positive", "review_score", "review_score_label"},
        )
        count, score, label = (
            summary.review_count,
            summary.review_score,
            summary.review_score_label,
        )
        if score:
            rows.add(ReviewScore, review_score=score, label=label)
        elif score == 0:
            findings.same(
                "review_score_label",
                label,
                f"{count} user reviews" if count else "No user reviews",
            )
        rows.add(
            AppReviewSummary,
            appid=appid,
            scope=scope,
            review_count=count,
            percent_positive=summary.percent_positive,
            review_score=score,
        )
    findings.rest(reviews, at, {key for key, _ in _REVIEW_SCOPES} | {"counts_all_purchases"})
    return reviews.counts_all_purchases


def _basic_info(appid: int, basic: BasicInfo | None, at: str, found: Described) -> Columns:
    """
    Turn an app's credits and featured creators into rows, and return its short texts.

    :param appid: The app.
    :param basic: Its basic info.
    :param at: Where it sits in the answer.
    :param found: What the item becomes; its credits, rows and findings grow.
    :return: The ``app_text`` columns ``short_description`` and ``capsule_headline``.
    :raise ValueError: When a credit has no name.
    """
    if basic is None:
        return {}
    findings = found.findings
    for key, role in _ROLES:
        for position, credit in enumerate(getattr(basic, key)):
            where = join(at, f"{key}[]")
            findings.rest(credit, where, {"name", "creator_clan_account_id"})
            if credit.name is None:
                message = f"{where} has no name"
                raise ValueError(message)
            found.credits.append(
                CreditRef(role, position, credit.name, credit.creator_clan_account_id or None)
            )
    for position, creator_id in enumerate(basic.featured_creator_home_clan_account_ids):
        found.rows.add(AppFeaturedCreator, appid=appid, position=position, creator_id=creator_id)
    if basic.first_franchise_clan_account_id is not None:  # sent since late 2026 only
        first = basic.franchises[0].creator_clan_account_id if basic.franchises else None
        findings.same(
            "basic_info.first_franchise_clan_account_id",
            basic.first_franchise_clan_account_id,
            first,
        )
    texts = ("short_description", "capsule_headline")
    return read_columns(
        basic,
        at,
        texts,
        findings,
        used=(
            "developers",
            "publishers",
            "franchises",
            "featured_creator_home_clan_account_ids",
            "first_franchise_clan_account_id",  # checked
        ),
    )


def _release(item: StoreItem, path: str, findings: Findings) -> Columns:
    """
    Read an app's release into columns, checking the flags Steam sends twice.

    :param item: The store item.
    :param path: Where the item sits in its answer.
    :param findings: Where fields nothing stores and flags that disagree are counted.
    :return: The release columns.
    """
    release = item.release
    early, soon = item.is_early_access, item.is_coming_soon
    names = (
        "release_from_early_access_style",
        "coming_soon_display",
        "custom_release_date_message",
        "is_preload",
    )
    columns = read_columns(
        release,
        join(path, "release"),
        names,
        findings,
        used=(*DATE_COLUMNS, "is_early_access", "is_coming_soon"),
    )
    columns |= {name: iso(getattr(release, name, None)) for name in DATE_COLUMNS}
    columns["is_early_access"], columns["is_coming_soon"] = early, soon
    if release is not None:
        findings.same("is_early_access", early, release.is_early_access)
        findings.same("is_coming_soon", soon, release.is_coming_soon)
        if release.is_early_access is not None:
            columns["is_early_access"] = release.is_early_access
        if release.is_coming_soon is not None:
            columns["is_coming_soon"] = release.is_coming_soon
    return columns


def _platforms(platforms: Platforms | None, at: str, findings: Findings) -> Columns:
    """
    Read the systems and VR hardware an app supports into columns.

    :param platforms: What it runs on.
    :param at: Where that sits in the answer.
    :param findings: Where fields nothing stores are counted.
    :return: The platform and ``vr_`` columns.
    """
    vr = platforms.vr_support if platforms else None
    columns = read_columns(
        vr,
        join(at, "vr_support"),
        (
            "vrhmd",
            "vrhmd_only",
            "htc_vive",
            "oculus_rift",
            "windows_mr",
            "valve_index",
            "show_optional_vr_mode_notice",
        ),
        findings,
        prefix="vr_",
    )
    return columns | read_columns(
        platforms,
        at,
        (
            "windows",
            "mac",
            "steamos_linux",
            "steam_deck_compat_category",
            "steam_os_compat_category",
            "steam_frame_compat_category",
            "steam_machine_compat_category",
        ),
        findings,
        used=("vr_support",),
    )


def _rating(
    appid: int,
    rating: GameRating | None,
    at: str,
    rows: Rows,
    findings: Findings,
    *,
    extra: ExtraDetails | None,
) -> Columns:
    """
    Turn an app's age rating into columns and rows, checking what it repeats of the details.

    :param appid: The app.
    :param rating: Its age rating.
    :param at: Where it sits in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and repeats that disagree are counted.
    :param extra: The extra details, which hold the interactive elements and survey notes.
    :return: The rating columns.
    """
    interactive = extra.interactive_elements if extra else ()
    for element in interactive:
        rows.add(AppInteractiveElement, appid=appid, element=element)
    if rating is None:
        return {}
    if rating.survey_interactive_elements:
        findings.same(
            "game_rating.survey_interactive_elements",
            rating.survey_interactive_elements,
            interactive,
        )
    if rating.content_survey_notes:
        findings.same(
            "game_rating.content_survey_notes",
            rating.content_survey_notes,
            extra.content_survey_notes if extra else None,
        )
    for position, descriptor in enumerate(rating.descriptors):
        rows.add(AppRatingDescriptor, appid=appid, position=position, descriptor=descriptor)
    agency, name = rating.agency, rating.rating or None
    if agency is not None and rating.type:
        rows.add(RatingAgency, agency=agency, rating_type=rating.type)
    if agency is not None and name and rating.image_url:
        rows.add(AgeRating, agency=agency, rating=name, image_url=rating.image_url)
    columns = read_columns(
        rating,
        at,
        (
            "agency",
            "agency_rating",
            "required_age",
            "use_age_gate",
            "banned",
            "esrb_online_music_not_rated",
            "esrb_online_interactions_not_rated",
        ),
        findings,
        used=(
            "type",
            "rating",
            "interactive_elements",
            "descriptors",
            "image_url",
            "survey_interactive_elements",  # checked
            "content_survey_notes",  # checked
        ),
    )
    return columns | {"rating": name, "rating_interactive_elements": rating.interactive_elements}


def _store_lists(appid: int, item: StoreItem, path: str, rows: Rows, findings: Findings) -> None:
    """
    Turn the lists on an app's store page into rows: links, notes, sign-ups and package groups.

    :param appid: The app.
    :param item: Its store item.
    :param path: Where the item sits in its answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    positioned(
        appid,
        AppLink,
        item.links,
        rows,
        findings,
        at=join(path, "links[]"),
        columns={"link_type": "link_type", "url": "url", "text": "link_text"},
    )
    positioned(
        appid,
        AppPurchaseNote,
        item.purchase_notes,
        rows,
        findings,
        at=join(path, "purchase_notes[]"),
        columns={"type": "type", "highlighted": "highlighted", "text_bbcode": "text_bbcode"},
    )
    for optin in item.optin_registration_tags:
        findings.rest(optin, join(path, "optin_registration_tags[]"), {"optin_name", "values"})
        for value in optin.values:
            rows.add(AppOptinTag, appid=appid, optin_name=optin.optin_name, value=value)
    for group in item.package_groups:
        names = (
            "name",
            "display_type",
            "heading",
            "dropdown_title",
            "dropdown_description_bbcode",
        )
        rows.add(
            AppPackageGroup,
            appid=appid,
            **read_columns(group, join(path, "package_groups[]"), names, findings),
        )


def _offers(
    appid: int, item: StoreItem, path: str, rows: Rows, findings: Findings, *, country: str
) -> None:
    """
    Turn the ways to buy an app into offers, prices and the app's list of offers.

    A light entry or a short record lists only its best option; it is added when the list of
    options lacks it, so its price is kept too.

    :param appid: The app.
    :param item: Its store item.
    :param path: Where the item sits in its answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :param country: The store country that quoted the prices.
    """
    best = item.best_purchase_option
    best_key = (best.packageid, best.bundleid) if best else None
    options = [(option, join(path, "purchase_options[]")) for option in item.purchase_options]
    if best and all((option.packageid, option.bundleid) != best_key for option, _ in options):
        options.append((best, join(path, "best_purchase_option")))
    for option, where in options:
        kind, id_ = purchase_option(option, where, country, rows, findings)
        rows.add(
            AppOffer,
            appid=appid,
            kind=kind,
            id=id_,
            package_group=option.package_group,
            is_edition=option.is_edition,
            is_best=(option.packageid, option.bundleid) == best_key,
        )


def _included(
    appid: int, included: IncludedItems | None, at: str, country: str, found: Described
) -> Sequence[StoreItem]:
    """
    Turn the short records an item holds into offers and creators, and list its other apps.

    :param appid: The app.
    :param included: The short records.
    :param at: Where they sit in the answer.
    :param country: The store country that sent them.
    :param found: What the item becomes; its rows and findings grow.
    :return: The short records of other apps, loaded only where nothing better describes them.
    :raise ValueError: When a record has no id.
    """
    if included is None:
        return ()
    rows, findings = found.rows, found.findings
    offers: tuple[tuple[Sequence[IncludedOffer], Literal["package", "bundle"]], ...] = (
        (included.included_packages, "package"),
        (included.included_bundles, "bundle"),
    )
    for records, kind in offers:
        for record in records:
            included_offer(
                record, join(at, f"included_{kind}s[]"), country, rows, findings, kind=kind
            )
    for creator in included.included_creators:
        _creator(creator, join(at, "included_creators[]"), rows, findings)
    for app in included.included_apps:
        rows.add(AppRelated, appid=appid, kind="included_app", related_appid=app.id)
    findings.rest(
        included,
        at,
        {"included_apps", "included_packages", "included_bundles", "included_creators"},
    )
    return included.included_apps


def _creator(creator: IncludedCreator, at: str, rows: Rows, findings: Findings) -> None:
    """
    Turn the short record of a creator page into its row.

    :param creator: The record.
    :param at: Where it sits in the answer.
    :param rows: Where the row goes.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :raise ValueError: When the record has no id.
    """
    if creator.id is None:
        message = f"{at} has no id"
        raise ValueError(message)
    findings.same("creator.item_type", creator.item_type, 5)
    findings.same("creator.visible", creator.visible, creator.success == 1)
    rows.add(
        Creator,
        creator_id=creator.id,
        name=creator.name or None,
        store_url_path=creator.store_url_path or None,
        store_url_slug=creator.store_url_slug or None,
        game_count=creator.game_count,
    )
    # item_type and visible are checked, and visible follows from success.
    findings.rest(creator, at, {*SHORT_RECORD_FIELDS, "game_count"})


def _related(
    appid: int, related: RelatedItems | None, at: str, rows: Rows, findings: Findings
) -> int | None:
    """
    Turn the apps an app points at into rows: demos, playtests, DLC parents and engines.

    :param appid: The app.
    :param related: Its related apps.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and lists that disagree are counted.
    :return: The app it belongs to, for a DLC, demo or soundtrack.
    """
    if related is None:
        return None
    for key, kind, ids in (
        ("demos", "demo", "demo_appid"),
        ("standalone_demos", "standalone_demo", "standalone_demo_appid"),
    ):
        entries = getattr(related, key)
        findings.same(
            f"related_items.{ids}",
            sorted(getattr(related, ids)),
            sorted(entry.appid for entry in entries if entry.appid is not None),
        )
        for entry in entries:
            findings.rest(entry, join(at, f"{key}[]"), {"appid", "label", "show_above_purchase"})
            rows.add(
                AppRelated,
                appid=appid,
                kind=kind,
                related_appid=entry.appid,
                label=entry.label,
                show_above_purchase=entry.show_above_purchase,
            )
    for playtest in related.playtests:
        findings.rest(playtest, join(at, "playtests[]"), {"appid", "is_open"})
        rows.add(
            AppRelated,
            appid=appid,
            kind="playtest",
            related_appid=playtest.appid,
            is_open=playtest.is_open,
        )
    for other in related.dlc_parent_appids:
        rows.add(AppRelated, appid=appid, kind="dlc_parent", related_appid=other)
    for other in related.provides_engine_appid:
        rows.add(AppRelated, appid=appid, kind="engine", related_appid=other)
    f2p = related.related_f2p
    if f2p is not None:
        findings.rest(f2p, join(at, "related_f2p"), {"appid", "header_text", "description_text"})
        rows.add(
            AppRelated,
            appid=appid,
            kind="related_f2p",
            related_appid=f2p.appid,
            header_text=f2p.header_text,
            description_text=f2p.description_text,
        )
    findings.rest(
        related,
        at,
        {
            "parent_appid",
            "demos",
            "standalone_demos",
            "demo_appid",  # checked
            "standalone_demo_appid",  # checked
            "playtests",
            "dlc_parent_appids",
            "related_f2p",
            "provides_engine_appid",
        },
    )
    return related.parent_appid
