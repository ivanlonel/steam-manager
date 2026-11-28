# Milestone 1, part 8: the loader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

The roadmap (`docs/superpowers/plans/README.md`) marks the **loader** as next. Parts 2–7 built the transport, the Steam endpoints and payload models, the raw archive, the Steam tables and the reports. Nothing yet turns archived answers into rows, so the database stays empty. The loader is the seam of ADR 0002: a sync, a rebuild and a Kaggle import all go through it.

The owner decided on 2026-11-28:

- **Review totals:** every app whose chosen answer has a review summary gets an `app_review_total` row. Wishlisted DLC get scores, and they show in `v_games`.
- **Failed answers rank last:** an answer whose `success` isn't 1 (such as 15, "not sold in this country") counts as the least complete. So a fallback country's data beats the home country's empty answer.

The work is cut into **two pull requests** so that each stays under Sourcery's 150,000 characters:

- **PR A:** a store item into rows. Pure functions, no database writes.
- **PR B:** choosing answers and writing the database.

**Goal:** `load(archive, engine, countries=…)` makes the Steam tables reflect the raw archive. It loads only what changed, replaces apps in place, and reports the fields nothing stores and the derived values that didn't follow.

**Architecture:** a new package, `src/steam_manager/loader/`.

- **PR A**
  - `rows.py`: `Rows` (rows per table, with column names checked) and `Findings` (the two reports).
  - `offers.py`, `media.py` and `store_item.py`: the notebook's cell 4 ported to the typed models. `describe(item)` returns the rows of one store item.
- **PR B**
  - `reviews.py`, `lookups.py` and `account.py`: the other answer kinds, also pure.
  - `write.py`: the merge rules per table, the blank parents and the foreign-key check.
  - `__init__.py`: `load` and `rebuild`.
- **Progress:** a Steam table, `loaded_answer`, records each answer the database reflects. It is dropped with the Steam tables, so a schema change reloads everything.
- **Transactions:** a load is one transaction. An interrupted load rolls back, and the next load redoes it.

