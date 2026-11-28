"""Tests for turning a store item into rows, against store items recorded from Steam."""

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from sqlalchemy import create_engine, insert

from steam_manager.db.schema import SteamBase
from steam_manager.loader.rows import MalformedAnswerError, iso
from steam_manager.loader.store_item import (
    SHARED_TABLES,
    STORE_ITEM_TABLES,
    CreditRef,
    Described,
    describe,
)
from steam_manager.steam.models.lookups import StoreCategoriesAnswer
from steam_manager.steam.models.store_item import StoreItem

if TYPE_CHECKING:
    from collections.abc import Mapping

FIXTURES: Final = Path(__file__).parents[2] / "fixtures" / "steam"
"""The recorded Steam answers."""
RECORDED: Final = sorted(
    [*FIXTURES.glob("store_item/*.json"), *FIXTURES.glob("store_item_light/*.json")]
)
"""Every recorded store item, full and light."""
NESTED: Final = "included_items.included_apps[]"
"""Where the short records of other apps sit in a store item."""


def category_types() -> dict[int, int]:
    """
    Read each store category's list from the recorded lookup.

    :return: Each category's ``type``, by id.
    """
    answer = StoreCategoriesAnswer.model_validate_json(
        (FIXTURES / "store_categories.json").read_bytes()
    )
    assert answer.response is not None
    return {
        category.categoryid: category.type
        for category in answer.response.categories
        if category.categoryid is not None and category.type is not None
    }


def read(path: Path) -> dict[str, object]:
    """
    Read a recorded store item as Steam sent it.

    :param path: Its file.
    :return: The item.
    """
    item: dict[str, object] = json.loads(path.read_bytes())
    return item


def described(path: Path, payload: Mapping[str, object] | None = None) -> Described:
    """
    Describe a recorded store item, or a changed copy of it, in the store it was recorded in.

    :param path: Its file, named ``<appid>-<country>.json``.
    :param payload: The item to describe instead of the file's.
    :return: Its rows and findings.
    """
    item = StoreItem.model_validate(read(path) if payload is None else payload)
    return describe(item, country=path.stem.split("-")[1], category_types=category_types())


def every_entry() -> list[tuple[str, StoreItem, str, str]]:
    """
    List every recorded store item, and every short record nested in one.

    :return: An id, the item, the store country, and where the item sits in its answer.
    """
    entries = []
    for path in RECORDED:
        item = StoreItem.model_validate(read(path))
        country = path.stem.split("-")[1]
        entries.append((path.stem, item, country, ""))
        nested = item.included_items.included_apps if item.included_items else ()
        entries.extend((f"{path.stem}/{app.id}", app, country, NESTED) for app in nested)
    return entries


ENTRIES: Final = every_entry()
"""Every recorded store item and short record."""


@pytest.mark.parametrize(
    ("item", "country", "path"), [entry[1:] for entry in ENTRIES], ids=[e[0] for e in ENTRIES]
)
def test_a_recorded_entry_leaves_nothing_out(item: StoreItem, country: str, path: str) -> None:
    """Every field is stored, checked or skipped on purpose, and every check holds."""
    found = describe(item, country=country, category_types=category_types(), path=path)

    assert found.findings.unknown == Counter()
    assert not +found.findings.mismatches


def test_a_new_field_is_reported_at_its_path() -> None:
    """A field Steam adds deep inside a full entry is reported where it was found."""
    payload = read(FIXTURES / "store_item" / "620-BR.json")
    extra = payload["extra_details"]
    assert isinstance(extra, dict)
    extra["new_field"] = 1

    found = described(FIXTURES / "store_item" / "620-BR.json", payload)

    assert found.findings.unknown == Counter({"extra_details.new_field": 1})


def test_a_new_field_in_a_nested_record_names_its_place() -> None:
    """A short record's field is reported at its path in the answer that holds it."""
    item = StoreItem.model_validate({"id": 400, "new_field": 1})

    found = describe(item, country="BR", category_types={}, path=NESTED)

    assert found.findings.unknown == Counter({f"{NESTED}.new_field": 1})


def test_portal_2_gives_the_notebooks_rows() -> None:
    """Portal 2's entry fills the app row, its best offer and its credits."""
    path = FIXTURES / "store_item" / "620-BR.json"
    item = StoreItem.model_validate(read(path))
    assert item.release is not None

    found = described(path)

    [app] = found.rows.tables["app"]
    assert app["appid"] == 620
    assert app["name"] == "Portal 2"
    assert app["type"] == 0
    assert app["store_country"] == "BR"
    assert app["steam_release_date"] == iso(item.release.steam_release_date)
    assert str(app["steam_release_date"]).startswith("2011-04-")
    assert app["counts_all_purchases"] is None
    assert [row["is_best"] for row in found.rows.tables["app_offer"]].count(True) == 1
    assert CreditRef("developer", 0, "Valve", 4) in found.credits


