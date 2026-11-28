"""Write a load's rows, each table by its rule, inside the load's one transaction."""

import itertools
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Final, cast

from sqlalchemy import Table, delete, select, tuple_
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.sql.functions import coalesce

from steam_manager.db.schema import SteamBase
from steam_manager.db.schema.creators import AppCredit, Credit
from steam_manager.loader.offers import COUNTRY_DEPENDENT
from steam_manager.loader.rows import Findings, Rows
from steam_manager.loader.store_item import STORE_ITEM_TABLES

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping, Sequence

    from sqlalchemy import Connection

    from steam_manager.loader.store_item import CreditRef, Described

__all__ = ["FILLED_PARENTS", "ForeignKeyViolationError", "Writer", "check_foreign_keys"]

FILLED_PARENTS: Final = frozenset(
    {"app", "creator", "offer", "app_package_group", "store_category", "tag", "genre"}
    | {"language", "review_score", "rating_agency", "age_rating", "anticheat"}
)
"""The tables a reference to a missing row gives a blank row, as the notebook's did."""

CHUNK: Final = 500
"""Keys per ``IN`` list, well under SQLite's limit on bound parameters."""

_REPLACED: Final = frozenset(
    {"offer_price", "creator", "trailer", "store_category", "tag", "genre", "language"}
)
_KNOWN: Final = frozenset({"review_score", "rating_agency", "age_rating", "anticheat"})
_GROUPED: Final[Mapping[str, tuple[str, ...]]] = {
    "offer_discount": ("kind", "id", "country"),
    "offer_app": ("kind", "id", "country"),
    "offer_category": ("kind", "id"),
    "offer_content_descriptor": ("kind", "id"),
}
_TABLES: Final = cast("Mapping[str, Table]", SteamBase.metadata.tables)


class ForeignKeyViolationError(RuntimeError):
    """A load would leave references to rows that don't exist; nothing of it was written."""

    def __init__(self, violations: Mapping[str, int]) -> None:
        """
        Name the tables holding the broken references.

        :param violations: How many broken references each table holds.
        """
        named = ", ".join(f"{table} ({count})" for table, count in sorted(violations.items()))
        super().__init__(f"the load would break foreign keys in {named}; nothing was written")
        self.violations: dict[str, int] = dict(violations)
        """How many broken references each table holds."""


def check_foreign_keys(connection: Connection) -> None:
    """
    Check every reference in the database, as the spec asks before a load commits.

    :param connection: The load's connection.
    :raise ForeignKeyViolationError: When a reference points at a row that doesn't exist.
    """
    violations = Counter(row[0] for row in connection.exec_driver_sql("PRAGMA foreign_key_check"))
    if violations:
        raise ForeignKeyViolationError(violations)