**Tech Stack:** Python 3.15, Pydantic 2.13 (the existing `steam.models`), SQLAlchemy 2.1 Core, SQLite, pytest and Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md` (*Loader*, *Derived figures*, *Database*, *Raw archive*, and *New fields* under *Steam endpoints*). For which values are left out as derivable and how each is derived, the authority is notebook cells 4–6 (`../steam-collection/steam-database/steam-database.ipynb`). For the review estimate and the purchase-type rule, it is `steam-games.ipynb` cells 5–6.

## Global Constraints

- **Code:** Python `>=3.15`; lines up to 99; complete typing; Sphinx docstrings. Tests come first, each seen failing. Tests mirror `src/` (`loader/offers.py` → `tests/steam_manager/loader/test_offers.py`, `loader/__init__.py` → `test___init__.py`).
- **SQL:** every interaction with SQLite goes through SQLAlchemy 2.1. `PRAGMA foreign_keys` changes only outside a transaction: read it back before relying on it, as `db/steam_schema.py` does.
- **Secrets and privacy:** no answer body, and no value from one, appears in an exception, a log line or the report. A malformed answer is named by source, kind, key and country, and by pydantic's error locations and types (`errors(include_input=False)`).
- **Report, don't drop:** every field a store item sends is stored, checked as derivable, or explicitly taken as not stored, with the reason in a comment. Both reports are empty on every recorded fixture.
- **Vocabulary:** *answer*, *app*, *full entry*, *light entry*, *offer*, *home country*, *fallback country*, *rebuild* (GLOSSARY.md). Never "response", "record", "stub" or "reload".
- **Pull requests:** never drafts. Run `just check` and the docs build first. Keep each under 150,000 characters (`git diff main...HEAD | Measure-Object -Character` in PowerShell). Handle Sourcery's first assessment only (memory). Merge by rebase.

## Decisions this plan makes (builder's calls, except where marked as the owner's)

| Topic                                                | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Why                                                                                                                                                                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ranking (owner, 2026-11-28)                          | Own answers are ordered by (full 0 / light 1, the country's place in `countries` or after all of them, latest first). They are parsed in that order, and the first with `success == 1` wins; when none succeeds, the first one wins.                                                                                                                                                                                                                                                                  | "The most complete one wins": an empty answer isn't complete.                                                                                                                                                        |
| Short records nested in another app                  | Taken from the full entries parsed in this load, best per app by country order, then latest. One is loaded only for an app with no row, a row without a name, or a row whose `success` isn't 1.                                                                                                                                                                                                                                                                                                       | As in the notebook, they only fill gaps. Ceiling: an app keeps an earlier nested record until a rebuild.                                                                                                             |
| Progress and interruption                            | `loaded_answer(source, kind, key, country, fetched_at TEXT)` is a Steam table, written in the load's own transaction. A load streams `Archive.stamps()` into a TEMP table. The changed answers are those whose `fetched_at` differs from `loaded_answer`'s, found with one SQL join.                                                                                                                                                                                                                  | The spec's second option: the progress is dropped with the Steam tables. One mechanism covers a sync, a resume after a crash and a first open after a schema change, and memory stays flat on a 200,000-app catalog. |
| Transactions                                         | One per `load` call: foreign keys off, then `PRAGMA foreign_key_check`, then commit. Violations roll back and raise `ForeignKeyViolationError` with the count per table. Apps are written 500 at a time (`LOAD_BATCH`) inside the transaction.                                                                                                                                                                                                                                                        | This is the spec's text. Ceiling: on a full catalog the check scans every table (tens of seconds), and the WAL grows to the size of what changed. Batched commits are the upgrade path if that hurts.                |
| `rebuild`                                            | The same transaction first deletes every Steam table's rows (`loaded_answer` included), then loads.                                                                                                                                                                                                                                                                                                                                                                                                   | An interrupted rebuild leaves the previous state, never half of one. An emptied archive empties the tables.                                                                                                          |
| Merge rules for shared rows                          | See *Write rules* in Task B4. Within a load, a later occurrence of a key replaces an earlier one.                                                                                                                                                                                                                                                                                                                                                                                                     | The newest answer wins, as it does for apps. Ceiling: an older answer loaded later wins a shared row. The Kaggle import (part 11) adds a `fetched_at` guard.                                                         |
| Offer fields that depend on the country (owed)       | `success`, `unavailable_for_country_restriction`, `best_kind` and `best_id`: a home-country answer overwrites them, and another country's answer only fills a blank. Every other offer column takes the newer non-blank value.                                                                                                                                                                                                                                                                        | No country column, and no provenance needed. No report reads them.                                                                                                                                                   |
| Review totals (owner, 2026-11-28)                    | `n` = `summary_filtered.review_count` and `p` = its `percent_positive`. Exact counts come from archived `app_reviews` answers, under the source `steam` only: the app's purchase type (1 if free, else 0) when its total is within 2% of `n`, else the total closest to `n`; an answer whose total is 0 is ignored. Without exact counts: `n ≤ 100` gives `ceil(p·n/100)` and `counts_exact = 1`; above that, `min(n·(2p+1)//200, n)` and `counts_exact = 0`. No summary and no exact counts: no row. | `steam-games.ipynb` cells 5–6, verbatim. The Kaggle import adds its own source.                                                                                                                                      |
| `reviews.counts_all_purchases` (new field)           | Stored as `app.counts_all_purchases`, appended.                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Fixtures: true on the three free apps, absent on paid ones. Storing it beats guessing a derivation.                                                                                                                  |
| `extra_details.dlc_for_purchase` (new field)         | A new table, `app_dlc(appid, dlc_appid, position, packageid, highlight_reason)`: key `(appid, dlc_appid)`, both columns foreign keys to `app`, `STRICT, WITHOUT ROWID`. `dlc_count` is checked against the list's length. Each DLC's `content_descriptorids` are checked against the nested record of the same DLC in the same answer. `formatted_total_price` goes to `app.dlc_formatted_total_price`, appended.                                                                                     | Every recorded entry follows both checks (checked 2026-11-28). The package id isn't derivable: 620's soundtrack has none in its nested record.                                                                       |
| Histogram `count_all_reviews`, `expand_graph` (owed) | `count_all_reviews` becomes `app_review_histogram.count_all_reviews`, appended. `expand_graph` is taken but not stored: it is how the store page draws the graph.                                                                                                                                                                                                                                                                                                                                     | One qualifies the histogram's totals (why they differ from `review_count`); the other is display.                                                                                                                    |
| Other fields left out (owed)                         | Not stored, each taken with a comment: the tag list's `version_hash` (a list version), and `GetAppReviews`' `cursor`, `day_range_used`, `total_matching` and `num_reviews` (paging of the one-review query). Checked: `total_reviews = positive + negative`, and `review_score_desc` against `review_score`'s label (the notebook's `known()`).                                                                                                                                                       | Facts about the query, not about the app.                                                                                                                                                                            |
| `event_gid` (owed)                                   | \`str                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | None`in`SalePage`and`Milestone\`. The columns are already TEXT.                                                                                                                                                      |
| `app_genres` with `data: []` or a `null` part (owed) | The model reads `data: []` as `None`, and the root as \`dict\[str, AppGenres                                                                                                                                                                                                                                                                                                                                                                                                                          | None\]\`.                                                                                                                                                                                                            |
| Negative discounts (owed)                            | Steam's `discount_pct` is checked against the generated column's own rule: SQLite `ROUND`, half away from zero, on `100.0·(original − final)/original`.                                                                                                                                                                                                                                                                                                                                               | A mismatch then means the database shows something other than what Steam says.                                                                                                                                       |
| `*_in_cents` in zero-decimal currencies (owed)       | Record `store_item/620-JP.json` and pin `final_price_in_cents / 100` against the number in `formatted_final_price`. If that isn't so, stop and ask the owner: `v_games.price` divides by 100.                                                                                                                                                                                                                                                                                                         | Verify, don't trust.                                                                                                                                                                                                 |
| `is_listed`                                          | 1 when the latest listing of any of the profile's countries holds the app. 0 when it doesn't, and the app is a game, mod or software (`LISTED_TYPES = {0, 2, 6}`, what `list_apps` asks for). Blank otherwise, and before any listing. A live test pins the type codes.                                                                                                                                                                                                                               | The notebook's meaning, "listed on either store", without calling a DLC delisted.                                                                                                                                    |
| Lookups and account lists                            | `store_categories`, `tags`, `wishlist` and `followed_apps`: the latest answer of the kind, whatever its key, loaded when that answer changed. Lookups are upserted (never deleted: apps reference them). The wishlist and followed apps are replaced whole, deleting before inserting.                                                                                                                                                                                                                | The latest fetch follows a language change. `wishlist_item.position` is UNIQUE and not deferrable.                                                                                                                   |
| Language names                                       | `LANGUAGES`, from steam-games cell 3 (ids 0–29 and 30 "Indonesian"), upserted into `language` on every load.                                                                                                                                                                                                                                                                                                                                                                                          | No endpoint lists them; it is Steam's fixed ELanguage list, checked by the notebook.                                                                                                                                 |
| Current players                                      | `UPDATE app SET current_players` (an upsert when the app has no row) for each changed `current_players` answer, and for each reloaded app that has one. `result` other than 1, or a 404 body, gives blank.                                                                                                                                                                                                                                                                                            | The figure is an app column, but its answer isn't the store item's.                                                                                                                                                  |

## Review Focus

1. **An app the home store doesn't sell:** BR answers `success: 15`, and US has a full entry. The app's row comes from the US, with `store_country = "US"` and no price in `v_games`. Test in Task B4.
1. **Steam removed a tag:** a newer entry without the tag loads, and the tag's row is gone. Another app's rows, and a bundle price the two share, stay. Test in Task B4.
1. **A load interrupted midway** (an exception in the second batch): nothing is committed, neither rows nor `loaded_answer`, and the next load loads everything. Test in Task B4.
1. **A truncated answer and a damaged archive row among good ones:** both are reported by key, with no body text. The rest load, and an app whose best answer is malformed gets its next candidate. Test in Task B4.
1. **A wishlist reordered on Steam** (two apps swap places): it is replaced without a UNIQUE error, and the positions follow the new order. Test in Task B5.

______________________________________________________________________

## PR A: a store item into rows (`feat/loader-rows`)

### Task A1: Fields Steam added, and the model fixes

**Files:**

- Modify `src/steam_manager/steam/models/details.py` and `models/lookups.py`.
- Modify `src/steam_manager/db/schema/apps.py`, `reviews.py` and `relations.py`.
- Tests:
  - create `tests/steam_manager/steam/models/test_details.py`;
  - modify `models/test_lookups.py`, and `db/schema/test_apps.py`, `test_reviews.py` and `test_relations.py`.

**Interfaces (produces):**

- `App.counts_all_purchases: Mapped[bool | None]` and `App.dlc_formatted_total_price: Mapped[str | None]`, the last two columns.

- `AppReviewHistogram.count_all_reviews: Mapped[bool | None]`, last.

- `AppDlc` (`app_dlc`) as decided.

- `App.is_listed`'s docstring takes the `is_listed` rule.

- [ ] **Step 1: failing tests**

  - `test_event_gids_stay_text`: `SalePage` and `Milestone` validated with `{"event_gid": "18446744073709551615"}` keep that string.
  - `test_genres_without_data_validate`: `{"1": {"success": true, "data": []}}` gives `data is None`, and `{"1": null}` gives a `None` part.
  - The schema comparisons expect the three new columns as `only declared:` lines (the form in `test_lookups.py`), and `app_dlc` as declared only, the way `app_compatibility_test` is.
  - `test_app_dlc_keys_and_references`: primary key `(appid, dlc_appid)`, and both reference `app.appid`.

- [ ] **Steps 2–5:** see them fail; implement; see them pass; commit `feat(db): store the fields Steam added since the notebooks`.

### Task A2: `Rows` and `Findings` (`loader/rows.py`)

**Files:** create `src/steam_manager/loader/__init__.py` (a docstring only, for now) and `loader/rows.py`. Tests: `tests/steam_manager/loader/__init__.py` and `test_rows.py`.

**Interfaces (produces):**

- `class Rows`:

  - `tables: dict[str, list[dict[str, object]]]`, keyed by table name, in insertion order;
  - `add(self, table: type[SteamBase], /, **values: object) -> None` raises `ValueError` naming the table and the column, for a column the table lacks or a generated one;
  - `extend(self, other: Rows) -> None`.

- `@dataclass class Findings`:

  - `unknown: Counter[str]` ("fields Steam sent that nothing stores") and `mismatches: Counter[str]` ("values left out as derivable that didn't follow");
  - `rest(self, model: BaseModel | None, path: str, used: Collection[str]) -> None` counts each field of `model`, declared or extra, that is not in `used` and not empty (`None`, `()`, `[]`, `{}`; `""` counts), at `f"{path}.{name}"`. It raises `ValueError` when `used` names a field the model doesn't declare;
  - `same(self, name: str, stored: object, derived: object) -> None`;
  - `update(self, other: Findings) -> None`.

- `iso(seconds: int | None) -> str | None`: the notebook's `str(datetime(1970, 1, 1) + timedelta(seconds=…))`, with `None` for 0 or `None`.

- [ ] **Step 1: failing tests**

  - `test_a_row_for_a_missing_column_is_refused`
  - `test_a_generated_column_is_refused` (`OfferPrice.discount_pct`)
  - `test_rest_counts_fields_left_unused`: a declared field and an extra one, both counted at their paths; empty values not counted; `""` counted.
  - `test_rest_refuses_a_name_the_model_lacks`
  - `test_same_counts_only_differences`
  - `test_iso_writes_the_notebooks_text`: `iso(1302566400) == "2011-04-12 00:00:00"`, and `iso(0) is None`.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): collect rows and what they leave out`.

