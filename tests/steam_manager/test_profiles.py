"""Tests for profiles: their settings, their folders, and where those folders live."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from steam_manager.answers import Kind
from steam_manager.archive import Archive
from steam_manager.db.schema.apps import App
from steam_manager.profiles import (
    ARCHIVE_FILE,
    Settings,
    create_profile,
    default_home,
    list_profiles,
    open_profile,
    read_settings,
)
from steam_manager.steam.community import INDIVIDUAL_BASE
from tests.steam_manager.loader._archive import put, recorded

STEAMID: Final = INDIVIDUAL_BASE + 1234
"""An individual's SteamID64."""


def test_countries_are_normalized() -> None:
    """Countries are upper-cased and stripped; fallbacks drop the home country and repeats."""
    settings = Settings(
        steamid=STEAMID, home_country=" br ", fallback_countries=("us", "BR", "US")
    )

    assert settings.home_country == "BR"
    assert settings.fallback_countries == ("US",)
    assert settings.countries == ("BR", "US")


@pytest.mark.parametrize("country", ["BRA", "B1", "", "ÉU"])
def test_a_country_must_be_two_letters(country: str) -> None:
    """A country that isn't two ASCII letters is refused, at home or as a fallback."""
    with pytest.raises(ValidationError):
        Settings(steamid=STEAMID, home_country=country)
    with pytest.raises(ValidationError):
        Settings(steamid=STEAMID, home_country="BR", fallback_countries=(country,))


def test_a_home_in_the_us_has_no_fallback_by_default() -> None:
    """The default fallback, the US, is dropped when it is the home country."""
    assert Settings(steamid=STEAMID, home_country="US").countries == ("US",)


def test_an_unknown_language_is_refused() -> None:
    """A language must be one of Steam's API codes: a typo would silently give English."""
    with pytest.raises(ValidationError):
        Settings(steamid=STEAMID, home_country="BR", language="pt-BR")

    settings = Settings(steamid=STEAMID, home_country="BR", language="brazilian")

    assert settings.language == "brazilian"


def test_max_ages_default_and_override() -> None:
    """A kind takes the default age unless overridden, and only overrides are written."""
    default = Settings(steamid=STEAMID, home_country="BR")
    text = json.dumps(
        {"steamid": STEAMID, "home_country": "BR", "max_ages": {"wishlist": "PT10M"}}
    )
    custom = Settings.model_validate_json(text)

    assert default.max_age(Kind.LISTING) == timedelta(days=7)
    assert custom.max_age(Kind.WISHLIST) == timedelta(minutes=10)
    assert custom.max_age(Kind.LISTING) == timedelta(days=7)
    assert json.loads(custom.model_dump_json())["max_ages"] == {"wishlist": "PT10M"}


@pytest.mark.parametrize("ages", [{"store_item_light": "PT1H"}, {"wishlist": "-PT1H"}])
def test_a_max_age_must_be_known_and_not_negative(ages: dict[str, str]) -> None:
    """A kind without a default age, or a negative age, is refused."""
    text = json.dumps({"steamid": STEAMID, "home_country": "BR", "max_ages": ages})

    with pytest.raises(ValidationError):
        Settings.model_validate_json(text)


@pytest.mark.parametrize("steamid", [1, INDIVIDUAL_BASE, INDIVIDUAL_BASE + 2**32])
def test_a_steamid_must_be_an_individual_one(steamid: int) -> None:
    """A profile's SteamID64 is a person's: the base plus a 32-bit account id other than 0."""
    with pytest.raises(ValidationError):
        Settings(steamid=steamid, home_country="BR")


@pytest.mark.parametrize(
    ("platform", "environ", "expected"),
    [
        ("win32", {"LOCALAPPDATA": "C:/Local"}, Path("C:/Local/steam-manager")),
        ("darwin", {}, Path.home() / "Library" / "Application Support" / "steam-manager"),
        ("linux", {"XDG_DATA_HOME": "/data"}, Path("/data/steam-manager")),
        ("linux", {}, Path.home() / ".local" / "share" / "steam-manager"),
    ],
)
def test_default_home_per_platform(platform: str, environ: dict[str, str], expected: Path) -> None:
    """The data folder is the platform's own, unless STEAM_MANAGER_HOME names another."""
    elsewhere = environ | {"STEAM_MANAGER_HOME": "/elsewhere"}

    assert default_home(environ, platform=platform) == expected
    assert default_home(elsewhere, platform=platform) == Path("/elsewhere")


def test_a_profile_round_trips(tmp_path: Path) -> None:
    """A profile's settings read back equal, profiles list by SteamID, and none is overwritten."""
    home = tmp_path / "home"
    first = Settings(
        steamid=STEAMID, home_country="BR", max_ages={Kind.WISHLIST: timedelta(minutes=10)}
    )
    second = Settings(steamid=STEAMID - 1, home_country="JP", language="japanese")

    folder = create_profile(home, first)
    create_profile(home, second)

    assert folder == home / str(STEAMID)
    assert read_settings(folder) == first
    assert list_profiles(home) == [second, first]
    with pytest.raises(FileExistsError):
        create_profile(home, first)


def test_list_profiles_of_a_missing_home_is_empty(tmp_path: Path) -> None:
    """A data folder that doesn't exist yet holds no profile."""
    assert list_profiles(tmp_path / "missing") == []


def test_opening_loads_what_was_archived(tmp_path: Path) -> None:
    """Answers archived by a sync that stopped before its load are loaded on the next open."""
    folder = create_profile(tmp_path, Settings(steamid=STEAMID, home_country="BR"))
    with Archive(folder / ARCHIVE_FILE) as archive:
        put(archive, Kind.STORE_ITEM, "620", "BR", recorded("store_item/620-BR.json"))

    with open_profile(folder) as profile, profile.engine.connect() as connection:
        names = connection.scalars(select(App.name).where(App.appid == 620)).all()

    assert names == ["Portal 2"]
    assert profile.report.loaded["app"] >= 1
    assert profile.settings.home_country == "BR"


def test_opening_creates_the_views(tmp_path: Path) -> None:
    """The reports are in the database as views once a profile is open."""
    folder = create_profile(tmp_path, Settings(steamid=STEAMID, home_country="BR"))

    with open_profile(folder) as profile, profile.engine.connect() as connection:
        rows = connection.exec_driver_sql("SELECT * FROM v_games").all()

    assert rows == []


def test_opening_closes_both_files(tmp_path: Path) -> None:
    """Leaving the block closes the database and the archive: Windows won't move an open file."""
    folder = create_profile(tmp_path, Settings(steamid=STEAMID, home_country="BR"))

    with open_profile(folder):
        pass
    folder.rename(tmp_path / "moved")

    assert (tmp_path / "moved" / ARCHIVE_FILE).exists()
