# Milestone 1, part 7: the reports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

Milestone 1 needs the notebooks' four public views: `v_app_scores`, `v_games`, `v_wishlist` and `v_followed`. The notebook builds them in Python (cell 7) with Brazil written in. Now that an application layer consumes the data, the owner chose (2026-11-16):

- **Definition:** each report is a SQLAlchemy `select()` in Python, used directly by the application with the profile's home country passed in. The same queries are written into `steam.sqlite` as `v_*` views on every open, with the home country filled in, so other SQLite tools see them.
- **Shape:** parity with the notebook's columns, except that the store categories become one list column, `store_categories`, instead of one true/false column per category.
- **Fallback data:** an app the home store didn't describe shows its data from whichever store did, with a `store_country` column and **every price blank**. The same rule holds in every report: a price in another currency never appears.
- **Dropped:**
  - `recommended_sort_order`; `original_sort_order` stays;
  - `on_notion`, for good: it means the owner's personal shared Notion database.
- **`v_games` account columns:** `owned`, `ignored` and the tracking status arrive with their data in milestone 2.

**Goal:** the four reports as typed, tested `select()`s, written into the file as views, matching the notebook's views on the same data except where the owner changed them.

**Architecture:**

- **`src/steam_manager/db/reports/`:**
  - `scores.py`: the score expressions, with the Bayes prior and the Wilson bound written into each report on its totals alias, as cell 7 does. Plus `app_scores()`.
  - `games.py`: `games(home_country)`.
  - `store_columns.py`: the store columns `v_wishlist` and `v_followed` share.
  - `wishlist.py`: `wishlist(home_country)`.
  - `followed.py`: `followed(home_country)`.
  - `__init__.py`: `reports(*, home_country: str) -> dict[str, Select[Any]]`, keyed by view name, and `create_views(engine, *, home_country: str) -> None`. For each report it runs `DROP VIEW IF EXISTS`, then `CreateView(select)` with the country as a literal, in one transaction.
- **Tests:** the notebook's own view SQL becomes a fixture, `tests/fixtures/notebook/steam_database_views.sql`. A helper builds two in-memory databases from the same sample rows, one with the notebook's DDL and views, the other with `SteamBase` and `create_views(home_country="BR")`, and compares the views:
  - column names in order, with the intended differences as an edit list;
  - values, row by row, on rows the home store described.