### Task A3: Offers and prices (`loader/offers.py`)

The notebook's `load_option` and `load_nested_offer`, on the models. `formatted_*` and `formatted_renewal_price` are now stored. `package_group` and `is_edition` are the caller's (`app_offer`).

**Files:**

- Create `loader/offers.py` and `tests/fixtures/steam/store_item/620-JP.json`.
- Test: `tests/steam_manager/loader/test_offers.py`.

**Interfaces (produces):**

- `COUNTRY_DEPENDENT: Final = frozenset({"success", "unavailable_for_country_restriction", "best_kind", "best_id"})`

- `purchase_option(option: PurchaseOption, path: str, country: str, rows: Rows, findings: Findings) -> tuple[str, int]` returns the offer's `(kind, id)`.

- `included_offer(kind: Literal["package", "bundle"], item: IncludedOffer, path: str, country: str, rows: Rows, findings: Findings) -> None`

- `sql_round(value: float) -> int`: half away from zero, as SQLite's `ROUND`.

- [ ] **Step 1: record JPY.** Run a one-off `uv run python` script, kept out of the repository: `get_items(transport, [620], country="JP")` through `make_client`. Write the item as JSON, indented by two, `ensure_ascii=False`, the way the other fixtures are. Store items carry no account data.

- [ ] **Step 2: failing tests**

  - `test_a_purchase_option_gives_its_price_and_discounts`: an option from `620-BR.json` gives an `offer_price` row with int cents and the `formatted_*` strings, and discount rows with `iso` end dates.
  - `test_discount_pct_is_checked_as_sqlite_rounds`: original 200, final 239. Steam's `-20` gives no mismatch; `-19` gives one `offer_price.discount_pct`.
  - `test_a_free_offer_derives_no_discount`: an original price of 0 or `None` expects `None`.
  - `test_an_included_offer_gives_its_apps_categories_and_options`: a recorded `included_bundles` item.
  - `test_yen_prices_are_in_hundredths`: in `620-JP.json`, each option's `final_price_in_cents / 100` equals the number in `formatted_final_price`, after stripping the symbol and separators. **If it fails, stop and ask the owner.**

