"""Tests for the extra details' models."""

from typing import Final

from steam_manager.steam.models.base import unknown_fields
from steam_manager.steam.models.details import (
    ExtraDetails,
    HardwareCompatibility,
    Milestone,
    SalePage,
)

LARGEST_UINT64: Final = "18446744073709551615"
"""An event id SQLite's INTEGER can't hold."""


def test_event_gids_stay_text() -> None:
    """A uint64 Steam sends as text is kept as that text, never turned into a number."""
    assert SalePage.model_validate({"event_gid": LARGEST_UINT64}).event_gid == LARGEST_UINT64
    assert Milestone.model_validate({"event_gid": LARGEST_UINT64}).event_gid == LARGEST_UINT64


def test_a_soundtrack_reads_its_album() -> None:
    """A soundtrack's credits and tracks are read, a track's second-language title included."""
    extra = ExtraDetails.model_validate(
        {
            "music_album": {
                "artist": "Someone",
                "tracks": [{"disc_number": 1, "track_number": 2, "other_name": "Otro"}],
            }
        }
    )

    assert extra.music_album is not None
    assert extra.music_album.artist == "Someone"
    assert extra.music_album.tracks[0].other_name == "Otro"


def test_a_milestone_reads_its_backfilled_release() -> None:
    """A season pass milestone says whether it shipped as a backfilled release."""
    milestone = Milestone.model_validate({"backfilled_release": True})

    assert milestone.backfilled_release is True
    assert unknown_fields(milestone) == []


def test_compatibility_reads_the_steam_deck_blog_url() -> None:
    """The compatibility reviews can link the announcement of the Steam Deck review."""
    url = "https://steamcommunity.com/games/10/announcements/detail/1?snr=2___"
    tests = HardwareCompatibility.model_validate({"steam_deck_blog_url": url})

    assert tests.steam_deck_blog_url == url
    assert unknown_fields(tests) == []