**Tech Stack:** Python 3.15, SQLAlchemy 2.1.8 Core (`select`, `aliased`, `case`, `func`, `scalar_subquery`, `CreateView`), SQLite JSON functions, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md` (*Goals*, *Database*, *Loader*, *Derived figures*, *Exports*, *Reference material*). Notebook cell 7 is authoritative for the column names and formulas; `compare_db.py` is the acceptance check the parity tests mirror.

## Global Constraints

- **Code standards:** Python `>=3.15`; lines up to 99; complete typing; Sphinx docstrings. Test first: watch each test fail before writing its code. Tests mirror `src/`: `db/reports/games.py` → `tests/steam_manager/db/reports/test_games.py`.
- **SQL:** every interaction with SQLite goes through SQLAlchemy 2.1, so reports are Core expressions over the ORM classes (`App`, `OfferPrice`…), not SQL text, and a renamed column fails at import and in type checking.
- **Vocabulary:** a **report** (new glossary term) is the query; a **view** is its copy in the file. *Store category* is never just "category".
- **Pull request:** one PR, never a draft; hooks, the suite and the docs build all pass first; merged by rebase. Sourcery's budget returns on 2026-11-18: keep the diff under 150,000 characters (`git diff main...HEAD | Measure-Object -Character`).

## Decisions this plan makes (builder's calls)

| Topic                         | Decision                                                                                                                                                                                                                                                                          | Why                                                                                                                                                                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| The price rule, mechanically  | `offer_price` and `offer_discount` join on **`country = home_country`**, not on `app.store_country`. Every column read from them is then blank for an app with no home-country price, and `v_games.price` drops the notebook's `IIF(store_country = 'BR', …)`.                    | One join condition implements "a price in another currency never appears" in all four reports. For apps the home store described, it gives exactly the notebook's values.                  |
| Fallback data in `v_wishlist` | The store columns read `app` unfiltered (the notebook joined it `AND store_country = 'BR'`). `store_country` is added after `visible`. `unvailable_for_country_restriction` is 1 when `store_country` isn't the home country. `success` and `visible` are the describing store's. | The owner's choice: show the fallback store's data. The flag still tells the user the home store doesn't sell the app.                                                                     |
| `store_categories`            | A JSON array of the app's store categories' `internal_name`s, ordered by `categoryid`, blank when it has none. It sits where the per-category columns were: after the last store column, before `genres`.                                                                         | Those names were the old columns' names, so the data and its order carry over.                                                                                                             |
| Notebook views fixture        | Cell 7 run against the cell-2 schema with no store or wishlist categories, keeping `v_app_scores`, `v_games`, `v_wishlist` and `v_followed`. The fixture's header gives the recipe.                                                                                               | Mechanical parity, as with the DDL. An empty database puts no account data in the file.                                                                                                    |
| Re-creating views             | `create_views` drops and re-creates the current reports' views on every call. It never fingerprints them and never touches other views.                                                                                                                                           | Views hold no data, so re-creating them costs milliseconds and can't go stale. A user's own views stay. ponytail: a report a later release retires needs its name dropped by that release. |
| Scores                        | The prior (`AVG` over rated `app_review_total` rows) and the 99% Wilson bound (z = 2.5758293035489004) as uncorrelated scalar subqueries, written into each report as the notebook does, not joined from `v_app_scores`.                                                          | Cell 7's measured reason: joining the view cost about 25 ms a row.                                                                                                                         |
| Callers                       | Nothing calls `create_views` yet. The sync stage calls `ensure_steam_schema` and then `create_views` with the profile's home country.                                                                                                                                             | No profile-open code exists yet.                                                                                                                                                           |
| `v_games.price`               | Cents divided by 100, as the notebook does.                                                                                                                                                                                                                                       | Whether Steam's `*_in_cents` are hundredths in zero-decimal currencies (JPY) is for the loader stage to check against a recorded answer; the formatted strings are always Steam's own.     |

## Review Focus

1. **An app only a fallback store described** shows its reviews, description and tags, `store_country` names that store, every price column is blank and `unvailable_for_country_restriction` is 1, in both `v_wishlist` and `v_followed`. Test in Tasks 3 and 4.
1. **A free app, or one without a price row,** has a blank price in `v_games`, not 0, and isn't dropped from the report. Test in Task 2.
1. **No rated apps at all** (an empty catalog, or zero reviews everywhere): the scores are blank, with no division error. Test in Task 1.
1. **A changed home country:** calling `create_views` again with another country changes which prices the views show, and replaces the old views. Test in Task 2.
1. **A view from an older release**, under a report's name but with different SQL, is replaced, while a view of the user's own (`v_mine`) survives. Test in Task 1.

______________________________________________________________________

### Task 1: The machinery, the fixture, and `v_app_scores`

**Files:**

- Create `src/steam_manager/db/reports/__init__.py` and `scores.py`.
- Create `tests/fixtures/notebook/steam_database_views.sql`.
- Create `tests/steam_manager/db/reports/__init__.py`, `_parity.py`, `test_init.py` and `test_scores.py`.
- Modify `GLOSSARY.md`, adding **Report**: "A named table of results over the database, such as the games or the wishlist, which the application computes and also writes into the database as a view. _Avoid_: View (for the report itself), tab."

**Interfaces (produces):**

- **`reports(*, home_country: str) -> dict[str, Select[Any]]`:** keyed `v_app_scores`, `v_games`, `v_wishlist`, `v_followed`. Each task adds its report.

- **`create_views(engine: Engine, *, home_country: str) -> None`:** described under *Architecture*.

- **`_parity.py`:**

  - `notebook_views() -> sqlite3.Connection` builds the fixture DDL plus its views;
  - `ours(home_country: str = "BR") -> Engine` builds the `SteamBase` tables plus `create_views`;
  - `load(sample: Mapping[str, Sequence[Mapping[str, object]]])` inserts the same rows into both;
  - `columns(view)` and `rows(view)` read either side, ordered by `appid`.

- **Fixture recipe** (also in its header): `exec` cell 7 with `conn` on the cell-2 schema, `lookups={"store_categories": []}` and `item_counts={}`. Then write `sqlite_schema.sql` for the four views, each followed by `;`.

- [ ] **Step 1: failing tests**

  - `test_app_scores_has_the_notebooks_columns`: same names, same order.
  - `test_app_scores_matches_the_notebook_on_the_same_rows`:
    - sample: 3 apps with totals, one with exact counts and one estimated, plus review summaries and history rows;
    - compares bayes and wilson to 1e-9, the rest exactly.
  - `test_no_rated_apps_gives_blank_scores` (Review Focus 3).
  - `test_views_are_replaced_and_others_kept` (Review Focus 5).

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(db): define reports and write them into the file as views`.

### Task 2: `v_games` (`games.py`)

Cell 7's `v_games` columns minus `owned`, `ignored`, `status` and `on_notion`. `price` is the home-country rule above. It reads from `app_review_total` joined to `app`, ordered by `appid`.

