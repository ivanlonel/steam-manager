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

The builder's calls (2026-11-28):

- **Data folder:** `STEAM_MANAGER_HOME` when set. Otherwise `%LOCALAPPDATA%\steam-manager` on
  Windows (local rather than roaming: an archive reaches gigabytes),
  `~/Library/Application Support/steam-manager` on macOS, and elsewhere
  `$XDG_DATA_HOME/steam-manager`, falling back to `~/.local/share/steam-manager`.
- **Profile folder:** `<data folder>/<steamid>/`, holding `settings.json`, `steam.sqlite` and
  `archive.sqlite`.
- **Settings file:** JSON holding the SteamID, the home country, the fallback countries, the
  language and the maximum ages. Only the ages the user changed are written, as ISO 8601
  durations, so a release's new defaults reach existing profiles.
- **Countries** are stripped, upper-cased and refused unless they are two ASCII letters: a
  lower-case `br` would show no prices. The fallbacks drop the home country and repeats,
  keeping the first.
- **Language** is one of Steam's API language codes (the Steamworks language page, 2026-11-28),
  refused otherwise: a typo would silently give English. Malay has a code but no known
  ELanguage number for the store categories, so it isn't offered.
- **Opening a profile** recreates the Steam tables when this release's differ, loads what the
  archive holds that the tables don't (a sync stopped between archiving and loading loses
  nothing), and writes the reports as views.

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
Any table or report can be exported. The web interface adds a button that copies TSV.

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
steam-manager export <table or report> --format csv|tsv|json|jsonl|parquet|xlsx [--output FILE]
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

The builder's calls, where the owner set no value:

- **Pacing:** `Query` 0.5 s between pages, `GetItems` 1 s between batches, and lookups,
  wishlist, followed apps and vanity URLs 1 s. The table's values hold for the rest.
- **Light and full entries:** the light catalog comes from `Query` only, with
  `data_request={"include_reviews": true}`. Full entries come from `GetItems` only, 100 at a
  time, so a full catalog resumes batch by batch.
