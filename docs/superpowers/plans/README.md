# Milestone 1: where it stands

Read this first when resuming. The spec (`../specs/2026-11-14-steam-manager-design.md`) is
normative; each stage's plan sits next to this file.

## Stages

| Part | Stage                                                                                          | Pull request |
| ---: | ---------------------------------------------------------------------------------------------- | ------------ |
|    1 | Scaffold, gates and automation                                                                 | #2–#6        |
|    2 | HTTP transport                                                                                 | #7           |
|    3 | Steam endpoints and payload models                                                             | #8           |
|    4 | Raw archive                                                                                    | #9           |
|    5 | Database schema, part 1                                                                        | #10          |
|    6 | Database schema, part 2                                                                        | #12          |
|    7 | Reports (`v_*` views)                                                                          | #13          |
|    8 | Loader (three pull requests: the new fields, store items into rows, then choosing and writing) | #17–#19      |
|    9 | **Sync** (next)                                                                                |              |
|   10 | CLI and exports                                                                                |              |
|   11 | Kaggle import                                                                                  |              |
|   12 | HowLongToBeat (spike first: if the list can't be paged or lacks the appid, stop and ask)       |              |
|   13 | Usage docs                                                                                     |              |

## How a stage runs

1. Plan it with `superpowers:writing-plans`, in plan mode. Questions only the owner can answer
   go to the owner before the plan; the owner approves the plan.
1. Execute it inline with `superpowers:executing-plans` and test-driven development. The
   skill's bash scripts don't run on this Windows machine, so the ledger
   (`.superpowers/sdd/<plan>/progress.md`, git-ignored) is kept by hand, with every deviation
   as a `Ruling:` line.
1. Open one pull request (never a draft), then dispatch one fresh reviewer on the most capable
   model.
1. Regrade the findings by what a user would get. Fix the Critical and Important ones in one
   pass, each seen failing first; ledger the Minor ones as deferred.
1. Merge by rebase on green CI. Report every ruling, with its cost if wrong, and every deferred
   minor to the owner; carry the deferred ones and the items owed to later stages into the
   lists below. Delete the ledger.

## Owed to later stages

Decisions and checks a review or a ruling left to the stage that owns them. The spec already
records the loader's decisions, where every new field went, and Kaggle dating by file time.

**Sync, and whichever stage first reads profile settings**

- On open: `ensure_steam_schema`, then `load`, then `create_views` (later, Alembic for the
  user's tables). A sync loads after each step, through `asyncio.to_thread`: the database has
  one synchronous writer.
- Normalize the home country to two upper-case letters: a lower-case `br` shows no prices.
- A new home country, or a new list of fallback countries, makes the next load rebuild the
  tables by itself; `create_views` follows.
- A load ends with `PRAGMA foreign_key_check`, which scans every table: tens of seconds on a
  full catalog. Batched commits are the upgrade path if that hurts.
- Show the `LoadReport`: fields nothing stores, mismatches and malformed answers are empty on a
  healthy run.
- Transport questions left open: POST and non-idempotent retries, per-request headers, a 200
  with an error body in general, the `Date` header in `Retry-After`.
- Archive: two processes creating a new file at once; no delete API or cross-country key
  listing; bound each `put` batch (a whole catalog is held in memory and one write lock).
- Whoever filters `wishlist()` filters it as a subquery: `ROW_NUMBER` runs after `WHERE`.

**CLI and exports**: `export <table or report>`; a report exports like a table.

**Kaggle import**

- A shared row (an offer's price, a trailer, a creator) takes the last loaded answer's values:
  guard it by fetch time before imported answers, older than fresh ones, load after them.
- Exact review counts come from the source `steam` only: an import adds its own.
- A Kaggle record's `is_listed`: `app.is_listed` now follows the profile's listings, so decide
  whether the record's value is reported, checked or stored.

**HowLongToBeat**: a key in HLTB's URL path (the transport strips only query strings).

**Milestone 2**

- `v_owned`, `v_ignored`; wishlist categories as one list column, like `store_categories`;
  `owned`, `ignored` and the tracking status in `v_games` (never `on_notion`).
- Alembic's baseline with the first table of the user's own data. A stale view blocks SQLite
  renaming the tables it reads, so a release that retires a report drops its view by name.
- `wishlist_item_category` will reference a Steam table that gets recreated; a table moving
  from Steam data to user data; a busy timeout once there are concurrent writers.

## Deferred minors

Polish the reviews found and the owner chose not to fix yet, by the stage that found them.

**Part 1, scaffold**

- No ruleset on `main` requiring the test, hooks and docs checks (a repository setting).
- `just test` re-splits quoted pytest arguments (`-k "a and b"`); needs `[positional-arguments]`
  recipes per OS.
- The justfile needs PowerShell 7 (`pwsh.exe`) on Windows, and CONTRIBUTING doesn't say so.
- `{{ justfile() }}` unquoted in the default recipe breaks on paths with spaces.
- `just clean` leaves `docs/api/generated/`.
- deptry (`always_run`) also runs on post-checkout, merge and rewrite; add
  `default_stages: [pre-commit, manual]`.
- CLAUDE.md says to build the docs "when docs changed"; a `src/` docstring change can fail the
  nitpicky build too.
- Test docstrings are declarative, against CLAUDE.md's "imperative for callables".
- pydoclint's `skip-checking-short-docstrings` defaults to true, so summary-only docstrings on
  functions with parameters pass.
- No `[tool.uv] required-environments` to make a missing wheel fail at lock time.
- Dependabot security updates run beside Renovate; their `uv.lock`-only pull requests fail the
  sync-with-uv hook (a repository setting).
- Release notes put most Renovate pull requests under Tooling, before Dependencies.
- The release workflow doesn't check that the tag's commit is on `main` or that CHANGELOG has
  the version; no release recipe or steps are documented.
- zizmor runs offline in CI (no `GH_TOKEN`), so the impostor-commit and known-vulnerable-actions
  audits are skipped.
- `update-dependencies.yml` has no concurrency group, so overlapping runs race to push.
- Part 1's committed plan still describes what its rulings reversed.
- CLAUDE.md's `git diff main...HEAD | wc -c` doesn't work in PowerShell.

**Part 2, transport**

- The transport relies on `make_client` for "no redirects"; a passed-in client that follows
  redirects bypasses pacing for the target host (fix: `send(request, follow_redirects=False)`).
- `endpoint_of` drops a non-default port and IPv6 brackets (fix: `url.netloc`).
- Commits 6c5b45b and 13ccdb5 misdescribe the notebooks' schedule and where the zone-less date
  branch landed (history only).
- The worst-case stall before a stop (about 2.75 h of timeouts, 4.2 h of `Retry-After` 300) is
  undocumented.
- `TIMEOUT_SECONDS` bounds each connect or read operation, not the attempt.
- Docstrings don't say a `Transport` is bound to one event loop, or that creating one changes
  two process-wide logger levels.
- The request is built once before the lock, so retries don't carry cookies earlier answers
  set.
- `setdefault(host, asyncio.Lock())` builds a throwaway lock on every call.
- `get`'s docstring doesn't warn that the returned `httpx.Response` still carries the full URL.

**Part 3, Steam endpoints**

- No test spells out the full data request; it compares `data_request` with
  `FULL_DATA_REQUEST` itself.
- A `Query` page past the total (the catalog shrinking mid-listing) is rejected for 270 s, then
  the listing fails.
- `models/offers.py` and `media.py` have no test module of their own.
- A vanity lookup that gets an HTML or rate-limit page reports `ProfileNotFoundError` instead
  of retrying.
- The missing-items warning gives a count, not the appids.
- `fetched_at` is taken when the consumer pulls an item, not when the answer arrived.
- A store item without `id`, or a non-dict item, raises `KeyError` or `ValidationError` naming
  no endpoint; the endpoint docstrings list no `:raise:` for transport errors.
- No recorded app is sold in the US but not in BR; 12170 stands for both the delisted and the
  success-15 cases.
- `unknown_fields` paths in a `RootModel` start with `root.`; the recorder keeps
  `GetAppReviews`' cursor; one test checks only the reason text; `Answer.body`'s docstring
  doesn't fit the client-built listing; `app_genres` sends no `cc`; three parameters are typed
  as concrete types; a `noqa: PLR2004` could be a `STEAMID64_DIGITS` constant.

**Part 4, raw archive**

- The Hypothesis property's `st.text()` never draws surrogates, so only the example test covers
  `surrogatepass`.
- The streaming test would pass if `answers()` read everything first; the batch test covers
  only pre-validation, not a row SQLite itself rejects.
- Opening trusts any SQLite file at `user_version` 0, and an older layout would be restamped
  when version 2 arrives.
- `close()` can't release a connection held by a live `answers()` stream kept past the `with`
  block; the archive reopens silently after `close()`.
- The WAL pragma's result isn't checked, and `journal_size_limit` is unset, so a long-lived
  reader lets the WAL grow.
- `datetime.min` or `max` at a non-UTC offset is stored but can't be read back; the error says
  "must be in UTC" though any zone is accepted; a double space in `CorruptAnswerError`'s message
  when the country is `""`.
- `:meth:Archive.answers` lacks backticks in `STREAM_ROWS`' docstring.

**Part 5, schema 1**

- The fingerprint's stability is tested within one process only; a CHECK built from a
  frozenset would vary with `PYTHONHASHSEED` (needs a two-subprocess test).
- `app_compatibility_test`'s key, WITHOUT ROWID and foreign key aren't pinned structurally.
- `test_foreign_keys_are_on_after_recreating` misses both app and tag, so its failure could
  come from either reference.
- `Flag` accepts any int-convertible value (`"1"`, `2`, `1.7`) instead of failing on non-bool.
- `open_database` doesn't check that WAL took effect (network shares keep the old journal
  mode).
- Two processes opening right after an upgrade can both drop and recreate (no `BEGIN IMMEDIATE` around the check and the drop).
- Part 5's plan counts tables off by one.

**Part 6, schema 2**

- `_notebook.py`'s docstrings are stale: `describe`'s summary omits checks and generated
  expressions, and `differences`' example uses the old line format.
- The spec says the store lists come with "every full entry"; a full entry can send them, not
  every one sends every list.

**Part 7, reports**

- `Store.listed` is the app alias `n`, while `Store.report`'s `listed` parameter and the locals
  in `wishlist.py` and `followed.py` are the list alias `w`; rename one.

**Part 8, loader**

- The README listed as owed items PR #17 settled, until this stage's last pull request.
- No test in PR #17 exercised `provides_engine_appid`; PR #18's hand-built entry does.
- `app_featured_creator`'s docstring says "creator home" where the code and spec say "creator
  page".
- Commit "declare and store three fields" stores two of them; the third is checked (a reword
  needed a force-push, which wasn't allowed).
- The media helpers report at fixed paths (`assets`, `screenshots`, `trailers`), ignoring a
  short record's path.
- A DLC without a short record reads as one without content descriptors.
- An empty `{}` part (assets, release, a review summary, `dlc_for_purchase`) isn't treated as
  missing, unlike the notebook's `if x:` guards.
- The table-classification and schema-fit tests don't cover `EVERY_SECTION`'s tables or the
  short records.
- When `best_purchase_option` repeats a listed option, its own fields are never compared.
- "record" alone in a few docstrings and locals of `offers.py` and `store_item.py`.
- `_included` returns `Sequence[StoreItem]`; `extra_details`, `positioned`, `screenshots` and
  `trailers` lack a `:raise:` for `Rows.add`.
- `_creator`'s comment doesn't say a creator's `success` isn't stored.
- A histogram takes the latest of the changed answers only, not of all its sources' answers.
- On a rebuild, a row several apps share takes the answer loaded last (by appid), not the
  newest; an incremental load gets the newest.
- An app a short record filled keeps it when its own failed answer arrives in a later load,
  where a rebuild keeps the short record's data too: loads and rebuilds can disagree.
- The load keeps each written app's whole `ReviewSummary`, and writes every total in one go.
- `LoadReport` counts are approximate: blank parents a batch then describes, rows ON CONFLICT
  ignored.
- An app row made as a blank parent, or for a player count, gets `is_listed` only when a
  listing changes.
- `Archive.stamps(kinds=…)` is unused; `loaded_answer` records stamps the load ignores (other
  sources' review counts, kinds from newer releases), which a later release would only read
  after a rebuild.
- The latest listings are read on every load, so their unknown fields are reported every time.

## The owner's to-dos

- Add the `RENOVATE_TOKEN` secret and check that the Renovate app can access the repository
  (CONTRIBUTING.md lists the maintainer setup).
- Optionally: a ruleset on `main` requiring the checks, and Dependabot security updates off.