- [ ] **Steps 3–5:** fail; implement; pass; commit `feat(loader): turn offers and prices into rows`.

### Task A4: Images and trailers (`loader/media.py`)

The notebook's `load_assets` and `load_media`.

**Interfaces (produces):**

- `assets(appid: int, assets: Assets | None, base: Assets | None, rows: Rows, findings: Findings) -> dict[str, int | None]` returns the app columns `assets_last_modified` and `assets_appid`.

- `screenshots(appid: int, screenshots: Screenshots | None, rows: Rows, findings: Findings) -> None`

- `trailers(appid: int, trailers: Trailers | None, rows: Rows, findings: Findings) -> None`

- [ ] **Step 1: failing tests**

  - `test_assets_mark_overrides_and_keep_the_base_file`
  - `test_assets_of_another_app_name_it`: `asset_url_format` under another appid sets `assets_appid`.
  - `test_trailers_give_their_files_and_positions`

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): turn images and trailers into rows`.

### Task A5: A store item (`loader/store_item.py`)

The rest of `load_app`:

- the app row and `app_text`;
- store categories, tags, languages, content descriptors and review summaries;
- credits, release dates, the free weekend, platforms and VR;
- the extra details;
- the age rating;
- the store lists;
- package groups and offers, adding the best option when `purchase_options` lacks it (as light entries do);
- related apps and the season pass;
- requirements;
- `hardware_compatibility` (into `app_compatibility_test`) and `dlc_for_purchase`.

The notebook's `known()` lookups become rows of the lookup tables (`review_score`, `rating_agency`, `age_rating`, `anticheat`). Their consistency across apps is checked in Task B4.

**Interfaces (produces):**

- `@dataclass(frozen=True, slots=True) class CreditRef`: `role: str`, `position: int`, `name: str`, `creator_id: int | None`.

- `@dataclass(slots=True) class Described`:

  - `item: StoreItem`;
  - `rows: Rows`;
  - `findings: Findings`;
  - `credits: list[CreditRef]`;
  - `nested: list[StoreItem]` (the `included_apps` records).

- `describe(item: StoreItem, *, country: str, category_types: Mapping[int, int]) -> Described`. It leaves `is_listed` and `current_players` blank: they are the writer's (Task B4).

- `STORE_ITEM_TABLES: Final[tuple[type[SteamBase], ...]]`: the tables one app owns, replaced per app.

- `SHARED_TABLES: Final[tuple[type[SteamBase], ...]]`: `offer`, `offer_price`, `offer_discount`, `offer_app`, `offer_category`, `offer_content_descriptor`, `creator`, `trailer` and the four lookups above.

- [ ] **Step 1: failing tests**

  - `test_a_recorded_entry_leaves_nothing_out`: parametrized over every recorded store item, full and light, and every nested record in them. Unknown fields are empty, and every mismatch count is 0.
  - `test_a_new_field_is_reported_at_its_path`: `extra_details.new_field` in `620-BR.json`.
  - `test_portal_2_gives_the_notebooks_rows`:
    - the app row's `name`, `type`, `store_country`, release date text and `counts_all_purchases`;
    - one `is_best` offer;
    - Valve credited as developer.
  - `test_dlc_on_sale_keep_steams_order`: `570-BR.json` gives two `app_dlc` rows in order, and `dlc_formatted_total_price == "R$33,99"`.
  - `test_compatibility_results_keep_steams_order`
  - `test_a_light_entry_keeps_its_best_price`: `10-BR.json` gives `offer_price` for package 7 in BR, with 3399 and `"R$33,99"`, and `app_offer.is_best`.
  - `test_an_app_not_sold_gives_a_bare_row`: `12170-BR.json` gives `success` 15 and `name` blank.
  - `test_described_rows_fit_the_schema`: every recorded entry's rows, inserted with plain inserts into in-memory `SteamBase` tables with foreign keys off, raise nothing. That means no STRICT error and no repeated key.
  - `test_every_table_is_owned_or_shared`: the tables of every recorded entry's rows are a subset of the union of `STORE_ITEM_TABLES` and `SHARED_TABLES`, which are disjoint.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): describe a store item as rows`.

