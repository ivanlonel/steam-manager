# steam-manager design

Date: 2026-11-14. Status: approved by the owner. Terms in **bold** are defined in
[`GLOSSARY.md`](../../../GLOSSARY.md); the decisions with lasting consequences are in
[`docs/adr/`](../../adr/).

## Intent

The owner collects Steam store and account data with six Kaggle notebooks that end in one
normalized SQLite file. They work, but every run needs manual steps (copying a token, starting
notebooks in order), the code is copied between notebooks, and everything is tied to one
account, one pair of countries and one spreadsheet.

steam-manager is a public application any Steam user can run on their own computer. It gathers
at least what those notebooks gather, keeps it in a database at least as complete as theirs, and
grows from reading the account into managing it. The notebooks and the owner's spreadsheet keep
running untouched; they only define the minimum data set.

Why it is wanted: fewer manual steps; tested, typed code instead of notebooks; acting on the
account and not just reading it; analysis the notebooks don't do.

## Goals

- One installation serves any Steam user. Nothing about the owner is built in.
- A command-line interface first, and a local web interface on top of the same core.
- A per-**profile** SQLite database holding the **catalog** and the account's data, with foreign
  keys and views, at least as complete as the notebooks' `steam.sqlite`.
- A **sync** that can be left unattended, resumed after an interruption, and that fetches only
  what is stale.
- The user's own organisation of their games: a **tracking status** and **custom lists**.
- Exports good enough to paste into a spreadsheet by hand.

## Non-goals

- No communication with Google Sheets, and no Steam Spy.
- No hosted, multi-user service, and no several accounts in one database.
- No history that depends on when the application ran, except **change events** (ADR 0004).
- No PyPI release for now: releases are GitHub Releases with the wheel attached.
- No Node toolchain for the web interface.
- The owner's two personal filter views (`v_add_to_most_wanted`, `v_add_to_backlog`) are not
  ported as fixed views; saved filters in milestone 6 replace them.

## Anti-goals

Any of these makes the project a failure even if everything else works:

- A token, key or cookie appearing in a log, an error message, an export or the repository.
- Private account data (above all the list of apps marked private) leaving the profile folder
  without the user asking for it.
- Hammering Steam or HowLongToBeat: every request is paced, and a run of failures stops the
  **sync** instead of retrying forever.
- Silently dropping a field a **source** sent. Unknown fields are reported.
- An upgrade that loses the user's **tracking status** or **custom lists**.

## Constraints

- Python 3.15 or newer. Lines up to 99 characters. Complete static typing everywhere, tests and
  helper scripts included. Sphinx-style docstrings without `:type:` or `:rtype:`.
- Pydantic 2.13+ for data structures. SQLAlchemy 2.1+ for every interaction with SQLite.
- pytest 9.2+, pytest-cov 7.1+ and hypothesis 6.170+. Code is written test-first. CI fails
  under 90% branch coverage and tests Python 3.15 on Ubuntu, Windows and macOS.
- Strict QA tooling modelled on the owner's `stratified-packager` and `postgis-with-extensions`
  repositories, listed under *Tooling* below.
- A `justfile` offers the common recipes, but the application never depends on `just`.
- MIT license. Public repository `ivanlonel/steam-manager`.
- Work lands through pull requests: never drafts, each self-contained with CI able to pass,
  under 150,000 diff characters where that is possible without an arbitrary cut (so the Sourcery
  reviewer can assess it), checked locally first, merged by rebase.

## Approaches considered

How data flows from **sources** to the database:

- **A. The raw archive is the seam (chosen).** A source only stores raw answers in the **raw
  archive**; one loader turns archived answers into rows. A sync, a **rebuild** and a Kaggle
  import share that loader and cannot drift apart, and the loader is tested with no network.
- **B. Load directly, archive on the side.** Fewer steps per sync, but the Kaggle import and the
  rebuild become separate loaders.
- **C. Map answers onto ORM objects and merge them.** Least code; far too slow for a
  200,000-app catalog across more than sixty tables.

The owner chose A because a full catalog takes hours to download and the notebooks found loader
bugs only after the fact (ADR 0002).

Other choices the owner made between alternatives: an own typed Steam client rather than a
third-party library (ADR 0001); SQLite, one database per profile, rather than DuckDB,
PostgreSQL or a shared multi-account database (ADR 0003); a live database refreshed in place
plus the archive, rather than rebuilding everything on each run.

## What the owner decided

### Profiles and settings

- One **profile** per Steam account, identified by its SteamID. A profile owns a database
  (`steam.sqlite`), a **raw archive** (`archive.sqlite`) and a settings file.
