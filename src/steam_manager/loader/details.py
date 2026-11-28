"""Turn an app's extra details into columns, long texts and rows."""

from typing import TYPE_CHECKING, Final

from steam_manager.db.schema.classification import (
    AppCompatibilityTest,
    AppDocument,
    AppGenre,
    AppManufacturer,
)
from steam_manager.db.schema.lookups import Anticheat
from steam_manager.db.schema.media import AppTrack
from steam_manager.db.schema.relations import (
    AppDlc,
    AppRelated,
    SeasonPassMilestone,
    SeasonPassMilestoneDate,
    SeasonPassMilestoneText,
)
from steam_manager.db.schema.requirements import AppPlatformRequirement, AppSystemRequirement
from steam_manager.db.schema.store_lists import (
    AppEula,
    AppPressReview,
    AppSalePage,
    AppSection,
    AppSteamAward,
)
from steam_manager.loader.rows import iso, join, positioned, read_columns

if TYPE_CHECKING:
    from collections.abc import Sequence

    from steam_manager.loader.rows import Columns, Findings, Rows
    from steam_manager.steam.models.details import (
        DlcForPurchase,
        ExtraDetails,
        HardwareCompatibility,
        LinksAndInfo,
        SeasonPass,
        SystemRequirements,
    )
    from steam_manager.steam.models.store_item import StoreItem

DEVICES: Final = ("steam_deck", "steam_os", "steam_machine", "steam_frame")
"""The devices of Steam's compatibility reviews."""


_EXTRA_COLUMNS: Final = (
    "vetted",
    "has_community_hub",
    "points_shop_eligible",
    "controller_wizard_complete",
    "item_store_eligible",
    "item_store_show_featured",
    "no_mouse_keyboard_support",
    "refund_checks_ea_playtime",
    "drm_third_party_type",
    "user_account_third_party",
    "user_account_third_party_link_to_steam",
    "running_time_minutes",
)


_EXTRA_TEXTS: Final = (
    "legal_notice_bbcode",
    "partner_awards_bbcode",
    "content_survey_notes",
    "content_survey_ai_notes",
)


def extra_details(
    appid: int,
    extra: ExtraDetails | None,
    at: str,
    rows: Rows,
    findings: Findings,
    *,
    nested: Sequence[StoreItem],
) -> tuple[Columns, Columns]:
    """
    Turn an app's extra details into columns, long texts and rows.

    :param appid: The app.
    :param extra: Its extra details.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :param nested: The short records of other apps in the same answer.
    :return: The ``app`` columns and the ``app_text`` columns.
    """
    if extra is None:
        return {}, {}
    columns = _links_and_info(
        appid, extra.links_and_info, join(at, "links_and_info"), rows, findings
    )
    columns |= read_columns(
        extra.metacritic,
        join(at, "metacritic"),
        ("score", "url", "always_show"),
        findings,
        prefix="metacritic_",
    )
    anticheat = extra.anticheat
    if anticheat is not None and anticheat.name:
        rows.add(Anticheat, name=anticheat.name, name_loc=anticheat.name_loc)
    columns |= read_columns(
        anticheat,
        join(at, "anticheat"),
        ("name", "kernel_mode", "uninstall_completely", "boot_protection", "boot_protection_name"),
        findings,
        prefix="anticheat_",
        used=("name_loc",),
    )
    columns |= read_columns(
        extra.ai_generation_service,
        join(at, "ai_generation_service"),
        ("name", "url"),
        findings,
        prefix="ai_generation_service_",
    )
    columns |= {name: getattr(extra, name) for name in _EXTRA_COLUMNS}
    columns["dlc_formatted_total_price"], columns["dlc_count"] = _dlc(
        appid, extra.dlc_for_purchase, join(at, "dlc_for_purchase"), rows, findings, nested=nested
    )
    texts = read_columns(
        extra.early_access,
        join(at, "early_access"),
        (
            "description_bbcode",
            "why_bbcode",
            "how_long_bbcode",
            "full_version_bbcode",
            "current_state_bbcode",
            "pricing_bbcode",
            "community_bbcode",
        ),
        findings,
        prefix="early_access_",
    )
    texts |= {name: getattr(extra, name) for name in _EXTRA_TEXTS}
    album = extra.music_album
    texts |= read_columns(
        album,
        join(at, "music_album"),
        ("artist", "composer", "label", "other_credits"),
        findings,
        prefix="music_album_",
        used=("tracks",),
    )
    positioned(
        appid,
        AppTrack,
        album.tracks if album else (),
        rows,
        findings,
        at=join(at, "music_album.tracks[]"),
        columns={
            name: name
            for name in (
                "disc_number",
                "track_number",
                "name",
                "other_name",
                "duration_seconds",
            )
        },
    )
    _season_pass(appid, extra.season_pass, join(at, "season_pass"), rows, findings)
    _requirements(
        appid, extra.system_requirements, join(at, "system_requirements"), rows, findings
    )
    columns |= _compatibility(
        appid, extra.hardware_compatibility, join(at, "hardware_compatibility"), rows, findings
    )
    positioned(
        appid,
        AppEula,
        extra.eula,
        rows,
        findings,
        at=join(at, "eula[]"),
        columns={"name": "name", "url": "url"},
    )
    positioned(
        appid,
        AppPressReview,
        extra.press_review,
        rows,
        findings,
        at=join(at, "press_review[]"),
        columns={"quote": "quote", "score": "score", "site": "site", "url": "url"},
    )
    positioned(
        appid,
        AppSection,
        extra.section,
        rows,
        findings,
        at=join(at, "section[]"),
        columns={"label": "label", "banner": "banner", "content_bbcode": "content_bbcode"},
    )
    positioned(
        appid,
        AppSalePage,
        extra.sale_pages,
        rows,
        findings,
        at=join(at, "sale_pages[]"),
        columns={"clan_account_id": "clan_account_id", "event_gid": "event_gid"},
    )
    for position, award in enumerate(extra.steam_award):
        findings.rest(award.localization, join(at, "steam_award[].localization"), {"title"})
        findings.rest(award, join(at, "steam_award[]"), {"voteid", "award_year", "localization"})
        rows.add(
            AppSteamAward,
            appid=appid,
            position=position,
            voteid=award.voteid,
            award_year=award.award_year,
            title=award.localization.title if award.localization else None,
        )
    findings.rest(
        extra,
        at,
        {
            *_EXTRA_COLUMNS,
            *_EXTRA_TEXTS,
            "interactive_elements",  # stored with the rating
            "links_and_info",
            "metacritic",
            "anticheat",
            "ai_generation_service",
            "early_access",
            "eula",
            "press_review",
            "section",
            "sale_pages",
            "steam_award",
            "season_pass",
            "system_requirements",
            "hardware_compatibility",
            "dlc_for_purchase",
            "music_album",
        },
    )
    return columns, texts