### Task A6: Spec, plan and PR A

- **Spec, *New fields*:** where each new field went.
- **Spec, *Database*:**
  - the three appended columns and `app_dlc`;
  - `event_gid` as text;
  - `is_listed`'s meaning.
- **This plan:** saved as `docs/superpowers/plans/2026-11-28-m1-part8-loader.md`.
- **README:** row 8 reads "Loader (two PRs)".
- [ ] **Step 1:** `just check` and `just docs` pass, and the diff is under 150,000 characters.
- [ ] **Step 2:** commit `docs: record where the new fields went`.
- [ ] **Step 3:** push, open PR A, wait for green CI, then send one fresh reviewer on the most capable model. Fix the Critical and Important findings, each seen failing first. Merge by rebase.

______________________________________________________________________

## PR B: choosing answers and writing the database (`feat/loader`)

### Task B1: Stamps (`archive.py`)

**Interfaces (produces):**

- `class Stamp(NamedTuple)`: `source: str`, `kind: str`, `key: str`, `country: str`, `fetched_at: datetime`.

- `Archive.stamps(self, *, kinds: Collection[Kind] | None = None) -> Generator[Stamp]`: every answer's identity and time, never its body, streamed with `yield_per=STREAM_ROWS`.

- [ ] **Step 1: failing tests** (`test_archive.py`):

  - `test_stamps_list_answers_without_their_bodies`
  - `test_stamps_of_some_kinds`
  - `test_a_damaged_answer_still_has_a_stamp`

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(archive): list answers without their bodies`.

### Task B2: Review figures (`loader/reviews.py`)

**Interfaces (produces):**

- `estimate_positive(percent: int, count: int) -> int`

- `review_total(appid: int, summary: ReviewSummary | None, exact: Mapping[int, QuerySummary], *, is_free: bool | None, rows: Rows, findings: Findings) -> None` adds the `AppReviewTotal` row, or none. `exact` is keyed by purchase type. It also adds `ReviewScore` rows from the query summaries.

- `histogram(appid: int, answer: ReviewHistogramAnswer, rows: Rows, findings: Findings) -> None`

- `players(answer: CurrentPlayersAnswer, findings: Findings) -> int | None`

- [ ] **Step 1: failing tests**

  - `test_up_to_100_reviews_the_count_is_exact`: for every `n ≤ 100` and positive count `k`, `estimate_positive(100·k//n, n) == k`.
  - `test_above_100_the_midpoint_is_estimated`: `(50, 1000) → 505` and `(100, 1000) → 1000`; `counts_exact` is 0.
  - `test_exact_counts_prefer_the_apps_purchase_type_within_2_percent`
  - `test_exact_counts_otherwise_take_the_closest_total`
  - `test_a_query_without_totals_is_ignored`
  - `test_total_reviews_is_checked`
  - `test_a_histogram_gives_periods_and_recent_days`: `review_histogram-620.json`, with `count_all_reviews` stored as false.
  - `test_no_figure_gives_no_player_count`: result 42.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): work out review totals and histograms`.

### Task B3: Lookups and account lists (`loader/lookups.py`, `loader/account.py`)

**Interfaces (produces):**

- `LANGUAGES: Final[Mapping[int, str]]` and `languages(rows: Rows) -> None`.

- `store_categories(answer: StoreCategoriesAnswer, rows: Rows, findings: Findings) -> None`

- `tags(answer: TagListAnswer, rows: Rows, findings: Findings) -> None`

- `genres(answer: AppDetailsGenresAnswer, rows: Rows, findings: Findings) -> None`: genre ids sent as text become int.

- `wishlist(answer: WishlistAnswer, rows: Rows, findings: Findings) -> None`: positions start at 1 in Steam's order, as the notebook's line numbers did; priority 0 is blank; dates go through `iso`.

- `followed(answer: FollowedAppsAnswer, rows: Rows, findings: Findings) -> None`

- [ ] **Step 1: failing tests**

  - `test_store_categories_keep_show_in_search`
  - `test_the_tag_list_stores_names_and_skips_its_version`: neither stored nor reported.
  - `test_genre_ids_become_numbers`
  - `test_languages_name_steams_numbers`: 0 is `"English"`, 22 `"Portuguese - Brazil"` and 30 `"Indonesian"`.
  - `test_the_wishlist_keeps_steams_order`: unranked priority is blank.
  - `test_followed_apps`

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): turn lookups and account lists into rows`.

