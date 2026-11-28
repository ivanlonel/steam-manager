"""Turn an app's images, screenshots and trailers into rows."""

import re
from typing import TYPE_CHECKING, Final

from steam_manager.db.schema.media import AppAsset, AppScreenshot, AppTrailer, Trailer, TrailerFile
from steam_manager.steam.models.media import Assets

if TYPE_CHECKING:
    from steam_manager.loader.rows import Findings, Rows
    from steam_manager.steam.models.media import Screenshots, Trailers

ASSET_DERIVED: Final = ("asset_url_format", "page_background_path", "last_modified")
"""The asset fields that aren't images: their paths follow from the app and the time."""
# pylint: disable-next=not-an-iterable  # pylint can't infer pydantic's class property
IMAGE_KINDS: Final = tuple(name for name in Assets.model_fields if name not in ASSET_DERIVED)
"""Every image an app's assets can name, each stored under its field's name."""

_OWNER: Final = re.compile(r"^steam/apps/(\d+)/")


def assets(
    appid: int, current: Assets | None, base: Assets | None, rows: Rows, findings: Findings
) -> dict[str, int | None]:
    """
    Turn an app's images into rows, each marked when a seasonal override replaces the base one.

    :param appid: The app.
    :param current: Its images as the store shows them.
    :param base: Its images before any override.
    :param rows: Where the rows go.
    :param findings: Where a base image without a current one, and paths that don't follow
        from the app and the time, are counted.
    :return: The app's columns ``assets_last_modified`` and ``assets_appid``.
    """
    columns: dict[str, int | None] = {"assets_last_modified": None, "assets_appid": None}
    if current is not None:
        last_modified = current.last_modified
        columns["assets_last_modified"] = last_modified
        match = _OWNER.search(current.asset_url_format or "")
        owner = int(match[1]) if match else appid
        columns["assets_appid"] = owner if owner != appid else None
        findings.same(
            "assets.asset_url_format",
            current.asset_url_format,
            f"steam/apps/{owner}/${{FILENAME}}?t={last_modified}",
        )
        findings.same(
            "assets.page_background_path",
            current.page_background_path,
            f"app/{owner}?t={last_modified}",
        )
    for name in ASSET_DERIVED:
        findings.same(
            f"assets_without_overrides.{name}",
            getattr(base, name, None),
            getattr(current, name, None),
        )
    shown: list[str] = []
    for kind in IMAGE_KINDS:
        filename = getattr(current, kind, None)
        if filename is None:
            continue
        shown.append(kind)
        original = getattr(base, kind, None)
        overridden = original != filename
        rows.add(
            AppAsset,
            appid=appid,
            kind=kind,
            filename=filename,
            is_override=overridden,
            base_filename=original if overridden else None,
        )
    findings.rest(current, "assets", Assets.model_fields)
    # A base image with no current one would be lost; it hasn't happened.
    findings.rest(base, "assets_without_overrides", [*ASSET_DERIVED, *shown])
    return columns


def screenshots(appid: int, shots: Screenshots | None, rows: Rows, findings: Findings) -> None:
    """
    Turn an app's screenshots into rows, marking those shown only to adults who ask.

    :param appid: The app.
    :param shots: Its screenshots.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    lists = (
        (
            ("all_ages_screenshots", False, shots.all_ages_screenshots),
            ("mature_content_screenshots", True, shots.mature_content_screenshots),
        )
        if shots
        else ()
    )
    for key, mature, listed in lists:
        for shot in listed:
            findings.rest(
                shot, f"screenshots.{key}[]", {"filename", "ordinal", "alt_text", "category"}
            )
            rows.add(
                AppScreenshot,
                appid=appid,
                is_mature=mature,
                ordinal=shot.ordinal,
                filename=shot.filename,
                alt_text=shot.alt_text,
                category=shot.category,
            )
    findings.rest(shots, "screenshots", {"all_ages_screenshots", "mature_content_screenshots"})


def trailers(appid: int, videos: Trailers | None, rows: Rows, findings: Findings) -> None:
    """
    Turn an app's trailers into rows: the trailer itself, shared, and the app's place and files.

    :param appid: The app.
    :param videos: Its trailers.
    :param rows: Where the rows go.
    :param findings: Where fields nothing stores are counted.
    """
    lists = (
        (
            ("highlights", True, videos.highlights),
            ("other_trailers", False, videos.other_trailers),
        )
        if videos
        else ()
    )
    for key, highlight, listed in lists:
        for position, trailer in enumerate(listed):
            base_id = trailer.trailer_base_id
            path = f"trailers.{key}[]"
            rows.add(
                AppTrailer,
                appid=appid,
                trailer_base_id=base_id,
                is_highlight=highlight,
                position=position,
            )
            for file in trailer.microtrailer:
                findings.rest(file, f"{path}.microtrailer[]", {"filename", "type"})
                rows.add(
                    TrailerFile,
                    appid=appid,
                    trailer_base_id=base_id,
                    kind="microtrailer",
                    path=file.filename,
                    format=file.type,
                )
            for stream in trailer.adaptive_trailers:
                findings.rest(stream, f"{path}.adaptive_trailers[]", {"cdn_path", "encoding"})
                rows.add(
                    TrailerFile,
                    appid=appid,
                    trailer_base_id=base_id,
                    kind="adaptive",
                    path=stream.cdn_path,
                    format=stream.encoding,
                )
            rows.add(
                Trailer,
                trailer_base_id=base_id,
                trailer_id=trailer.trailer_id,
                name=trailer.trailer_name,
                url_format=trailer.trailer_url_format,
                category=trailer.trailer_category,
                all_ages=trailer.all_ages,
                screenshot_small=trailer.screenshot_small,
                screenshot_medium=trailer.screenshot_medium,
                screenshot_full=trailer.screenshot_full,
                captions_manifest=trailer.captions_manifest,
            )
            findings.rest(
                trailer,
                path,
                {
                    "trailer_base_id",
                    "trailer_id",
                    "trailer_name",
                    "trailer_url_format",
                    "trailer_category",
                    "all_ages",
                    "screenshot_small",
                    "screenshot_medium",
                    "screenshot_full",
                    "captions_manifest",
                    "microtrailer",
                    "adaptive_trailers",
                },
            )
    findings.rest(videos, "trailers", {"highlights", "other_trailers"})
