"""Tests for the rows a store item becomes, and the findings that go with them."""

from collections import Counter

import pytest

from steam_manager.db.schema.lookups import Tag
from steam_manager.db.schema.media import AppScreenshot, Trailer
from steam_manager.db.schema.offers import OfferPrice
from steam_manager.loader.rows import Findings, MalformedAnswerError, Rows, iso
from steam_manager.steam.models.details import Metacritic


def test_rows_are_kept_per_table_in_order() -> None:
    """Each table's rows come back in the order they were added."""
    rows = Rows()
    rows.add(Tag, tagid=9, name="Strategy")
    rows.add(Tag, tagid=19)

    assert rows.tables == {"tag": [{"tagid": 9, "name": "Strategy"}, {"tagid": 19}]}


def test_rows_extend_other_rows() -> None:
    """Rows built apart join, table by table."""
    rows, more = Rows(), Rows()
    rows.add(Tag, tagid=9)
    more.add(Tag, tagid=19)

    rows.extend(more)

    assert rows.tables == {"tag": [{"tagid": 9}, {"tagid": 19}]}


def test_a_row_for_a_missing_column_is_refused() -> None:
    """A column the table lacks fails where it is written, naming the table and the column."""
    with pytest.raises(ValueError, match=r"tag has no column label") as raised:
        Rows().add(Tag, tagid=9, label="Strategy")

    assert not isinstance(raised.value, MalformedAnswerError)  # a bug, not Steam's answer


def test_a_generated_column_is_refused() -> None:
    """SQLite works out a generated column itself; a value for one is a mistake."""
    with pytest.raises(ValueError, match=r"offer_price\.discount_pct is generated"):
        Rows().add(OfferPrice, kind="package", id=7, country="BR", discount_pct=10)


def test_a_row_without_a_required_value_is_refused() -> None:
    """A blank Steam sent for a column that can't be blank makes the answer malformed, at once."""
    with pytest.raises(MalformedAnswerError, match=r"app_screenshot needs filename"):
        Rows().add(AppScreenshot, appid=620, is_mature=False, ordinal=0, filename=None)
    with pytest.raises(MalformedAnswerError, match=r"app_screenshot needs ordinal, filename"):
        Rows().add(AppScreenshot, appid=620, is_mature=False)


def test_a_blank_key_is_refused_where_sqlite_would_number_it() -> None:
    """SQLite would invent an id for a blank INTEGER PRIMARY KEY; a trailer has Steam's own."""
    with pytest.raises(MalformedAnswerError, match=r"trailer needs trailer_base_id"):
        Rows().add(Trailer, trailer_id=1)


def test_rest_counts_fields_left_unused() -> None:
    """A declared field nothing used and a field nothing declares are both reported."""
    findings = Findings()
    metacritic = Metacritic.model_validate(
        {"score": 90, "url": "https://example.com", "new_field": 1, "placeholder": None}
    )

    findings.rest(metacritic, "metacritic", {"score"})

    assert findings.unknown == Counter({"metacritic.url": 1, "metacritic.new_field": 1})


def test_rest_counts_an_empty_text_but_not_an_empty_list() -> None:
    """``""`` is a value Steam sent; ``None``, ``[]`` and ``{}`` are placeholders."""
    findings = Findings()
    metacritic = Metacritic.model_validate({"url": "", "list": [], "map": {}})

    findings.rest(metacritic, "metacritic", set())

    assert findings.unknown == Counter({"metacritic.url": 1})


def test_rest_at_the_top_names_fields_bare() -> None:
    """A field at the top of an answer is named as ``unknown_fields`` names it."""
    findings = Findings()

    findings.rest(Metacritic(url="x"), "", {"score"})

    assert findings.unknown == Counter({"url": 1})


def test_rest_of_nothing_counts_nothing() -> None:
    """A part Steam didn't send has nothing left over."""
    findings = Findings()

    findings.rest(None, "metacritic", {"score"})

    assert findings.unknown == Counter()


def test_rest_refuses_a_name_the_model_lacks() -> None:
    """A wrong name in the used list would hide a field: it fails instead."""
    with pytest.raises(ValueError, match=r"metacritic has no field grade"):
        Findings().rest(Metacritic(), "metacritic", {"grade"})


def test_same_counts_only_differences() -> None:
    """A derived value that follows counts 0, and one that doesn't counts 1."""
    findings = Findings()

    findings.same("visible", stored=True, derived=True)
    findings.same("item_type", stored=1, derived=0)

    assert findings.mismatches == Counter({"visible": 0, "item_type": 1})


def test_findings_add_up() -> None:
    """Findings gathered apart add up."""
    findings, more = Findings(), Findings()
    findings.unknown["a"] += 1
    more.unknown["a"] += 2
    more.mismatches["b"] += 1

    findings.update(more)

    assert findings.unknown == Counter({"a": 3})
    assert findings.mismatches == Counter({"b": 1})


def test_iso_writes_the_notebooks_text() -> None:
    """Epoch seconds become the notebook's UTC text, and 0 or nothing means no date."""
    assert iso(1302566400) == "2011-04-12 00:00:00"
    assert iso(0) is None
    assert iso(None) is None