### Task B4: Loading store items (`loader/write.py`, `loader/__init__.py`, `db/schema/progress.py`)

**Write rules:**

| Tables                                                     | Rule                                                                                                                                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `STORE_ITEM_TABLES`                                        | The batch's apps' rows are deleted, then inserted with `ON CONFLICT DO NOTHING`, so a repeat within one answer keeps the first, as in the notebook.                      |
| `offer`                                                    | Upsert. A column takes the newer non-blank value (`COALESCE(excluded.c, c)`). For `COUNTRY_DEPENDENT`, a non-home answer only fills a blank (`COALESCE(c, excluded.c)`). |
| `offer_price`, `creator`, `trailer`                        | The whole row is replaced.                                                                                                                                               |
| `offer_discount`, `offer_app`                              | The offer's rows for that country are deleted, then inserted.                                                                                                            |
| `offer_category`, `offer_content_descriptor`               | The offer's rows are deleted, then inserted.                                                                                                                             |
| `credit`                                                   | Inserted once per `(name, creator_id)`. Existing ids are kept, and `AppCredit` rows take them.                                                                           |
| `review_score`, `rating_agency`, `age_rating`, `anticheat` | The newer non-blank value wins. A non-blank value that differs from the stored one counts as `"{table}.{column}"` in mismatches, as `known()` did.                       |
| `store_category`, `tag`, `genre`, `language`               | Upsert of the whole row, filling blank parents.                                                                                                                          |

**Blank parents:** `FILLED_PARENTS` is the notebook's set: `app`, `creator`, `offer`, `store_category`, `tag`, `genre`, `language`, `review_score`, `rating_agency`, `age_rating`, `anticheat` and `app_package_group`. For every `Rows` written, each foreign key into one of them gets its referenced keys inserted, with `ON CONFLICT DO NOTHING`. The keys come from the rows themselves, through SQLAlchemy's foreign-key metadata, never from a table scan.

**`load` steps,** in one connection and one transaction:

1. Turn foreign keys off and read them back (`RuntimeError` if they're still on). `CREATE TEMP TABLE stamp`, then insert `archive.stamps()` in chunks. `fetched_at` is `isoformat(timespec="microseconds")`.
1. *(Task B5)* Load languages, lookups and genres.
1. Find the changed store answers: the `store_item` and `store_item_light` stamps whose `fetched_at` differs from `loaded_answer`'s. For each changed appid, read all of its own stamps, rank them, and parse with `archive.get` until one succeeds. A malformed or damaged candidate goes to `LoadReport.malformed` and the next one is tried. Then call `describe`, passing `category_types` read from `store_category`, set `is_listed`, and write 500 apps at a time.
1. Load the best nested record for each gap, per the decision.
1. *(Task B5)* The remaining kinds.
1. Run `PRAGMA foreign_key_check`. On violations, roll back and raise. Otherwise upsert `loaded_answer` from the changed stamps, commit, turn foreign keys back on and drop the temp table.

**Files:**

- Create `src/steam_manager/loader/write.py` and `src/steam_manager/db/schema/progress.py` (`LoadedAnswer`), registered in `db/schema/__init__.py`.
- Modify `loader/__init__.py`.
- Tests: `tests/steam_manager/loader/test_write.py`, `test___init__.py` and a `conftest.py` with an archive and a database in `tmp_path`. Its helper is `put(archive, kind, key, country, path_or_body, at)`. Also `tests/steam_manager/db/schema/test_progress.py`, where the table is declared only.

**Interfaces (produces):**

- `@dataclass(frozen=True, slots=True) class Malformed`: `source`, `kind`, `key`, `country`, `reason: str`.

- `@dataclass class LoadReport`:

  - `unknown: Counter[str]`;
  - `mismatches: Counter[str]`;
  - `malformed: list[Malformed]`;
  - `loaded: Counter[str]`, by table;
  - `blank_parents: Counter[str]`.

- `class ForeignKeyViolationError(RuntimeError)`, with `violations: dict[str, int]`.

- `load(archive: Archive, engine: Engine, *, countries: Sequence[str]) -> LoadReport`: `countries` is the home country first, then the fallback countries in order. It raises `ValueError` when empty.

- `rebuild(archive: Archive, engine: Engine, *, countries: Sequence[str]) -> LoadReport`

- [ ] **Step 1: failing tests**

  - `test_write.py`:
    - `test_references_get_blank_parents`
    - `test_a_repeat_within_an_answer_keeps_the_first`
    - `test_home_offer_fields_overwrite_and_others_fill_blanks`
    - `test_a_lookup_conflict_is_a_mismatch`
  - `test___init__.py`:
    - `test_a_load_fills_the_tables`: `620-BR`, `570-BR` and the light `10-BR`. The rows land, the report's unknown fields and mismatches are empty, and `loaded["app"]` counts them.
    - `test_a_second_load_parses_nothing`: patch `describe` to count its calls, and expect 0.
    - `test_full_beats_light_and_home_beats_fallback`
    - `test_a_newer_answer_from_another_source_wins`: source `kaggle`, same kind, key and country.
    - `test_an_app_the_home_store_doesnt_sell_comes_from_the_fallback` (Review Focus 1). Build `12170-US` from `620-US.json` with its ids changed.
    - `test_a_removed_tag_disappears_and_shared_prices_stay` (Review Focus 2)
    - `test_an_interrupted_load_commits_nothing` (Review Focus 3): patch `describe` to raise on the second batch, with `LOAD_BATCH` patched to 1.
    - `test_malformed_answers_are_reported_and_skipped` (Review Focus 4): the message holds no body text.
    - `test_a_nested_record_fills_a_gap`: 104600 is only nested in 620. The record isn't used once 104600 has its own light entry.
    - `test_a_foreign_key_violation_rolls_back`: patch `FILLED_PARENTS` without `tag`.
    - `test_rebuild_forgets_what_the_archive_lost`

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): load store items, replacing apps in place`.

### Task B5: The other kinds in `load`

- **Languages, lookups and genres:** step 2 above.

- **`is_listed`:** the latest listing of each of the profile's countries. When any of them changed, every app's `is_listed` is recomputed and only the differences are written.

- **Current players:** as decided.

- **Review totals:** for the reloaded apps and the appids of changed `app_reviews`. The summary comes from the `Described` when the app was reloaded, else from `app_review_summary` (`filtered`) and `app.is_free`. The rows are deleted, then inserted.

- **Histograms:** for changed keys, `app_review_histogram` and `review_history` are deleted, then inserted.

- **Wishlist and followed apps:** each replaced whole.

- [ ] **Step 1: failing tests** (`test___init__.py`; `test_live.py`):

  - `test_lookups_come_from_the_latest_answer`
  - `test_is_listed_follows_the_profiles_listings`: listed is 1; a game outside the listings is 0; a DLC is blank; with no listing, blank.
  - `test_current_players_survive_a_reload`
  - `test_exact_counts_replace_the_estimate`: `app_reviews-620-0.json` gives positive 387851 and `counts_exact` 1.
  - `test_every_app_with_reviews_gets_totals`: a DLC gets a row (the owner's choice).
  - `test_a_reordered_wishlist_replaces_the_old_one` (Review Focus 5)
  - `test_reports_read_what_was_loaded`: after `create_views(engine, home_country="BR")`, `v_games` shows Portal 2 with its BR best offer's price and exact counts.
  - live: `test_the_listing_type_filters_match_the_type_codes`. A `Query` with only `include_mods` gives type 2, and with only `include_software` type 6.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): load lookups, review figures and the account lists`.