- **Answer kinds:** the archive keeps each answer under its kind:
  - `store_item` (a full entry) and `store_item_light`;
  - `listing` (the appids a country lists, with Steam's total);
  - `store_categories`, `tags` and `app_genres`;
  - `app_reviews` (one per purchase type), `review_histogram` and `current_players`;
  - `wishlist` and `followed_apps`.
- **Profiles:** a person's SteamID64 is 76561197960265728 plus a 32-bit account id. A vanity
  URL resolves through `steamcommunity.com/id/<name>?xml=1`; a missing one answers 200 with an
  `<error>` element.
- **New fields:** fields the notebooks' loader never had, and where the loader puts them:
  - seen on 2026-11-15:
    - `extra_details.hardware_compatibility` goes to the table `app_compatibility_test`;
    - `extra_details.dlc_for_purchase` goes to the table `app_dlc`. Its total price goes to
      `app.dlc_formatted_total_price`, and its count to `app.dlc_count`, since Steam lists 200
      DLC at most. Each DLC's content descriptors are checked against the answer;
    - `reviews.counts_all_purchases` goes to `app.counts_all_purchases`;
    - the store categories' `show_in_search` goes to `store_category.show_in_search`;
  - seen on 2026-11-28:
    - `related_items.provides_engine_appid` goes to `app_related`, of kind `engine`;
    - `basic_info.featured_creator_home_clan_account_ids` goes to the table
      `app_featured_creator`. It can't be derived: Steam leaves it out of some apps whose
      credits have creator pages;
    - `basic_info.first_franchise_clan_account_id` is checked against the first franchise's
      creator page whenever Steam sends it.

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

The builder's calls:

- **Layout:** one `STRICT`, `WITHOUT ROWID` table, `answer`, keyed by source, kind, key and
  country. The time is in microseconds since the Unix epoch, UTC. The body is UTF-8 JSON
  compressed with zstd. Lone surrogates, from half an emoji escaped in Steam's JSON, are kept.
- **Latest:** an answer replaces another only if it was fetched later, so a Kaggle import dated
  by its file never undoes a fresh fetch. A batch is written in one transaction, whole or not
  at all.
- **WAL mode:** the web interface reads while a sync writes.
- **Version:** `PRAGMA user_version` holds the layout's version. A file from a newer release is
  refused; it can be deleted, and the next sync fetches it again.
- **Damage:** a row that won't decompress is reported with its key, never as a bare zstd
  error.

### Database

- The schema keeps the notebooks' table and column names wherever the concept is unchanged
  (`steam-database.ipynb`, cell 2), so completeness can be checked mechanically against a
  notebook-built file. It is declared with SQLAlchemy Declarative classes using `STRICT`,
  `WITHOUT ROWID`, generated columns and partial indexes.

- Changes from the notebooks' schema: no check restricting countries to BR and US; Steam's
  `formatted_*` price strings are stored instead of derived (the derivation only worked for two
  currencies), as four columns appended to `offer_price` after the notebook's own (builder's
  call); `list_entry` is replaced by tracking status and custom lists in milestone 2.
  Fields Steam added since the notebooks get columns and tables, listed under *New fields*
  (builder's calls):

  - the columns `store_category.show_in_search`, `app.counts_all_purchases`,
    `app.dlc_formatted_total_price`, `app.dlc_count` and `app_review_histogram.count_all_reviews`;
  - the kind `engine` of `app_related`;
  - the tables `app_compatibility_test` (Steam's compatibility review per device, in Steam's
    order), `app_dlc` and `app_featured_creator`.

  Event ids (`event_gid`) are uint64 that Steam sends as text, and stay text: they can exceed
  SQLite's INTEGER. `app.is_listed` is 1 when the latest listing of one of the profile's stores
  holds the app; 0 when none does and the app is a game, mod or software, the types a listing
  covers; blank otherwise, and before any listing.

- The notebook's DDL is a test fixture, and every shared table is compared with it column by
  column: name, order, type, NOT NULL, default, generated or not, primary key, foreign keys,
  unique indexes and their conditions, CHECK and generated expressions, `STRICT` and
  `WITHOUT ROWID`. Flags are INTEGER 1 or 0 and dates ISO 8601 text, as the notebooks store
  them (builder's calls).

- Milestone 1 creates the lookup, app, classification, credit, relation, offer, media,
  requirement and review tables, `wishlist_item`, `followed_app`, the HowLongToBeat tables and
  the reports `v_app_scores`, `v_games`, `v_wishlist` and `v_followed`. It also creates the store
  page's other lists (links, licence agreements, press quotes, sections, sale pages, Steam
  Awards, purchase notes and sign-up options), which every full entry sends (builder's call).
  `wishlist_item` and `followed_app` come from archived answers, so they are Steam tables. Tables
  for data that needs sign-in arrive in milestone 2.

- Steam tables are never migrated: when their schema changes they are dropped and rebuilt from
  the archive. Tables holding the user's own data are migrated with Alembic, whose baseline
  arrives with the first such table in milestone 2 (builder's call: milestone 1 has none).

- A file records each Steam table it holds, with a SHA-256 fingerprint of the DDL that built
  them. Opening it with a release whose fingerprint differs drops the recorded and the declared
  Steam tables, and only those, creates them again and has the caller replay the archive. A
  table holding the user's own data is never dropped (builder's call).

- A rebuild that stops before it finishes (an interrupted sync, a crash) is redone on the next
  load, never left half-done in silence. The loader keeps its progress inside the Steam tables,
  in `loaded_answer`, so it is dropped with them, and a load is one transaction: one that stops
  writes nothing.

- The database runs in WAL mode so it can be read while a sync writes.

- It needs SQLite 3.44 or newer, since the reports order rows inside aggregates. Opening it with
  an older SQLite fails with a message naming both versions (builder's call).

### Reports

The owner's decisions (2026-11-16):

- A **report** is a SQLAlchemy query the application runs with the profile's home country.
  Each one is also written into the database as a `v_*` view of the same name, with the home
  country filled in, so other SQLite tools see it.
- The reports keep the notebooks' view columns, except that the store categories are one list
  column, `store_categories`, instead of one column per store category.
- An app the home store didn't describe shows the describing store's data, named in
  `store_country`, and every price blank, in every report.
- `v_wishlist` has no `recommended_sort_order`: it ranked by the owner's own wishlist
  category, and milestone 6's saved rankings replace it.
- `v_games` gains `owned`, `ignored` and the tracking status with their data in milestone 2,
  and never `on_notion`, which names the owner's personal Notion database.

The builder's calls:

- Each open compares every view with its report and rewrites only those that differ, after an
  upgrade or a change of home country. A current view is only read, so opening the database
  while a sync writes never waits for the sync's lock. Views of other names are left alone.
- Each report is checked against the notebook's own view SQL (cell 7, run with no categories)
  on the same rows: the same columns in order after the owner's changes, and the same values
  where the home store described the app.
- A price shows only for an app the home store described, and only the home country's: the
  price joins on both, as the notebook's `v_games` showed Brazilian prices only. A bundle's
  price at home can belong to an offer that doesn't hold the app there, so an app another store
  described never borrows it.

### Loader

- Input: archived answers. Output: rows. It never touches the network.
- An app is replaced in place: its rows are removed and written again in one transaction, so a
  tag or screenshot Steam removed disappears.
- When several answers describe the same app, the most complete one wins: a full entry from the
  home country, then from a fallback country in list order, then from any other country (an
  imported Kaggle record, for a profile outside Brazil and the US), then a light entry, then the
  short record nested inside another app, each of these two in the same country order. Within
  one rank and country the most recently fetched answer wins, whichever source it came from
  (builder's calls: the country order for light entries and short records makes an app the home
  store describes count as described by it, so the reports show its home price). An answer
  whose `success` isn't 1, such as a store's "not sold here", ranks after every answer that
  succeeded (the owner's decision, 2026-11-28). A short record only fills a gap: an app with no
  row, no name, or a failed answer's row.
- A price is always stored under the country it was quoted in. The reports show the home
  country's prices only, so a price in another currency is never mistaken for a local one: a
  profile outside Brazil that imports the Kaggle catalog gets names, tags, reviews and
  descriptions for every app, and prices only for what it has fetched itself (builder's call,
  following the notebooks' rule for dollar prices).
- Answers are validated with Pydantic at this boundary. A field no model declares is counted
  and reported ("fields Steam sent that nothing stores"); a value the schema leaves out as
  derivable is checked against its derivation and mismatches are reported. Both reports must be
  empty on a healthy run. A malformed answer is reported and skipped, never fatal.
- Foreign keys are off while loading and `PRAGMA foreign_key_check` runs before the commit;
  a reference to an app nothing else describes gets a blank parent row.

The builder's calls (2026-11-28):

- **What changed:** a load compares every archived answer's fetch time with `loaded_answer`,
  the Steam table that records what the tables reflect, and loads again only what changed: an
  app whose own answers changed, and the figures, lists and lookups whose answers changed. One
  transaction holds the whole load, and `rebuild` empties the Steam tables first in it. A load
  that finds other countries than the tables were ranked for (`loaded_country`) rebuilds them.
- **Shared rows:** an app's own rows are replaced. An offer takes the newer value Steam sent for
  each column, but for `success`, `unavailable_for_country_restriction` and the best offer,
  which depend on the country, a fallback country only fills what the home country left blank.
  A lookup value that contradicts the one already known is reported.
- **Review totals:** every app with a review summary gets them (the owner's decision,
  2026-11-28), exact when Steam's counts are archived: the app's purchase type when within 2%
  of the store's count, else the closer total.
- **The rest:** lookups come from the latest list of each kind, whatever its language; language
  names are Steam's fixed list; `is_listed` follows the latest listing of each of the profile's
  countries; the wishlist and the followed apps are replaced whole.
- **Malformed answers:** an answer lacking a value its rows need is skipped and reported, named
  without a word of what it holds; any other error is a loader bug and stops the load.

### Derived figures

- Up to 100 reviews, the positive count is `ceil(percent * count / 100)`, exact because Steam
  truncates the percentage. Above 100 it is a midpoint estimate until the exact count is
  fetched, and a flag says which.
- The Bayes average and the Wilson lower bound (99% confidence) are computed in the reports from
  the totals, with the prior taken from every rated app in the database.

### Sync

- Each kind of answer has a maximum age (a setting). A sync fetches what is older, `--force`
  fetches regardless, and an interrupted sync continues from what the archive already holds.
- The network side is asyncio. The database has a single synchronous writer called through
  `asyncio.to_thread`.
- The owner decided on 2026-11-28 that the apps the account apps point at get a full entry
  too, one level deep: their related apps of every kind but `included_app` (parent game,
  demos, playtests, season pass, free-to-play version, engine) and the DLC their store page
  lists. An included app already comes with a short record, and bundles are out.

The builder's calls (2026-11-28):

- **Steps** run in this order, whatever order they are given in, with a load after each:
  `lookups`, `wishlist`, `followed`, `catalog`, `apps`, `reviews`. The loader checks store
  categories while it reads apps, the apps step reads the account lists from the database, and
  the reviews step reads review summaries from it. A load runs only when the step archived
  something.
- **Country passes:** full entries are asked a country at a time. The home country is asked
  for every stale app; fallback country *n* for the stale apps no earlier country sells. An
  earlier country's answer in the same run decides; for an app no earlier pass asked, the
  loaded row does: an `app` row with `success` 1 and a `store_country` among the earlier
  countries means sold. The run's own answers come first because a row can say sold while
  that country's full entry says it isn't: the loader ranks an older light entry, or a short
  record nested in another app, above an answer that failed. A load follows each pass.
- **Catalog:** each country whose `listing` is stale is listed again. A fallback's light entries
  are archived only for apps no earlier country's latest listing holds; the listing itself is
  archived whole, so `is_listed` is right for every country.
- **Apps:** full entries for the account apps, then for the apps they point at; then current
  players for the account apps, and one `appdetails` request per genre without a name,
  skipping genres an app asked before also has.
- **Reviews:** exact totals for the account apps above 100 reviews, or for every such app on
  request, the most reviewed first. Their staleness is read from the key of the purchase type
  the app's count matches: 1 if it is free, else 0. Then histograms for the account apps.
- **Maximum ages**, by default: store categories and tags 7 days; the wishlist and the
  followed apps 1 hour (one request each, so a sync run again within the hour, after an
  interruption, skips them); listings 7 days; full entries 1 day; current players 1 day; exact
  review totals 7 days; histograms 7 days (1 s per app). Light entries go stale with their
  listing, and genre names are asked only for a genre without one.
- **Failures:** a request that fails after its retries skips its unit (one batch of 100, one
  app, one listing, one lookup), is reported by its endpoint alone, and the step goes on. A
  listing that strays from Steam's total is reported and its `listing` answer isn't archived.
  A run of failures stops the sync: what was archived is loaded, the report says why it
  stopped, and no exception escapes. A loader error is a bug and propagates.
- **Archive writes:** answers asked one app at a time are archived 100 at a time, a batch's
  answers together and light entries a page (1,000) at a time, so a stop loses little and no
  answer costs a transaction of its own. A stop still archives what is waiting.
- **Full catalog:** `catalog fetch --full` runs the country passes over every app with
  `is_listed` 1, and resumes through staleness.

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
