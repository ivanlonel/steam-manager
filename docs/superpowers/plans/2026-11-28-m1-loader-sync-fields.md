# Milestone 1: the fields the sync's live runs found — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

The roadmap (`docs/superpowers/plans/README.md`) puts "Loader, before the CLI" ahead of part 10. Now that the sync fetches referenced apps (DLC, soundtracks, season passes), the loader meets fields it doesn't know, plus two checks whose premise is wrong.

A wider live run on 2026-11-28 covered 24 popular apps and their references: 447 full entries and 24 histograms. It is archived at `<scratchpad>/wide-home`. It confirmed the four owed items and added two:

- `unknown`:
  - `extra_details.music_album` 9;
  - `season_pass.milestones[].backfilled_release` 3;
  - `review_histogram.past_events` 8;
  - `hardware_compatibility.steam_deck_blog_url` 1.
- `mismatches`:
  - `basic_info.first_franchise_clan_account_id` 219;
  - `included_offer.package_group` 37.

Until these are handled, every sync that reaches a soundtrack, a season pass or a DLC reports them. The CLI (part 10) would show that noise to every user.

**Goal:** after this change, the wide profile reloads from its archive with `unknown == {}` and every mismatch 0. A broader live sample of other app types comes back clean too, or anything it finds is owed in the README.

**Branch:** `feat/loader-sync-fields`, which already holds `5d5dcac docs: note two lessons from the sync stage`, so the CLAUDE.md note rides along.

## What each field is, and where it goes (builder's calls)

These are read from the wide run's archive.

| Field                                                             | Seen                                                                                                                                                                                                                                                                          | Goes to                                                                                                                                                                                                                                                                                                                                                             | Why                                                                                                                                                                                                                |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `extra_details.music_album`                                       | On 9 soundtracks (type 11 only). It has `artist`, `composer`, `label` and `other_credits` as free text, often multi-line, and `tracks[]` of `disc_number`, `track_number`, `name`, `duration_seconds`, plus `other_name` (a second-language title, on 67 of 413 tracks).      | The `app_text` columns `music_album_artist`, `music_album_composer`, `music_album_label` and `music_album_other_credits`. A new table `app_track(appid → app, position, disc_number, track_number, name, other_name, duration_seconds)`, keyed by `(appid, position)`.                                                                                              | The texts sit with the app's other texts. The position keeps Steam's order and assumes nothing about `(disc, track)` being unique, though it was in all 413.                                                       |
| `season_pass.milestones[].backfilled_release`                     | On 3 milestones, each shipped, always `true`.                                                                                                                                                                                                                                 | A flag `season_pass_milestone.backfilled_release`, appended.                                                                                                                                                                                                                                                                                                        | One flag per milestone.                                                                                                                                                                                            |
| `hardware_compatibility.steam_deck_blog_url`                      | On 1 app (271590). It's Steam's announcement URL, ending `?snr=2___`.                                                                                                                                                                                                         | `app.steam_deck_blog_url`, as sent.                                                                                                                                                                                                                                                                                                                                 | `snr` is Steam's navigation code, not a secret, and `links[].url` is already stored as sent. The secrets rule is about the URLs this app requests.                                                                 |
| `review_histogram.past_events`                                    | Sent at the top of the answer by 8 of the 24 histograms. Each holds 1 or 2 entries of `{type, start_date, end_date}`, with `type` 0 on all.                                                                                                                                   | A new table `review_event(appid → app_review_histogram, position, type, start_date, end_date)`, keyed by `(appid, position)`. The dates are ISO, as `review_history`'s are. It is cleared and rewritten with the histogram.                                                                                                                                         | Its rows belong to the histogram answer, as `review_history`'s do. The docstring says only "a period the store marks on the review graph; `type` was 0 on every one seen (2026-11-28)". Its meaning is unverified. |
| `basic_info.first_franchise_clan_account_id` (the 219 mismatches) | On 271 of 447 entries. 216 send it without `franchises`; DLC send their parent's, and 213 of those 216 match the parent's. Hades sends a franchise credit with no creator page. Where a franchise credit has a creator page, the value equals the first such page (all seen). | `app.first_franchise_creator_id → creator.creator_id`, appended. Use `ForeignKey("creator.creator_id")`, a string as `apps.py` already uses for `app.appid`, because `creators.py` imports `apps.py`. The blank creator parent comes from `Writer._blank_parents` (`loader/write.py`) on its own, since `creator` is in `FILLED_PARENTS`. **The check is dropped.** | It can't be derived, so it is stored. The spec bullet changes from "checked" to "goes to".                                                                                                                         |
| `included_offer.package_group` (the 37 mismatches)                | Subscription packages in DLC 1158100's `included_packages` say `subscriptions`, one of 1158100's own `package_groups`. All 9,464 short-record options seen sit in `default` or one of the including app's page groups.                                                        | Still a check, now "`default`, or one of the including app's `package_groups` names". `included_offer` (`loader/offers.py`) gains a parameter carrying those names. `_included` (`loader/store_item.py`) passes `{"default", *names}` from `item.package_groups`.                                                                                                   | The old premise ("a short record's options belong to no page") was wrong: they carry the including page's group. Storing that would repeat `app_offer.package_group`, which already holds it for 35 of the 37.     |

