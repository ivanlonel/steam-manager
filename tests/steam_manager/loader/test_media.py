"""Tests for turning an app's images and trailers into rows."""

import json
from collections import Counter
from pathlib import Path
from typing import Final

from steam_manager.loader.media import assets, screenshots, trailers
from steam_manager.loader.rows import Findings, Rows
from steam_manager.steam.models.media import Screenshots
from steam_manager.steam.models.store_item import StoreItem

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam" / "store_item"
"""The recorded full entries."""


def recorded(name: str) -> dict[str, object]:
    """
    Read a recorded full entry as Steam sent it.

    :param name: Its file's stem, such as ``620-BR``.
    :return: The entry.
    """
    loaded: dict[str, object] = json.loads((FIXTURES / f"{name}.json").read_bytes())
    return loaded


def test_assets_mark_overrides_and_keep_the_base_file() -> None:
    """A seasonal image is an override, and the image it replaces is kept beside it."""
    item = StoreItem.model_validate(recorded("1172470-BR"))
    assert item.assets is not None
    assert item.assets_without_overrides is not None
    rows, findings = Rows(), Findings()

    columns = assets(1172470, item.assets, item.assets_without_overrides, rows, findings)

    assert columns == {"assets_last_modified": item.assets.last_modified, "assets_appid": None}
    by_kind = {row["kind"]: row for row in rows.tables["app_asset"]}
    assert by_kind["header"]["is_override"] is True
    assert by_kind["header"]["filename"] == item.assets.header
    assert by_kind["header"]["base_filename"] == item.assets_without_overrides.header
    assert by_kind["library_capsule"]["is_override"] is False
    assert by_kind["library_capsule"]["base_filename"] is None
    assert findings.unknown == Counter()
    assert not +findings.mismatches


def test_assets_of_another_app_name_it() -> None:
    """A DLC that shows its parent's images names the parent, and the paths still follow."""
    answer = recorded("620-BR")
    images = answer["assets"]
    assert isinstance(images, dict)
    images["asset_url_format"] = f"steam/apps/400/${{FILENAME}}?t={images['last_modified']}"
    images["page_background_path"] = f"app/400?t={images['last_modified']}"
    answer["assets_without_overrides"] = images
    item = StoreItem.model_validate(answer)
    findings = Findings()

    columns = assets(620, item.assets, item.assets_without_overrides, Rows(), findings)

    assert columns["assets_appid"] == 400
    assert not +findings.mismatches


def test_a_base_image_with_no_current_one_is_reported() -> None:
    """An image only the base set has would be lost, so it is reported."""
    item = StoreItem.model_validate(recorded("620-BR"))
    assert item.assets is not None
    current = item.assets.model_copy(update={"header": None})
    findings = Findings()

    assets(620, current, item.assets_without_overrides, Rows(), findings)

    assert findings.unknown == Counter({"assets_without_overrides.header": 1})


def test_screenshots_keep_their_audience_and_order() -> None:
    """Screenshots shown only to adults are marked so, and each keeps its place."""
    shots = Screenshots.model_validate(
        {
            "all_ages_screenshots": [{"filename": "a.jpg", "ordinal": 0}],
            "mature_content_screenshots": [{"filename": "b.jpg", "ordinal": 0, "category": 2}],
        }
    )
    rows, findings = Rows(), Findings()

    screenshots(620, shots, rows, findings)

    assert [
        (row["is_mature"], row["ordinal"], row["filename"])
        for row in rows.tables["app_screenshot"]
    ] == [(False, 0, "a.jpg"), (True, 0, "b.jpg")]
    assert findings.unknown == Counter()


def test_trailers_give_their_files_and_positions() -> None:
    """Each trailer is shared by id; the app keeps its place in each list, and its files."""
    item = StoreItem.model_validate(recorded("570-BR"))
    assert item.trailers is not None
    rows, findings = Rows(), Findings()

    trailers(570, item.trailers, rows, findings)

    placed = [(row["is_highlight"], row["position"]) for row in rows.tables["app_trailer"]]
    assert placed == [(True, 0), (True, 1), (False, 0), (False, 1), (False, 2)]
    assert len(rows.tables["trailer"]) == 5
    assert {row["kind"] for row in rows.tables["trailer_file"]} <= {"microtrailer", "adaptive"}
    assert rows.tables["trailer_file"]
    assert findings.unknown == Counter()


def test_an_app_without_images_has_no_asset_rows() -> None:
    """A delisted app sends no assets: no rows, blank columns, nothing to report."""
    rows, findings = Rows(), Findings()

    columns = assets(12170, None, None, rows, findings)

    assert columns == {"assets_last_modified": None, "assets_appid": None}
    assert "app_asset" not in rows.tables
    assert findings.unknown == Counter()
    assert not +findings.mismatches