def _links_and_info(
    appid: int, info: LinksAndInfo | None, at: str, rows: Rows, findings: Findings
) -> Columns:
    """
    Turn an app's links and facts into columns, and its genres, documents and makers into rows.

    :param appid: The app.
    :param info: Its links and facts.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    :return: The columns.
    """
    if info is not None:
        for position, genreid in enumerate(info.genreids):
            rows.add(AppGenre, appid=appid, genreid=genreid, position=position)
        for document in info.available_documents:
            rows.add(AppDocument, appid=appid, document=document)
        for position, name in enumerate(info.manufacturers):
            rows.add(AppManufacturer, appid=appid, position=position, name=name)
    return read_columns(
        info,
        at,
        (
            "website",
            "stats_url",
            "online_manual_url",
            "privacy_policy_url",
            "health_warning_url",
            "achievements_visible",
            "achievement_count",
        ),
        findings,
        used=("genreids", "available_documents", "manufacturers"),
    )


def _dlc(
    appid: int,
    dlc: DlcForPurchase | None,
    at: str,
    rows: Rows,
    findings: Findings,
    *,
    nested: Sequence[StoreItem],
) -> tuple[str | None, int | None]:
    """
    Turn the DLC an app's store page offers into rows, checking what follows from the answer.

    :param appid: The app.
    :param dlc: The DLC on sale.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores and derived values that differ are counted.
    :param nested: The short records of other apps in the same answer, which hold each DLC's
        content descriptors.
    :return: What all the DLC cost, as the store shows it, and how many there are: Steam lists
        200 at most, so the count doesn't follow from the list.
    """
    if dlc is None:
        return None, None
    descriptors: dict[int | None, list[int]] = {
        app.id: sorted(app.content_descriptorids) for app in nested
    }
    for position, offer in enumerate(dlc.dlc):
        findings.rest(
            offer,
            join(at, "dlc[]"),
            {"appid", "packageid", "highlight_reason", "content_descriptorids"},
        )
        rows.add(
            AppDlc,
            appid=appid,
            dlc_appid=offer.appid,
            position=position,
            packageid=offer.packageid,
            highlight_reason=offer.highlight_reason,
        )
        findings.same(
            "dlc_for_purchase.content_descriptorids",
            sorted(offer.content_descriptorids),
            descriptors.get(offer.appid, []),
        )
    findings.rest(dlc, at, {"dlc", "dlc_count", "formatted_total_price"})
    return dlc.formatted_total_price, dlc.dlc_count