Not in scope: `blank_parents` counts, such as `app_package_group` 719. That is existing behaviour, and the run reports it.

## Global constraints

- Follow CLAUDE.md:
  - test first, each test seen failing;
  - full typing, and Sphinx docstrings with an attribute docstring for every model field and column;
  - `tests/` mirrors `src/`;
  - Conventional Commits with a body that says why;
  - `GLOSSARY.md` terms (*full entry*, *short record*, *creator page*, *histogram*).
- New model fields follow `steam/models/` style: `X | None = None`, lists `tuple[T, ...] = ()`.
- New columns are appended at the end of their class, so the notebook comparison shows them only as `only declared:` lines. New tables join the "The notebook has no such tables" group in `tests/steam_manager/db/schema/test_base.py`'s `STEAM_TABLES`. Each gets a keys-and-references test, as `test_app_dlc_keys_and_references` (`test_relations.py`) does.
- Recorded fixtures go in `tests/fixtures/steam/…`. They hold store data, not account data. Copy them from the wide archive pretty-printed, as the others are, only when small (about 15 KB or less). Otherwise build the case in the test by editing a recorded one in place, as `test_the_first_franchise_is_checked_against_the_franchises` does with `read()` and `described()`.
- One pull request, never a draft, under 150,000 diff characters (`git diff main...HEAD | wc -c`).

### Task 1: Soundtracks (`music_album`)

**Files:**

- `steam/models/details.py`: `Track` and `MusicAlbum`, and `ExtraDetails.music_album`.

- `db/schema/media.py`: `AppTrack`.

- `db/schema/apps.py`: four `AppText` columns.

- `loader/details.py`:

  - `read_columns(extra.music_album, …, ("artist", "composer", "label", "other_credits"), prefix="music_album_", used=("tracks",))` into `texts`;
  - `positioned(appid, AppTrack, …)` for the tracks;
  - `"music_album"` in the final `findings.rest`.

- The tests that mirror each of these.

- [ ] **Step 1: failing tests.**

  - `test_a_soundtracks_tracks_keep_steams_order` (`loader/test_details.py`): the tracks' rows, `other_name` included, in order, with `findings.unknown == Counter()`. Use a recorded soundtrack: the smallest of the wide run's nine that fits the size rule. Otherwise use a `music_album` built into 620-BR's `extra_details`.
  - `test_a_soundtracks_credits_are_texts`: the four `music_album_*` texts.
  - Model test: `ExtraDetails` accepts `music_album`.
  - Schema: `app_text`'s expected differences gain the four `only declared:` lines; `app_track` is in `STEAM_TABLES`, with its keys and its reference to `app`.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): store soundtracks' tracks and credits`.

### Task 2: A season pass's backfilled releases

- [ ] **Step 1: failing tests.**
  - `test_a_milestones_backfilled_release_is_stored`: 620-BR with a `season_pass` built in, one milestone sending `backfilled_release: true`. Its `season_pass_milestone` row holds `True`, and nothing is unknown.
  - Model and schema: `season_pass_milestone`'s expected differences gain the `only declared:` line.
- [ ] **Steps 2–5:** fail; implement (`Milestone.backfilled_release`, the column, `_season_pass`'s `rows.add` and its rest set); pass; commit `feat(loader): store a season pass milestone's backfilled release`.

### Task 3: The Steam Deck review's announcement

- [ ] **Step 1: failing tests.**
  - `test_the_steam_deck_blog_url_is_stored`: 620-BR's `hardware_compatibility` with `steam_deck_blog_url` added. `columns["steam_deck_blog_url"]` is that URL, as sent, and nothing is unknown.
  - Schema: `app`'s expected differences gain the line.
- [ ] **Steps 2–5:**
  - fail;
  - implement: `HardwareCompatibility.steam_deck_blog_url`, `App.steam_deck_blog_url`, and `_compatibility` returns `read_columns(tests, at, ("steam_deck_blog_url",), findings, used=<the four test lists>)`, merged into `columns` by `extra_details`;
  - pass;
  - commit `feat(loader): store the Steam Deck review's announcement link`.

### Task 4: The first franchise, stored instead of checked

- [ ] **Step 1: failing tests.** In `loader/test_store_item.py`, replace `test_the_first_franchise_is_checked_against_the_franchises` with:
  - `test_the_first_franchise_is_stored`: 546560-JP's app row has `first_franchise_creator_id == 33078398`.
  - `test_a_first_franchise_without_franchises_is_no_mismatch`: 620-BR with `first_franchise_clan_account_id` and no `franchises`. The name is absent from `findings.mismatches`, and the value is stored.
  - Schema: `app`'s expected differences gain the column line and the foreign-key line, in the comparison's own form.
  - `loader/test_write.py`, or wherever blank creators are tested: a first franchise with no creator row gets a blank `creator` parent.