- [ ] **Step 1: failing tests**
  - `test_games_has_the_notebooks_columns_less_the_account_ones`: the notebook's list minus those four, in order.
  - `test_games_matches_the_notebook_on_the_same_rows`: on BR-described sample rows, every shared column.
  - `test_a_free_app_has_no_price` (Review Focus 2).
  - `test_a_price_from_another_country_never_shows`: a US-described app with a US price row has a blank `price`.
  - `test_a_new_home_country_replaces_the_views` (Review Focus 4): one app with BR and US price rows. `create_views(home_country="BR")` shows the BR price in `v_games`; calling it again with `"US"` shows the US price.
- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(db): add the games report`.

### Task 3: The store columns and `v_followed` (`store_columns.py`, `followed.py`)

`store_columns.py` holds cell 7's `STORE_COLUMNS`, with each expression ported to Core. Its JSON helpers become functions returning Core expressions:

- `json_rows` becomes `func.json_group_array` over a scalar subquery;
- the credits, demos and related-app columns;
- `free_weekend` with `json_patch`;
- the score labels;
- `epoch` becomes `func.strftime('%s', …)` cast to INTEGER;
- `store_categories`;
- the prices read from the stored `formatted_*` columns instead of `money()`.

`followed.py` ports `catalog_columns` the same way.

- [ ] **Step 1: failing tests**
  - `test_followed_has_the_notebooks_columns_plus_store_categories`: the notebook's 150 columns in order, with `store_categories` inserted where the per-category columns were.
  - `test_followed_matches_the_notebook_on_the_same_rows`:
    - sample: a full BR game with offers, a discount, credits, demos, genres, tags, a free weekend and a DLC;
    - our `formatted_*` columns hold what the notebook's `money()` derives for those cents.
  - `test_store_categories_lists_internal_names`.
  - `test_a_fallback_app_shows_its_store_but_no_price` (Review Focus 1, `v_followed`).
- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(db): add the followed report`.

### Task 4: `v_wishlist` (`wishlist.py`)

Cell 7's `wishlist_columns` with:

- `original_sort_order` (priority with blanks last, then position);
- the store columns from Task 3, via the fallback rule (unfiltered `app`, `store_country` after `visible`, the `unvailable_for_country_restriction` rule);
- `HISTORY_AND_PLAYERS`.

It has no `recommended_sort_order`, no sort keys and no wishlist-category columns (those arrive in milestone 2, as a list column like `store_categories`).

- [ ] **Step 1: failing tests**
  - `test_wishlist_has_the_notebooks_columns_with_the_owners_changes`. The edit list: `recommended_sort_order` removed; `store_country` after `visible`; `store_categories` where the per-category columns were.
  - `test_wishlist_matches_the_notebook_on_the_same_rows`: on BR-described rows, every shared column. `original_sort_order` follows priority, then position.
  - `test_a_fallback_app_shows_its_store_but_no_price` (Review Focus 1, `v_wishlist`).
- [ ] **Steps 2–5:** fail; implement; pass. Then run hooks, the suite and the docs build. Commit `feat(db): add the wishlist report`.

### Task 5: Spec, changelog and the pull request

- **Spec, *Goals* and *Database*:** reports are `select()`s in the application, written into the file as `v_*` views on every open with the home country filled in. Record the owner's 2026-11-16 decisions:
  - store categories as a list;
  - fallback data with no prices, in every report;
  - no `recommended_sort_order`;
  - account columns with their data;
  - never `on_notion`.
- **Spec, *Derived figures*:** "computed in views" becomes "computed in the reports".
- **Spec, *Exports*:** a report exports like a table.
- **CHANGELOG:** "Reports: app scores, games, the wishlist and followed apps, computed by the application and written into the database as views."
- **This plan:** saved as `docs/superpowers/plans/2026-11-16-m1-part7-reports.md`.
- [ ] **Step 1:** hooks, the suite and the docs build pass; the diff is under 150,000 characters.
- [ ] **Step 2:**
  - commit `docs: record the reports' decisions`;
  - push `feat/reports` and open the PR;
  - wait for CI to pass;
  - final reviewer on the most capable model;
  - fix pass, then merge by rebase.

## Verification

- **Per task:** named tests seen failing, then passing.
- **Parity:**
  - the four views' column lists equal the notebook's after the listed edits;
  - on sample rows the home store described, every shared value is equal, scores to 1e-9;
  - the fallback-only rows behave as Review Focus 1 says.
- **Gates:** `uv run pytest` at 100% branch coverage, `uv run prek run --all-files`, the docs build, and CI on Ubuntu, Windows and macOS.

## Execution

Inline (`superpowers:executing-plans`), with a ledger at `.superpowers/sdd/2026-11-16-m1-part7-reports/progress.md`, then one fresh reviewer on the most capable model before the merge.