def _complete(table: Table, rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """
    Give every row a value for every column it may hold, blank where it has none.

    :param table: The table.
    :param rows: Its rows, which may each leave out different columns.
    :return: The rows, all with the same columns, as one ``executemany`` needs.
    """
    columns = [column.name for column in table.columns if column.computed is None]
    return [{column: row.get(column) for column in columns} for row in rows]


class Writer:
    """Write a load's rows, keeping what it finds and what it writes."""

    def __init__(self, connection: Connection, *, home: str) -> None:
        """
        Prepare to write on *connection*, reading the lookups already stored.

        :param connection: The load's connection, inside its transaction, foreign keys off.
        :param home: The profile's home country, whose word on an offer stands.
        """
        self._connection = connection
        self._home = home
        self._known: dict[str, dict[tuple[object, ...], dict[str, object]]] = {}
        for name in _KNOWN:
            table = _TABLES[name]
            keys = [column.name for column in table.primary_key.columns]
            self._known[name] = {
                tuple(row[key] for key in keys): dict(row)
                for row in connection.execute(select(table)).mappings()
            }
        self._credits: dict[tuple[str, int | None], int] = {}
        self.findings: Findings = Findings()
        """Lookup values that differ from the ones already known."""
        self.loaded: Counter[str] = Counter()
        """Rows written, by table."""
        self.blank_parents: Counter[str] = Counter()
        """Blank rows added for references to missing rows, by table."""

    def clear(self, tables: Iterable[type[SteamBase]], appids: Collection[int] | None) -> None:
        """
        Delete the rows of some apps, or every row, of some tables.

        :param tables: The tables.
        :param appids: The apps whose rows go, or ``None`` for every row.
        """
        for model in tables:
            table = cast("Table", model.__table__)
            if appids is None:
                self._connection.execute(delete(table))
                continue
            for chunk in itertools.batched(appids, CHUNK, strict=False):
                self._connection.execute(delete(table).where(table.c.appid.in_(chunk)))

    def apps(self, batch: Sequence[tuple[Described, str]]) -> None:
        """
        Replace apps in place: their own rows go, and what their store items say is written.

        :param batch: Each app's store item turned into rows, with the country that sent it.
        """
        self.clear(STORE_ITEM_TABLES, [described.item.id for described, _ in batch])
        combined = {True: Rows(), False: Rows()}
        groups: defaultdict[str, dict[tuple[object, ...], list[dict[str, object]]]]
        groups = defaultdict(dict)
        for described, country in batch:
            rows = described.rows
            for ref in described.credits:
                rows.add(
                    AppCredit,
                    appid=described.item.id,
                    role=ref.role,
                    position=ref.position,
                    credit_id=self._credit_id(ref),
                )
            for name, columns in _GROUPED.items():
                # A later answer's group replaces an earlier's, and an emptied group empties.
                by_group: dict[tuple[object, ...], list[dict[str, object]]]
                by_group = {key: [] for key in rows.replaced.get(name, ())}
                for row in rows.tables.get(name, ()):
                    by_group.setdefault(tuple(row[column] for column in columns), []).append(row)
                groups[name].update(by_group)
            for name, table_rows in rows.tables.items():
                if name not in _GROUPED:
                    combined[country == self._home].tables[name].extend(table_rows)
        # Blank parents only once every app's own row is in: one added between the two writes
        # would take the place of an app the second one writes, whose row then loses.
        self.write(combined[False], home=False, parents=False)
        self.write(combined[True], home=True, parents=False)
        grouped = self._groups(groups)
        for rows in (combined[False], combined[True], grouped):
            self._blank_parents(rows)

    def _groups(
        self, groups: Mapping[str, Mapping[tuple[object, ...], Sequence[dict[str, object]]]]
    ) -> Rows:
        """
        Replace groups of an offer's rows: those of its discounts, apps, categories, descriptors.

        :param groups: Each table's groups, by key, with their new rows, possibly none.
        :return: The rows written.
        """
        written = Rows()
        for name, by_group in groups.items():
            table = _TABLES[name]
            key = tuple_(*(table.c[column] for column in _GROUPED[name]))
            for chunk in itertools.batched(by_group, CHUNK, strict=False):
                self._connection.execute(delete(table).where(key.in_(chunk)))
            values = _complete(table, itertools.chain.from_iterable(by_group.values()))
            if values:
                self._connection.execute(insert(table).on_conflict_do_nothing(), values)
            written.tables[name].extend(values)
            self.loaded[name] += len(values)
        return written

    def write(self, rows: Rows, *, home: bool, parents: bool = True) -> None:
        """
        Write rows by their tables' rules; rows of an app's own tables must be cleared first.

        :param rows: The rows.
        :param home: Whether they came from the home country, whose word on an offer stands.
        :param parents: Whether to give references to missing rows blank ones.
        """
        for name, table_rows in rows.tables.items():
            table = _TABLES[name]
            values = _complete(table, table_rows)
            if name == "offer":
                self._offers(table, values, home=home)
            elif name in _REPLACED:
                self._connection.execute(insert(table).prefix_with("OR REPLACE"), values)
            elif name in _KNOWN:
                self._lookups(table, values)
            else:  # an app's own rows, cleared first; an offer's groups are replaced by apps()
                self._connection.execute(insert(table).on_conflict_do_nothing(), values)
            self.loaded[name] += len(values)
        if parents:
            self._blank_parents(rows)

    def _offers(self, table: Table, values: Sequence[Mapping[str, object]], *, home: bool) -> None:
        """
        Merge offers: a column takes the newer value Steam sent, but abroad only fills blanks.

        :param table: The ``offer`` table.
        :param values: Its rows.
        :param home: Whether they came from the home country.
        """
        statement = insert(table)
        new, old = statement.excluded, table.c
        merged = {}
        for column in table.columns:
            if column.primary_key:
                continue
            name = column.name
            if name in COUNTRY_DEPENDENT and not home:
                merged[name] = coalesce(old[name], new[name])
            else:
                merged[name] = coalesce(new[name], old[name])
        upsert = statement.on_conflict_do_update(index_elements=["kind", "id"], set_=merged)
        self._connection.execute(upsert, list(values))

    def _lookups(self, table: Table, values: Sequence[Mapping[str, object]]) -> None:
        """
        Merge lookup values, reporting one that differs from the value already known.

        :param table: The lookup table.
        :param values: Its rows.
        """
        keys = [column.name for column in table.primary_key.columns]
        known = self._known[table.name]
        for row in values:
            stored = known.setdefault(tuple(row[key] for key in keys), {})
            for column, value in row.items():
                if column in keys or value is None:
                    continue
                if stored.get(column) not in (None, value):
                    self.findings.mismatches[f"{table.name}.{column}"] += 1
                stored[column] = value
        statement = insert(table)
        merged = {
            column.name: coalesce(statement.excluded[column.name], table.c[column.name])
            for column in table.columns
            if not column.primary_key
        }
        self._connection.execute(
            statement.on_conflict_do_update(index_elements=keys, set_=merged), list(values)
        )

    def _credit_id(self, ref: CreditRef) -> int:
        """
        Give a credit its id, numbering it the first time it appears.

        :param ref: The credit, as a store item names it.
        :return: Its id.
        """
        key = (ref.name, ref.creator_id)
        if key not in self._credits:
            self._connection.execute(
                insert(Credit).on_conflict_do_nothing(),
                [{"name": ref.name, "creator_id": ref.creator_id}],
            )
            found = select(Credit.credit_id).where(Credit.name == ref.name)
            found = found.where(
                Credit.creator_id.is_(None)
                if ref.creator_id is None
                else Credit.creator_id == ref.creator_id
            )
            self._credits[key] = self._connection.execute(found).scalar_one()
            credit = Rows()
            credit.add(
                Credit, credit_id=self._credits[key], name=ref.name, creator_id=ref.creator_id
            )
            self._blank_parents(credit)
        return self._credits[key]

    def _blank_parents(self, rows: Rows) -> None:
        """
        Give every reference in *rows* to a missing row of a filled table a blank row.

        The keys come from the rows themselves, through the tables' foreign keys, so nothing
        scans a table.

        :param rows: Rows just written.
        """
        for name, table_rows in rows.tables.items():
            for constraint in _TABLES[name].foreign_key_constraints:
                parent = constraint.referred_table
                if parent.name not in FILLED_PARENTS:
                    continue
                columns = [column.name for column in constraint.columns]
                targets = [element.column.name for element in constraint.elements]
                keys = {tuple(row.get(column) for column in columns) for row in table_rows}
                missing = [dict(zip(targets, key, strict=True)) for key in keys if None not in key]
                if not missing:
                    continue
                before = self._changes()
                self._connection.execute(insert(parent).prefix_with("OR IGNORE"), missing)
                self.blank_parents[parent.name] += self._changes() - before

    def _changes(self) -> int:
        """
        Tell how many rows this connection has changed so far.

        :return: SQLite's ``total_changes()``.
        """
        return int(self._connection.exec_driver_sql("SELECT total_changes()").scalar_one())