- Profiles live under the platform's user-data folder, overridable with `STEAM_MANAGER_HOME`.
  Nothing private is ever written inside the repository.
- A profile has a **home country**, an ordered list of **fallback countries** (default `US`)
  and one language (default English). A fallback country is asked only for apps the home
  country doesn't sell.

### Sources

- **Steam store and community, over HTTPS.** The endpoints and their quirks are listed under
  *Steam endpoints* below.
- **HowLongToBeat.** Opt-in per profile. The application pages through HLTB's whole game list
  and joins it to Steam by the appid HLTB stores, with name matching only as a flagged fallback.
  HLTB has no official API; the client is our own. A spike comes first: if the list cannot be
  paged or doesn't carry the appid, work stops and the owner is asked.
- **Kaggle files.** `catalog import <folder>` reads a local folder holding the output of the
  owner's public `steam-games` notebook: `steam_games_raw.jsonl.gz` (one record per app with
  `store_item`, `is_listed`, `store_country`), `steam_games.csv` (exact review totals) and
  `steam_lookups.json`. The records carry no fetch time, so an imported answer is dated by the
  modification time of the file it came from (builder's call, not the owner's).
- **Steam client protocol** (milestone 5), implemented in-house.
- Steam Spy is never contacted. Delisted appids are known from: appids already seen (never
  forgotten), the account's lists, an imported Kaggle catalog, and later the PICS change feed.

### Catalog depth

- By default the **catalog** is light: every app the home and fallback stores list gets a
  **light entry**, and the **account apps** plus the apps they reference get a **full entry**.