def test_a_free_app_counts_every_purchase() -> None:
    """Steam's review counts of a free game include people who didn't buy it on Steam."""
    [app] = described(FIXTURES / "store_item" / "570-BR.json").rows.tables["app"]

    assert app["counts_all_purchases"] is True


def test_featured_creators_are_stored() -> None:
    """The creator homes a store page features have rows, in Steam's order."""
    found = described(FIXTURES / "store_item" / "546560-JP.json")

    assert found.rows.tables["app_featured_creator"] == [
        {"appid": 546560, "position": 0, "creator_id": 33078398}
    ]


def test_the_first_franchise_is_stored() -> None:
    """The creator page of an app's first franchise is kept on the app."""
    found = described(FIXTURES / "store_item" / "546560-JP.json")

    [app] = found.rows.tables["app"]
    assert app["first_franchise_creator_id"] == 33078398


def test_a_first_franchise_without_franchises_is_no_mismatch() -> None:
    """A DLC sends its parent's first franchise without the franchises: stored, not checked."""
    path = FIXTURES / "store_item" / "620-BR.json"
    payload = read(path)
    basic = payload["basic_info"]
    assert isinstance(basic, dict)
    basic["first_franchise_clan_account_id"] = 9

    found = described(path, payload)

    assert "basic_info.first_franchise_clan_account_id" not in found.findings.mismatches
    assert found.findings.unknown == Counter()
    [app] = found.rows.tables["app"]
    assert app["first_franchise_creator_id"] == 9


def grouped(group: str) -> Described:
    """
    Describe Portal 2 with its first included package's best option in a given group.

    :param group: The group the option names.
    :return: Its rows and findings.
    """
    path = FIXTURES / "store_item" / "620-BR.json"
    payload = read(path)
    included = payload["included_items"]
    assert isinstance(included, dict)
    packages = included["included_packages"]
    assert isinstance(packages, list)
    packages[0]["best_purchase_option"]["package_group"] = group
    return described(path, payload)


def test_a_short_records_option_may_sit_in_a_page_group() -> None:
    """A subscription a DLC includes sits in that DLC's own subscriptions group: no mismatch."""
    found = grouped("subscriptions")

    assert found.findings.mismatches["included_offer.package_group"] == 0


def test_a_short_records_option_in_an_unknown_group_is_a_mismatch() -> None:
    """An option in a group the including page lacks is reported."""
    found = grouped("elsewhere")

    assert found.findings.mismatches["included_offer.package_group"] == 1


def test_a_light_entry_keeps_its_best_price() -> None:
    """A light entry's only offer is its best one, priced in the store it came from."""
    found = described(FIXTURES / "store_item_light" / "10-BR.json")

    [price] = found.rows.tables["offer_price"]
    assert (price["kind"], price["id"], price["country"]) == ("package", 7, "BR")
    assert price["final_price_in_cents"] == 3399
    assert price["formatted_final_price"] == "R$33,99"
    [offer] = found.rows.tables["app_offer"]
    assert offer["is_best"] is True
    assert offer["package_group"] == "default"


def test_an_app_not_sold_gives_a_bare_row() -> None:
    """A store that doesn't sell an app answers with its id and little else."""
    found = described(FIXTURES / "store_item" / "12170-BR.json")

    [app] = found.rows.tables["app"]
    assert app["success"] == 15
    assert app["name"] is None
    assert set(found.rows.tables) == {"app"}


def test_a_credit_without_a_name_is_malformed() -> None:
    """A credit names someone; without a name it can't be stored."""
    item = StoreItem.model_validate({"id": 620, "basic_info": {"developers": [{}]}})

    with pytest.raises(MalformedAnswerError, match=r"basic_info\.developers\[\] has no name"):
        describe(item, country="BR", category_types={})


def test_a_creator_without_an_id_is_malformed() -> None:
    """A creator page is known by its id; without one it can't be stored."""
    item = StoreItem.model_validate({"id": 620, "included_items": {"included_creators": [{}]}})

    with pytest.raises(MalformedAnswerError, match=r"included_creators\[\] has no id"):
        describe(item, country="BR", category_types={})


def test_every_table_is_owned_or_shared() -> None:
    """Every table a store item fills is either replaced with the app or shared with others."""
    owned = {table.__tablename__ for table in STORE_ITEM_TABLES}
    shared = {table.__tablename__ for table in SHARED_TABLES}
    filled = {
        name
        for _, item, country, path in ENTRIES
        for name in describe(item, country=country, category_types={}, path=path).rows.tables
    }

    assert not owned & shared
    assert filled <= owned | shared


@pytest.mark.parametrize("path", RECORDED, ids=lambda path: path.stem)
def test_described_rows_fit_the_schema(path: Path) -> None:
    """
    An entry's rows insert into the real tables: no STRICT error, no key repeated in one answer.

    A store item's own rows go in with plain inserts; shared rows replace each other, as a load
    does.
    """
    owned = {table.__tablename__ for table in STORE_ITEM_TABLES}
    engine = create_engine("sqlite://")
    SteamBase.metadata.create_all(engine)
    with engine.begin() as connection:
        for name, rows in described(path).rows.tables.items():
            table = SteamBase.metadata.tables[name]
            columns = [column.name for column in table.columns if column.computed is None]
            statement = insert(table)
            if name not in owned:
                statement = statement.prefix_with("OR REPLACE")
            connection.execute(statement, [{c: row.get(c) for c in columns} for row in rows])
    engine.dispose()


