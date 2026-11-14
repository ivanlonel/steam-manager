"""Tests for the package root."""

import importlib.metadata
import re

import steam_manager


def test_version_matches_the_installed_metadata() -> None:
    """The package reports the version it was installed with."""
    assert steam_manager.__version__ == importlib.metadata.version("steam-manager")


def test_version_is_a_release_number() -> None:
    """The version has the three numeric parts a release tag needs."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", steam_manager.__version__)