### Task B6: Spec, roadmap, changelog and PR B

- **Spec, *Loader*:**

  - both of the owner's 2026-11-28 decisions;
  - `loaded_answer`, one transaction per load, and `rebuild`;
  - the write rules;
  - nested records;
  - `is_listed`;
  - lookups from the latest answer;
  - language names.

- **Spec, *Database*:** the interrupted-rebuild paragraph now names the settled option.

- **README:**

  - move the loader's owed items out as settled;
  - add, under Kaggle import, the `fetched_at` guard for shared rows and `app_reviews` from other sources;
  - add, under Sync, calling `load` after each step and on open, `rebuild` when the countries change, and that the foreign-key check costs tens of seconds on a full catalog;
  - add the review's deferred minors.

- **CHANGELOG:** "Loader: fills the database from the raw archive, loading only what changed, and reports fields nothing stores and values that don't follow."

- [ ] **Step 1: live smoke.** Run a scratchpad script, not committed. Into a temporary archive, fetch:

  - `get_items` for 620, 570 and 1172470 in BR, and 12170 in BR and US;
  - `store_categories` and `tag_list`;
  - `app_reviews` for 620;
  - `review_histogram` for 620;
  - `current_players` for 570.

  Then `load(countries=["BR", "US"])` and `create_views`. Expect empty `unknown` and `mismatches`, and `v_games` rows for those apps.

- [ ] **Step 2:** `just check` and `just docs` pass; diff under 150,000 characters; commit `docs: record the loader's decisions`.

- [ ] **Step 3:** PR B, CI, one fresh reviewer, the fix pass, then merge by rebase. Report every ruling and deferred minor to the owner. Delete the ledger.

## Verification

- **Per task:** each named test is seen failing, then passing.
- **Fixtures:** every recorded store item, and every nested record in one, describes with empty `unknown` and zero `mismatches`. Their rows insert into the real schema.
- **End to end:** the Review Focus tests. `v_games` reads loaded rows. The live smoke sees no new field and no mismatch on today's answers.
- **Gates:** `uv run pytest` at full branch coverage, `uv run prek run --all-files`, the docs build, and CI on Ubuntu, Windows and macOS for each PR.

## Execution

Inline (`superpowers:executing-plans`), with the ledger at `.superpowers/sdd/2026-11-28-m1-part8-loader/progress.md`, kept by hand. Each PR ends with one fresh reviewer on the most capable model before its merge.

## Rulings during execution

PR A is split in two, each under 150,000 characters:

- **PR A1:** the fields Steam added, with their recording, the spec's account of them, and this
  plan.
- **PR A2:** the loader's rows.

PR A1:

- Recording Portal 2 from the Japanese store, and a probe of the Brazilian one, showed three
  fields Steam added after 2026-11-15:
  - `related_items.provides_engine_appid` goes to `app_related`, of kind `engine`;
  - `basic_info.featured_creator_home_clan_account_ids` goes to a new table,
    `app_featured_creator`. It can't be derived: Half-Life 2 features Valve though its first
    franchise has a creator page of its own;
  - `basic_info.first_franchise_clan_account_id` is checked, only when sent, against the first
    franchise's creator page.
- The committed recording is Half-Life: Alyx's, `546560-JP` (24 kB), instead of Portal 2's
  (98 kB). It has a yen price and two of the three new fields; a hand-built entry covers the
  engine.
- Yen prices are in hundredths (¥8,450 is 845000), so `v_games.price` holds.

PR A2:

- `Rows.add` refuses a blank for a column that can't be blank. Such an answer is then reported
  as malformed, instead of failing the whole load at the insert.
- `describe` takes a `path`, so a nested record's fields are reported at their full path.
- The extra details live in `loader/details.py`, and the shared helpers in `loader/rows.py`, to
  keep `store_item.py` under pylint's 1,000 lines.
- Signatures follow pylint's limit of five positional arguments: `included_offer`'s `kind` and
  `_offers`' `country` are keywords. The media functions' parameters are renamed so they don't
  shadow their functions.
