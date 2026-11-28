"""Tests for turning an app's extra details into rows, against recorded full entries."""

import json
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any, Final

from steam_manager.loader.details import extra_details
from steam_manager.loader.rows import Findings, Rows
from steam_manager.steam.models.details import DlcForPurchase, ExtraDetails, SeasonPass
from steam_manager.steam.models.store_item import StoreItem

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam" / "store_item"
"""The recorded full entries."""


def details_of(name: str) -> tuple[Rows, Findings, dict[str, object]]:
    """
    Turn a recorded entry's extra details into rows.

    :param name: The entry's file stem, such as ``570-BR``.
    :return: The rows, the findings and the ``app`` columns.
    """
    item = StoreItem.model_validate_json((FIXTURES / f"{name}.json").read_bytes())
    nested = item.included_items.included_apps if item.included_items else ()
    rows, findings = Rows(), Findings()
    columns, _ = extra_details(
        item.id, item.extra_details, "extra_details", rows, findings, nested=nested
    )
    return rows, findings, columns


def test_dlc_on_sale_keep_steams_order() -> None:
    """The DLC a store page offers keep their order, packages and the total price."""
    rows, findings, columns = details_of("570-BR")

    dlc = sorted(rows.tables["app_dlc"], key=itemgetter("position"))
    assert [(row["dlc_appid"], row["position"], row["packageid"]) for row in dlc] == [
        (1241930, 0, 431132),
        (652720, 1, None),
    ]
    assert columns["dlc_formatted_total_price"] == "R$33,99"
    assert columns["dlc_count"] == 2
    assert findings.mismatches["dlc_for_purchase.content_descriptorids"] == 0


def test_compatibility_results_keep_steams_order() -> None:
    """Each device's results keep the order Steam lists them in."""
    answer = json.loads((FIXTURES / "620-BR.json").read_bytes())
    tests = answer["extra_details"]["hardware_compatibility"]

    rows, findings, _ = details_of("620-BR")

    stored = [
        (row["device"], row["position"], row["display_type"], row["loc_token"])
        for row in rows.tables["app_compatibility_test"]
    ]
    assert sorted(stored) == sorted(
        (key.removesuffix("_tests"), position, test.get("display_type"), test.get("loc_token"))
        for key, listed in tests.items()
        for position, test in enumerate(listed)
    )
    assert findings.unknown == Counter()


def test_no_extra_details_give_nothing() -> None:
    """A light entry has no extra details: no columns, no texts, no rows."""
    rows = Rows()

    assert extra_details(10, None, "extra_details", rows, Findings(), nested=()) == ({}, {})
    assert not rows.tables


def test_a_dlc_count_past_steams_list_is_kept() -> None:
    """Steam lists 200 DLC at most, so an app's count of them is stored, not derived."""
    dlc = DlcForPurchase.model_validate(
        {"dlc": [{"appid": appid} for appid in range(1, 201)], "dlc_count": 532}
    )
    extra = ExtraDetails(dlc_for_purchase=dlc)
    findings = Findings()

    columns, _ = extra_details(10, extra, "extra_details", Rows(), findings, nested=())

    assert columns["dlc_count"] == 532
    assert not +findings.mismatches


def soundtrack() -> tuple[dict[str, Any], StoreItem]:
    """
    Read a recorded soundtrack, with the fields other soundtracks send added to it.

    :return: Its album as sent, and the item.
    """
    answer = json.loads((FIXTURES / "492140-BR.json").read_bytes())
    album = answer["extra_details"]["music_album"]
    album |= {"label": "A Label", "other_credits": "Mixed by Someone\r\nMastered by Another"}
    album["tracks"][1]["other_name"] = "Sendo observado"
    return album, StoreItem.model_validate(answer)


def test_a_soundtracks_tracks_keep_steams_order() -> None:
    """Each track keeps its place in Steam's list, with its second-language title."""
    album, item = soundtrack()
    rows, findings = Rows(), Findings()

    extra_details(item.id, item.extra_details, "extra_details", rows, findings, nested=())

    names = ("disc_number", "track_number", "name", "other_name", "duration_seconds")
    stored = sorted(rows.tables["app_track"], key=itemgetter("position"))
    assert [(row["appid"], row["position"], *itemgetter(*names)(row)) for row in stored] == [
        (492140, position, *(track.get(name) for name in names))
        for position, track in enumerate(album["tracks"])
    ]
    assert stored[1]["other_name"] == "Sendo observado"
    assert findings.unknown == Counter()


def test_a_soundtracks_credits_are_texts() -> None:
    """A soundtrack's credits are free text, often several lines, kept with the app's texts."""
    album, item = soundtrack()

    _, texts = extra_details(
        item.id, item.extra_details, "extra_details", Rows(), Findings(), nested=()
    )

    assert {name: texts[f"music_album_{name}"] for name in ("artist", "composer")} == {
        "artist": "Michel F. April",
        "composer": "Michel F. April",
    }
    assert texts["music_album_label"] == album["label"]
    assert texts["music_album_other_credits"] == album["other_credits"]


def test_a_milestones_backfilled_release_is_stored() -> None:
    """A milestone that shipped as a backfilled release says so in its row."""
    season = SeasonPass.model_validate(
        {
            "appid": 4241400,
            "milestones": [
                {"milestone_id": 93226, "appid": 4241420, "shipped": True},
                {
                    "milestone_id": 49672,
                    "appid": 4241440,
                    "shipped": True,
                    "backfilled_release": True,
                },
            ],
        }
    )
    rows, findings = Rows(), Findings()

    extra_details(10, ExtraDetails(season_pass=season), "extra_details", rows, findings, nested=())

    assert [
        (row["milestone_id"], row["backfilled_release"])
        for row in rows.tables["season_pass_milestone"]
    ] == [(93226, None), (49672, True)]
    assert findings.unknown == Counter()


def test_the_steam_deck_blog_url_is_stored() -> None:
    """The Steam Deck review's announcement is kept as sent, Steam's navigation code included."""
    url = "https://steamcommunity.com/games/620/announcements/detail/6356356787200715685?snr=2___"
    answer = json.loads((FIXTURES / "620-BR.json").read_bytes())
    answer["extra_details"]["hardware_compatibility"]["steam_deck_blog_url"] = url
    item = StoreItem.model_validate(answer)
    findings = Findings()

    columns, _ = extra_details(
        item.id, item.extra_details, "extra_details", Rows(), findings, nested=()
    )

    assert columns["steam_deck_blog_url"] == url
    assert findings.unknown == Counter()


def test_a_videos_running_time_is_stored() -> None:
    """A video says how long it runs, and the app keeps it."""
    extra = ExtraDetails.model_validate({"running_time_minutes": 76})
    findings = Findings()

    columns, _ = extra_details(10, extra, "extra_details", Rows(), findings, nested=())

    assert columns["running_time_minutes"] == 76
    assert findings.unknown == Counter()