def _season_pass(
    appid: int, season: SeasonPass | None, at: str, rows: Rows, findings: Findings
) -> None:
    """
    Turn an app's season pass into rows: its milestones, their dates and texts, and its app.

    :param appid: The app.
    :param season: Its season pass.
    :param at: Where it sits in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    if season is None:
        return
    for milestone in season.milestones:
        key = {"appid": appid, "milestone_id": milestone.milestone_id}
        for position, date in enumerate(milestone.dates):
            where = join(at, "milestones[].dates[]")
            findings.rest(date, where, {"coming_soon_display_type", "rtime"})
            rows.add(
                SeasonPassMilestoneDate,
                **key,
                position=position,
                coming_soon_display_type=date.coming_soon_display_type,
                rtime=iso(date.rtime),
            )
        for field_name, kind in (("title", "title"), ("milestone_desc", "description")):
            for text in getattr(milestone, field_name):
                where = join(at, f"milestones[].{field_name}[]")
                findings.rest(text, where, {"language", "localized_string"})
                rows.add(
                    SeasonPassMilestoneText,
                    **key,
                    kind=kind,
                    language=text.language,
                    localized_string=text.localized_string,
                )
        rows.add(
            SeasonPassMilestone,
            **key,
            milestone_appid=milestone.appid,
            coming_soon_appid=milestone.coming_soon_appid,
            event_gid=milestone.event_gid,
            rtime_complete=iso(milestone.rtime_complete),
            shipped=milestone.shipped,
            backfilled_release=milestone.backfilled_release,
        )
        findings.rest(
            milestone,
            join(at, "milestones[]"),
            {
                "milestone_id",
                "appid",
                "coming_soon_appid",
                "event_gid",
                "rtime_complete",
                "shipped",
                "backfilled_release",
                "dates",
                "title",
                "milestone_desc",
            },
        )
    if season.appid:
        rows.add(AppRelated, appid=appid, kind="season_pass", related_appid=season.appid)
    findings.rest(season, at, {"appid", "milestones"})


def _requirements(
    appid: int, requirements: SystemRequirements | None, at: str, rows: Rows, findings: Findings
) -> None:
    """
    Turn an app's requirements into a row per platform and one per platform and tier.

    :param appid: The app.
    :param requirements: Its requirements.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    names = (
        "os_version",
        "os_version_unsupported",
        "processor",
        "graphics",
        "directx",
        "sound_card",
        "notes",
        "legacy_bbcode",
        "broadband",
        "vr_support",
    )
    for platform in requirements.platforms if requirements else ():
        for tier in ("minimum", "recommended"):
            needs = getattr(platform, tier)
            if needs is None:
                continue
            where = join(at, f"platforms[].{tier}")
            values = read_columns(
                needs, where, names, findings, used=("memory", "storage", "storage_hq")
            )
            for amount in ("memory", "storage", "storage_hq"):
                values |= read_columns(
                    getattr(needs, amount),
                    f"{where}.{amount}",
                    ("amount", "units"),
                    findings,
                    prefix=f"{amount}_",
                )
            rows.add(
                AppSystemRequirement, appid=appid, platform=platform.platform, tier=tier, **values
            )
        rows.add(
            AppPlatformRequirement,
            appid=appid,
            **read_columns(
                platform,
                join(at, "platforms[]"),
                ("platform", "requires_64bit", "requires_apple_silicon", "unsupported_os_note"),
                findings,
                used=("minimum", "recommended"),
            ),
        )
    findings.rest(requirements, at, {"platforms"})


def _compatibility(
    appid: int, tests: HardwareCompatibility | None, at: str, rows: Rows, findings: Findings
) -> Columns:
    """
    Turn the results of Steam's compatibility reviews into rows, per device in Steam's order.

    :param appid: The app.
    :param tests: The results.
    :param at: Where they sit in the answer.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    :return: The columns: the Steam Deck review's announcement.
    """
    for device in DEVICES if tests else ():
        for position, test in enumerate(getattr(tests, f"{device}_tests")):
            findings.rest(test, join(at, f"{device}_tests[]"), {"display_type", "loc_token"})
            rows.add(
                AppCompatibilityTest,
                appid=appid,
                device=device,
                position=position,
                display_type=test.display_type,
                loc_token=test.loc_token,
            )
    return read_columns(
        tests,
        at,
        ("steam_deck_blog_url",),
        findings,
        used=[f"{device}_tests" for device in DEVICES],
    )