- [ ] **Steps 2–5:** fail; implement in `_basic_info` or `describe`, `store_item.py:453–472`; pass; commit `feat(loader): store an app's first franchise instead of checking it`.

### Task 5: The review histogram's events

**Files:**

- `steam/models/reviews.py`: `PastEvent`, and `ReviewHistogramAnswer.past_events`.

- `db/schema/reviews.py`: `ReviewEvent`, table `review_event`.

- `loader/reviews.py` `histogram()`: the rows, and `"past_events"` in the answer's rest set.

- `loader/__init__.py:823`: `clear([ReviewHistory, ReviewEvent, AppReviewHistogram], appids)`.

- [ ] **Step 1: failing tests.**

  - `test_a_histograms_events_are_stored` (`loader/test_reviews.py`): `review_histogram-620.json` with `past_events` added, or a recorded one from the wide run. Rows come out in order with ISO dates, and nothing is unknown.
  - `test_a_newer_histogram_replaces_its_events` (`loader/test___init__.py`, in its archive style): a later histogram without events leaves no `review_event` rows for the app.
  - Model and schema: `review_event` in `STEAM_TABLES`, with its key and its reference to `app_review_histogram`.

- [ ] **Steps 2–5:** fail; implement; pass; commit `feat(loader): store the periods a review histogram marks`.

### Task 6: A short record's option sits in the including page's group

- [ ] **Step 1: failing tests** (`loader/test_store_item.py`, or `test_offers.py` for `included_offer` directly):
  - `test_a_short_records_option_may_sit_in_a_page_group`: an included package whose best option says `subscriptions`, while the including app has a `package_groups` entry named `subscriptions`. The mismatch is 0.
  - `test_a_short_records_option_in_an_unknown_group_is_a_mismatch`: the same with a group the page lacks. The mismatch is 1.
- [ ] **Steps 2–5:** fail; implement (the `included_offer` parameter, `_included` passing the names, and the comment at `offers.py:263` restated); pass; commit `fix(loader): let a short record's option sit in its page's group`.

### Task 7: Docs, live checks, the PR

- [ ] **Step 1: docs.**
  - **Spec** (`docs/superpowers/specs/2026-11-14-steam-manager-design.md`):
    - under *New fields*, the five fields and where each goes, dated 2026-11-28;
    - the first-franchise bullet becomes "goes to `app.first_franchise_creator_id`", with the reason;
    - the short-record package-group rule, if the spec states it;
    - under *Database* → *Changes from the notebooks' schema*, the new columns and tables.
  - **README:**
    - the "Loader, before the CLI" block goes;
    - the part 9 row reads "Profiles and the sync, then the fields its live runs found", `#20–#21`;
    - anything the broader sample owes is added.
  - **CHANGELOG** (under Added): "Loader: soundtracks' tracks and credits, season-pass backfilled releases, review histogram events, the Steam Deck review's announcement and an app's first franchise."
  - The plan itself goes in as `docs/superpowers/plans/2026-11-28-m1-loader-sync-fields.md`.
- [ ] **Step 2: live checks** (scratchpad scripts, nothing committed).
  - Re-open the wide profile with this release. The schema change recreates the tables, and the archive reloads with no network. Expect `unknown == {}` and every mismatch 0.
  - Then a small live sample of types the wide run lacked: software, a tool, hardware, a video, a mod, a demo, a playtest. Use a throwaway profile, with steps `WISHLIST` and `APPS` after archiving a hand-made wishlist, as the part 9 smoke did.
  - Handle a new field there in this PR, test first, when it fits a pattern above: a scalar becomes a column, a list becomes a positioned table. Owe anything that needs a decision in the README.
- [ ] **Step 3: gates.** `just check`, `just docs`, and the diff size. Commit `docs: record the loader's new fields`.
- [ ] **Step 4: review and merge.**
  1. Push, and open the PR (never a draft).
  1. Wait for green CI. Sourcery's budget is spent until about 2026-11-30, so don't wait for it.
  1. Send one fresh reviewer on the most capable model, with the ledger's `Ruling:` lines.
  1. Make one fix pass, each fix seen failing first.
  1. Merge by rebase.
  1. Report every ruling and deferred minor, then delete the ledger.

## Verification

- **Per task:** each named test is seen failing, then passing; the whole suite passes at 100% branch coverage.
- **End to end:** the wide profile reloads with no unknown field and no mismatch; the broader sample is clean or owed.
- **Gates:** `just check` (every hook, then the tests), `just docs`, and CI on Ubuntu, Windows and macOS.

## Execution

Inline (`superpowers:executing-plans`). The ledger is at `.superpowers/sdd/2026-11-28-m1-loader-sync-fields/progress.md`, kept by hand.