EVERY_SECTION: Final = {
    "id": 900,
    "item_type": 0,
    "success": 1,
    "visible": True,
    "name": "Every Section",
    "store_url_path": "app/900/Every_Section",
    "store_url_slug": "Every_Section",
    "is_early_access": True,
    "is_coming_soon": False,
    "reviews": {
        "summary_filtered": {
            "review_count": 3,
            "percent_positive": 66,
            "review_score": 0,
            "review_score_label": "3 user reviews",
        }
    },
    "release": {
        "steam_release_date": 1302566400,
        "is_early_access": True,
        "is_coming_soon": False,
    },
    "free_weekend": {"start_time": 1302566400, "end_time": 0, "text": "Free!", "appid": 901},
    "game_rating": {"type": "esrb", "agency": 1, "rating": "m", "image_url": "esrb_m.png"},
    "optin_registration_tags": [{"optin_name": "beta", "values": ["yes", "maybe"]}],
    "related_items": {
        "playtests": [{"appid": 902, "is_open": True}],
        "dlc_parent_appids": [903],
        "related_f2p": {"appid": 904, "header_text": "Free", "description_text": "Play free"},
        "provides_engine_appid": [907],
    },
    "extra_details": {
        "links_and_info": {"available_documents": [1], "manufacturers": ["Valve"]},
        "steam_award": [{"voteid": 7, "award_year": 2025, "localization": {"title": "Best"}}],
        "season_pass": {
            "appid": 905,
            "milestones": [
                {
                    "milestone_id": 1,
                    "appid": 906,
                    "event_gid": "18446744073709551615",
                    "rtime_complete": 1302566400,
                    "shipped": True,
                    "dates": [{"coming_soon_display_type": "date", "rtime": 1302566400}],
                    "title": [{"language": 0, "localized_string": "Part 1"}],
                    "milestone_desc": [{"language": 0, "localized_string": "The first part"}],
                }
            ],
        },
    },
}
"""A store item with every section the recordings lack."""


def test_a_store_item_with_every_section_fills_every_table() -> None:
    """The sections no recording holds are stored too, and nothing is left out."""
    found = describe(StoreItem.model_validate(EVERY_SECTION), country="BR", category_types={})
    tables = found.rows.tables

    [app] = tables["app"]
    assert (app["free_weekend_start"], app["free_weekend_end"]) == ("2011-04-12 00:00:00", None)
    assert (app["free_weekend_text"], app["free_weekend_appid"]) == ("Free!", 901)
    assert (app["is_early_access"], app["is_coming_soon"]) == (True, False)
    assert (app["agency"], app["rating"]) == (1, "m")
    assert tables["rating_agency"] == [{"agency": 1, "rating_type": "esrb"}]
    assert tables["age_rating"] == [{"agency": 1, "rating": "m", "image_url": "esrb_m.png"}]
    assert [row["value"] for row in tables["app_optin_tag"]] == ["yes", "maybe"]
    related = {(row["kind"], row["related_appid"]) for row in tables["app_related"]}
    assert related == {
        ("playtest", 902),
        ("dlc_parent", 903),
        ("related_f2p", 904),
        ("season_pass", 905),
        ("engine", 907),
    }
    assert tables["app_document"] == [{"appid": 900, "document": 1}]
    assert tables["app_manufacturer"] == [{"appid": 900, "position": 0, "name": "Valve"}]
    assert tables["app_steam_award"][0]["title"] == "Best"
    [milestone] = tables["season_pass_milestone"]
    assert milestone["event_gid"] == "18446744073709551615"
    assert milestone["milestone_appid"] == 906
    assert [row["kind"] for row in tables["season_pass_milestone_text"]] == [
        "title",
        "description",
    ]
    assert tables["season_pass_milestone_date"][0]["rtime"] == "2011-04-12 00:00:00"
    assert "review_score" not in tables  # a score of 0 has no label of its own
    assert found.findings.unknown == Counter()
    assert not +found.findings.mismatches


def test_sparse_sections_add_no_lookups_or_relations() -> None:
    """A summary without a score, a bare rating and an empty season pass add only their rows."""
    item = StoreItem.model_validate(
        {
            "id": 900,
            "item_type": 0,
            "success": 1,
            "visible": True,
            "reviews": {"summary_language_specific": {"review_count": 0}},
            "game_rating": {"agency": 2},
            "extra_details": {"season_pass": {"milestones": []}},
        }
    )

    found = describe(item, country="BR", category_types={})

    assert set(found.rows.tables) == {"app", "app_review_summary"}
    assert found.rows.tables["app"][0]["agency"] == 2
    assert found.findings.unknown == Counter()
    assert not +found.findings.mismatches
