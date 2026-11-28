"""Profiles: one folder per Steam account, holding its settings, database and raw archive."""

import sys
from datetime import timedelta
from operator import attrgetter
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from steam_manager.answers import Kind
from steam_manager.steam.community import INDIVIDUAL_BASE
from steam_manager.steam.store import API_LANGUAGES

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_AGES: Final[Mapping[Kind, timedelta]] = MappingProxyType(
    {
        Kind.STORE_CATEGORIES: timedelta(days=7),
        Kind.TAGS: timedelta(days=7),
        # One request each: a sync run again within the hour, after an interruption, skips them.
        Kind.WISHLIST: timedelta(hours=1),
        Kind.FOLLOWED_APPS: timedelta(hours=1),
        Kind.LISTING: timedelta(days=7),
        Kind.STORE_ITEM: timedelta(days=1),
        Kind.CURRENT_PLAYERS: timedelta(days=1),
        Kind.APP_REVIEWS: timedelta(days=7),
        Kind.REVIEW_HISTOGRAM: timedelta(days=7),
    }
)
"""
How old each kind of answer may grow before a sync fetches it again, unless a profile says.

Light entries go stale with their listing, and genre names are asked only for a genre that has
no name, so neither kind has an age of its own.
"""
SETTINGS_FILE: Final = "settings.json"
"""A profile's settings, inside its folder."""
DATABASE_FILE: Final = "steam.sqlite"
"""A profile's database, inside its folder."""
ARCHIVE_FILE: Final = "archive.sqlite"
"""A profile's raw archive, inside its folder."""

_APP: Final = "steam-manager"
_COUNTRY_LENGTH: Final = 2


def _country(code: str) -> str:
    """
    Read a country code typed loosely, such as ``br`` with a space around it.

    :param code: The code.
    :return: It stripped and upper-cased, such as ``BR``.
    :raise ValueError: When it isn't two ASCII letters.
    """
    found = code.strip().upper()
    if not (len(found) == _COUNTRY_LENGTH and found.isascii() and found.isalpha()):
        message = f"a country is two letters, such as BR, not {code!r}"
        raise ValueError(message)
    return found


def _language(code: str) -> str:
    """
    Accept one of Steam's API language codes only: a typo would silently give English.

    :param code: The code, such as ``brazilian``.
    :return: The code.
    :raise ValueError: When Steam has no such code.
    """
    if code not in API_LANGUAGES:
        message = f"{code!r} isn't a Steam language code, such as english or brazilian"
        raise ValueError(message)
    return code


def _aged(kind: Kind) -> Kind:
    """
    Accept a kind of answer only when it has a maximum age.

    :param kind: The kind.
    :return: The kind.
    :raise ValueError: When it has none.
    """
    if kind not in MAX_AGES:
        message = f"{kind} has no maximum age"
        raise ValueError(message)
    return kind


type Country = Annotated[str, AfterValidator(_country)]
"""A store country: two upper-case ASCII letters, such as ``BR``."""


class Settings(BaseModel):
    """What a profile is about, and how its sync behaves."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    steamid: Annotated[int, Field(gt=INDIVIDUAL_BASE, lt=INDIVIDUAL_BASE + 2**32)]
    """The account's SteamID64."""
    home_country: Country
    """The store country whose prices the reports show."""
    # Validated by default too, so that a home in the US drops the default fallback.
    fallback_countries: tuple[Country, ...] = Field(default=("US",), validate_default=True)
    """Countries asked, in order, for the apps the earlier ones don't sell."""
    language: Annotated[str, AfterValidator(_language)] = "english"
    """Steam's API code for the language of the answers, such as ``english``."""
    max_ages: dict[Annotated[Kind, AfterValidator(_aged)], Annotated[timedelta, Field(ge=0)]] = (
        Field(default_factory=dict)
    )
    """The user's own maximum ages; every other kind takes :data:`MAX_AGES`'."""

    @field_validator("fallback_countries")
    @classmethod
    def _drop_repeats(cls, countries: tuple[str, ...], info: ValidationInfo) -> tuple[str, ...]:
        """
        Drop the home country and repeats from the fallbacks, keeping the first of each.

        :param countries: The fallbacks, each already normalized.
        :param info: The fields validated before, the home country among them.
        :return: What remains, in order.
        """
        home = info.data.get("home_country")
        return tuple(country for country in dict.fromkeys(countries) if country != home)

    @property
    def countries(self) -> tuple[str, ...]:
        """The home country, then the fallbacks in order."""
        return (self.home_country, *self.fallback_countries)

    def max_age(self, kind: Kind) -> timedelta:
        """
        Tell how old an answer of one kind may grow before a sync fetches it again.

        :param kind: A kind in :data:`MAX_AGES`.
        :return: The user's age for it, else the default.
        """
        return self.max_ages.get(kind, MAX_AGES[kind])


def default_home(environ: Mapping[str, str], *, platform: str = sys.platform) -> Path:
    """
    Find the data folder that holds every profile.

    :param environ: The environment, such as :data:`os.environ`.
    :param platform: The platform, as :data:`sys.platform` names it.
    :return: ``STEAM_MANAGER_HOME`` when set, else the platform's local user-data folder:
        local rather than roaming on Windows, since an archive reaches gigabytes.
    """
    if home := environ.get("STEAM_MANAGER_HOME"):
        return Path(home)
    if platform == "win32":
        return Path(environ["LOCALAPPDATA"]) / _APP
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _APP
    data = environ.get("XDG_DATA_HOME")
    return (Path(data) if data else Path.home() / ".local" / "share") / _APP


def create_profile(home: Path, settings: Settings) -> Path:
    """
    Create a profile's folder, named by its SteamID, and write its settings there.

    :param home: The data folder, created when missing.
    :param settings: The profile's settings.
    :return: The profile's folder.
    :raise FileExistsError: When the account already has a profile.
    """
    folder = home / str(settings.steamid)
    folder.mkdir(parents=True)
    (folder / SETTINGS_FILE).write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    return folder


def read_settings(folder: Path) -> Settings:
    """
    Read a profile's settings.

    :param folder: The profile's folder.
    :return: Its settings.
    """
    return Settings.model_validate_json((folder / SETTINGS_FILE).read_text(encoding="utf-8"))


def list_profiles(home: Path) -> list[Settings]:
    """
    Read every profile's settings.

    :param home: The data folder.
    :return: The settings, by SteamID; none when the folder doesn't exist yet.
    """
    found = (read_settings(path.parent) for path in home.glob(f"*/{SETTINGS_FILE}"))
    return sorted(found, key=attrgetter("steamid"))