- The full catalog is an explicit, resumable command, or a Kaggle import.
- Exact positive and negative review counts are fetched for apps above 100 reviews (below that
  they follow exactly from Steam's truncated percentage): for account apps by default, for the
  whole catalog on request, largest first.

### The account (milestone 2)

- Sign-in by QR code, by pasted web token, by username + password + Steam Guard, or not at all
  (a SteamID or profile URL gives public data only).
- The refresh token is kept in the operating system's credential store and nowhere else.
- A **tracking status** is one-or-none per app, from a customizable set whose defaults are
  backlog, playing, played, dropped and on-hold. It keeps the date the user last changed it.
- A **custom list** is a named set of apps; an app can be in many.

### Exports

CSV, JSON, TSV and JSON Lines in the core; Parquet and Excel behind optional install extras.
Any table or view can be exported. The web interface adds a button that copies TSV.

### Later milestones

Each starts with its own interview with the owner before any of its code.

1. Foundation (this document's detailed part).
1. Sign-in and account data; tracking status and custom lists. The database reaches the
   notebooks' completeness here.
1. Web interface: FastAPI, Jinja2 pages and HTMX; one vendored table library with server-side
   paging and one chart library.
1. Steam writes: reorder the wishlist, add and remove wishlist items, edit **wishlist
   categories**, follow and ignore. Each previews and changes nothing until confirmed.
1. Client protocol: licenses, PICS app and package info, PICS change feed, **library
   collections** (read-only).
1. Extras: change feed, bundle advisor, saved filters and rankings, local Steam client data,
   Notion sync, MCP server, scheduled sync and notifications, family-sharing library, IGDB sync.

## Milestone 1 in detail

Milestone 1 uses no credentials at all. A profile is created from a SteamID or profile URL and
holds public data.

### Commands

```text
steam-manager profile add <steamid | profile url> --country BR [--fallback US] [--language english]
steam-manager profile list | show | remove
steam-manager sync [lookups | wishlist | followed | catalog | apps | reviews | hltb] [--force]
steam-manager catalog fetch --full          # every listed app as a full entry; resumable
steam-manager catalog import <folder>       # Kaggle steam-games files
steam-manager rebuild                       # replay the archive through the loader
steam-manager status                        # what is archived, how old, what is stale
steam-manager export <table or view> --format csv|tsv|json|jsonl|parquet|xlsx [--output FILE]
steam-manager db path | check               # where the database is; integrity and foreign keys
```

A profile is chosen with `--profile` or `STEAM_MANAGER_PROFILE`; with a single profile it is
implied. `python -m steam_manager` is the same program.

### Steam endpoints

All on `api.steampowered.com` unless a host is given. None needs a credential.

| Purpose             | Endpoint                                                             | Notes                                                                                                                                                                                           |
| ------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| List apps           | `IStoreQueryService/Query`                                           | `sort: 2` (ascending appid; the default sort repeats and skips). 1,000 per page at most. Type filters: games, mods, software. A listing may differ from its reported total by 0.1% at most.     |
| Store data by appid | `IStoreBrowseService/GetItems`                                       | Batches of 100 (300 fails). Use `id`, never `appid` (0 on delisted apps). `success: 15` mostly means "not sold in this country". A 200 answer without `store_items` is a failure: retry.        |
| Lookups             | `IStoreBrowseService/GetStoreCategories`, `IStoreService/GetTagList` | Names of store categories and tags.                                                                                                                                                             |
| Genre names         | `store.steampowered.com/api/appdetails?filters=genres`               | No endpoint lists genres, so one app is asked per unseen genre. 1.5 s apart.                                                                                                                    |
| Exact review counts | `IUserReviewsService/GetAppReviews`                                  | `languages: ["all"]`, `num_per_page: 1`. `purchase_type` 0 (Steam purchases) for paid apps, 1 (all) for free ones; if the total is more than 2% off `review_count`, try the other. 0.2 s apart. |
| Review histogram    | `store.steampowered.com/appreviewhistogram/<appid>`                  | Account apps only. 1 s apart. Its totals are a different figure from `review_count`.                                                                                                            |
| Current players     | `ISteamUserStats/GetNumberOfCurrentPlayers`                          | Account apps only. A 404 means no figure. 0.2 s apart.                                                                                                                                          |
| Wishlist            | `IWishlistService/GetWishlist`                                       | By SteamID. Priority 0 means unranked.                                                                                                                                                          |
| Followed apps       | `IStoreService/GetGamesFollowed`                                     | By SteamID.                                                                                                                                                                                     |
| Vanity URL          | `steamcommunity.com/id/<name>?xml=1`                                 | Resolves a profile URL to a SteamID without a key.                                                                                                                                              |

The full `data_request` for store data sets every `include_*` flag the notebooks set
(`include_all_purchase_options`, `include_assets`, `include_assets_without_overrides`,
`include_basic_info`, `include_extra_details`, `include_full_description`,
`include_included_items`, `include_links`, `include_optin_registration_tags`,
`include_platforms`, `include_ratings`, `include_release`, `include_reviews`,
`include_screenshots`, `include_supported_languages`, `include_trailers`) and
`include_tag_count: 100`.

### Transport

- One httpx `AsyncClient` wrapper. Per-host pacing with the intervals above; retries on 429 and
  5xx that honour `Retry-After`; ten failures in a row stop the step that was running.
- No error message or log line ever contains a query string, token, key or cookie. Tests
  enforce this with arbitrary secrets.

The builder's calls, where the owner set no value:

- Pacing keeps one request in flight per host, and each request waits its own interval after
  the previous answer from that host arrived, as the notebooks paused after each call. Every
  request states its interval; there is no default.
- Up to five retries, as many as the notebooks allowed (`Retry(total=5)`): on 429, 5xx,
  timeouts, refused and dropped connections. The wait is `Retry-After` when the server sends
  one, else 10 s doubling up to 120 s. A `Retry-After` over five minutes stops the step at
  once: nothing more goes to that host, and the sync doesn't stall.
- Redirects are never followed: a retired Steam endpoint redirects to the store front, and that
  page is not an answer.
- Failures in a row are counted per host, so an outage of one source doesn't stop another; a
  success resets the count.
- httpx and httpcore log below `WARNING` never reaches the log: they record full URLs and
  response headers. The transport logs its own lines, naming the endpoint only.

### Raw archive

- A separate SQLite file per profile, so the database stays lean and the archive can be deleted.
- One row per (source, kind, key, country) holding the latest answer, compressed with the
  standard library's `compression.zstd`, and the time it was fetched.
- A batched answer is archived per item (one row per app), so the loader always works on one
  app at a time.

### Database

- The schema keeps the notebooks' table and column names wherever the concept is unchanged
  (`steam-database.ipynb`, cell 2), so completeness can be checked mechanically against a
  notebook-built file. It is declared with SQLAlchemy Declarative classes using `STRICT`,
  `WITHOUT ROWID`, generated columns and partial indexes; views use SQLAlchemy 2.1's
  `CreateView`.
- Changes from the notebooks' schema: no check restricting countries to BR and US; Steam's
  `formatted_*` price strings are stored instead of derived (the derivation only worked for two
  currencies); `list_entry` is replaced by tracking status and custom lists in milestone 2.
- Milestone 1 creates the lookup, app, classification, credit, relation, offer, media,
  requirement and review tables, `wishlist_item`, `followed_app`, the HowLongToBeat tables and
  the views `v_app_scores`, `v_games`, `v_wishlist` and `v_followed`. Tables for data that needs
  sign-in arrive in milestone 2.
- Steam tables are never migrated: when their schema changes they are dropped and rebuilt from
  the archive. Tables holding the user's own data are migrated with Alembic.
- The database runs in WAL mode so it can be read while a sync writes.

### Loader

- Input: archived answers. Output: rows. It never touches the network.
- An app is replaced in place: its rows are removed and written again in one transaction, so a
  tag or screenshot Steam removed disappears.
- When several answers describe the same app, the most complete one wins: a full entry from the
  home country, then from a fallback country in list order, then from any other country (an
  imported Kaggle record, for a profile outside Brazil and the US), then a light entry, then the
  short record nested inside another app. Within one rank the most recently fetched answer wins,
  whichever source it came from (builder's call).
- A price is always stored under the country it was quoted in. `v_games.price` shows the home
  country's price only, so a price in another currency is never mistaken for a local one: a
  profile outside Brazil that imports the Kaggle catalog gets names, tags, reviews and
  descriptions for every app, and prices only for what it has fetched itself (builder's call,
  following the notebooks' rule for dollar prices).
- Answers are validated with Pydantic at this boundary. A field no model declares is counted
  and reported ("fields Steam sent that nothing stores"); a value the schema leaves out as
  derivable is checked against its derivation and mismatches are reported. Both reports must be
  empty on a healthy run. A malformed answer is reported and skipped, never fatal.
- Foreign keys are off while loading and `PRAGMA foreign_key_check` runs before the commit;
  a reference to an app nothing else describes gets a blank parent row.

### Derived figures

- Up to 100 reviews, the positive count is `ceil(percent * count / 100)`, exact because Steam
  truncates the percentage. Above 100 it is a midpoint estimate until the exact count is
  fetched, and a flag says which.
- The Bayes average and the Wilson lower bound (99% confidence) are computed in views from the
  totals, with the prior taken from every rated app in the database.

### Sync

- Each kind of answer has a maximum age (a setting). A sync fetches what is older, `--force`
  fetches regardless, and an interrupted sync continues from what the archive already holds.
- The network side is asyncio. The database has a single synchronous writer called through
  `asyncio.to_thread`.

## Tooling

- `pyproject.toml`: `uv_build` backend, `src/` layout, static version. Dependency groups `dev`,
  `test`, `type`, `doc`, `hook`. ruff with `ALL` selected (ignoring COM812, CPY001, D203, D212),
  pylint with the rules that ruff or the type checkers already govern disabled, mypy strict with
  the extra error codes of `stratified-packager`, ty, deptry, pytest strict, branch coverage.
- flake8 with cognitive-complexity, rst-docstrings and pydoclint (Sphinx style, no types).
- prek hooks: meta checks, file hygiene, check-ast, debug-statements, name-tests-test,
  editorconfig-checker, typos, gitleaks, pygrep hooks, uv-lock, uv-sync, sync-with-uv,
  pyproject-fmt, taplo, ruff, flake8, pylint, ty, mypy, deptry, `just --fmt --check`, mdformat,
  renovate-config-validator, actionlint, zizmor.
- Workflows: linting, testing, documentation (Sphinx with warnings as errors, GitHub Pages),
  post-Renovate hooks, pull-request labeler, release (a tag builds the wheel and creates a
  GitHub Release). Renovate keeps dependencies and hook pins current.
- Documentation: Sphinx with MyST, autodoc and sphinx-autodoc-typehints.
- Python 3.15-only syntax is used only where every tool in the gate can parse it.

## Reference material

The notebooks are not part of this repository. They live in the owner's `steam-collection`
repository, checked out next to this one (`../steam-collection`). The plans for the schema and
loader pull requests copy what they need from these files, which are authoritative for the
names they define:

- `steam-database/steam-database.ipynb`: cell 2 is the schema (every table and column name);
  cells 3 to 6 are the loader, including which values are left out as derivable and how each is
  derived; cell 7 is the views and the score formulas in SQL; cells 8 and 9 are the checks.
- `steam-database/compare_db.py`: the field-by-field comparison the acceptance check is based
  on.
- `steam-games/steam-games.ipynb`: request shapes, paging, the positive-count estimate, the
  Bayes prior and the Wilson bound.
- `steam-wishlist`, `steam-owned-games`, `steam-account-data`: the per-account requests.
- `CLAUDE.md`: findings about the Steam API, each of which becomes a test.

## Left to the builder

- Module boundaries inside each package, names of private helpers, index choices.
- Default maximum ages per kind of answer, and the exact pacing where the table above gives
  none.
- Which recorded Steam answers become test fixtures (they must be sanitized of account data).
- The columns of the HowLongToBeat tables, which follow from what the spike finds.
- The table and chart libraries of the web interface (milestone 3).
