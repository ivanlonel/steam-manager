"""Tests for the extra details' models."""

from steam_manager.steam.models.details import Milestone, SalePage

LARGEST_UINT64 = "18446744073709551615"
"""An event id SQLite's INTEGER can't hold."""


def test_event_gids_stay_text() -> None:
    """A uint64 Steam sends as text is kept as that text, never turned into a number."""
    assert SalePage.model_validate({"event_gid": LARGEST_UINT64}).event_gid == LARGEST_UINT64
    assert Milestone.model_validate({"event_gid": LARGEST_UINT64}).event_gid == LARGEST_UINT64
