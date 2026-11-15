# Milestone 1, part 4: the raw archive — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the latest **answer** of every source per (source, kind, key, country) in a per-profile `archive.sqlite`. Answers are compressed and read back exactly, so the loader, a rebuild and the sync's staleness checks all work from it.

**Architecture:** one module, `src/steam_manager/archive.py`. Its `Archive` class owns a SQLAlchemy 2.1 engine on one SQLite file. The file holds one `STRICT`, `WITHOUT ROWID` table, `answer`, in WAL mode.

- **Writes:** `put` writes a batch in one transaction, as an upsert that keeps the newer answer.
- **Reads:** `get`, `answers` (streamed, in key order) and `fetched_at` (staleness).
- **Threads:** everything is synchronous. The sync stage calls it through `asyncio.to_thread`, as the spec says.

**Tech Stack:** Python 3.15, SQLAlchemy 2.1.8 (cp315 wheels exist for every CI system), stdlib `compression.zstd`, pytest, hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md`: *Raw archive*, *Sync*, *Profiles and settings*, and the Kaggle import note under *Sources*. ADR 0002 makes the archive the seam.

**Where this fits:** stage 4 of milestone 1. It consumes `steam_manager.answers.Answer` and `Kind` from stage 3. Next come schema part 1, schema part 2 with views, the loader (it reads `answers`) and the sync (it calls `put`, and `fetched_at` for staleness).

## Global Constraints

- Python `>=3.15`; lines up to 99; complete typing; Sphinx docstrings without `:type:`/`:rtype:`, attributes documented.
- Test first, and watch every test fail before its code exists.
- Tests mirror `src/`: `src/steam_manager/archive.py` → `tests/steam_manager/test_archive.py`.
- SQLAlchemy 2.1+ for every interaction with SQLite (spec *Constraints*); `sqlalchemy` joins `dependencies` in Task 1.
- Paths are `pathlib.Path`; no global mutable state (the engine belongs to an `Archive` object).
- Private data stays private: tests write only under pytest's temporary directories.
- One pull request, never a draft, `just check` and `just docs` first, merged by rebase. Before 2026-11-18 there is no Sourcery review, and the 150,000-character limit is waived.

## Decisions this plan makes (builder's calls)

| Topic       | Decision                                                                                                                                                       | Why                                                                                                                                                                                  |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Table       | `answer(source TEXT, kind TEXT, key TEXT, country TEXT, fetched_at INTEGER, body BLOB)`, primary key `(source, kind, key, country)`, `STRICT`, `WITHOUT ROWID` | The spec's key. `STRICT` allows only INTEGER, TEXT, BLOB, REAL and ANY, so the columns use SQLAlchemy's `Text`, `Integer` and `LargeBinary`, never `String` (VARCHAR) or `DateTime`. |
| Time        | `fetched_at` as microseconds since the Unix epoch, UTC; a naive `datetime` is refused with `ValueError`                                                        | Exact, sortable, and comparable for staleness without parsing.                                                                                                                       |
| Body        | `compression.zstd.compress(body.encode("utf-8", "surrogatepass"))` at the default level; read back with `"surrogatepass"` too                                  | Steam's JSON can escape half an emoji (`"\ud83d"`). `json.loads` turns that into a lone surrogate, which plain UTF-8 can't encode.                                                   |
| Latest wins | `INSERT … ON CONFLICT DO UPDATE … WHERE excluded.fetched_at > answer.fetched_at`                                                                               | "Latest" means fetched last, not written last. A Kaggle import, dated by its file's time, never replaces a newer fetch. A tie keeps the first.                                       |
| Batches     | `put` writes its whole iterable in one transaction                                                                                                             | An interrupted sync leaves whole batches or none.                                                                                                                                    |
| Concurrency | WAL, set on every connection; the engine's `QueuePool` is shared across threads (checked: SQLAlchemy 2.1.8 does this for SQLite files)                         | The web interface reads while a sync writes; the sync writes from `asyncio.to_thread`.                                                                                               |
| Version     | `PRAGMA user_version = 1` on creation; opening a file with a higher version raises `ArchiveVersionError`                                                       | An archive written by a newer release is never read by an older one. It is safe to delete: the next sync fetches it again.                                                           |
| Corruption  | A row whose body won't decompress raises `CorruptAnswerError` naming its source, kind, key and country                                                         | Never a bare zstd error; the loader reports it and skips the answer.                                                                                                                 |

## Review Focus

1. A Kaggle import arrives after a fresh fetch of the same app. The older answer must not replace the newer one, whatever the write order. Test in Task 2.
1. A sync stops in the middle of a batch: an invalid answer, Ctrl-C, a crash. Either all of a `put` is written or none of it. Test in Task 2.
1. The web interface reads while a sync writes, from another `Archive` on the same file. The reader sees each committed batch and never waits for the writer. Test in Task 2.
1. A truncated or corrupt row: `CorruptAnswerError` naming its key, never a bare zstd error. Test in Task 3.
1. A body holding a lone surrogate, CJK text or emoji comes back character for character. Test in Task 1, plus a hypothesis property in Task 3.

______________________________________________________________________

### Task 1: The archive file, writing and reading one answer

**Files:**

- Modify `pyproject.toml` (`dependencies` gains `"sqlalchemy~=2.1.8"`), `uv.lock`, and `docs/conf.py` (intersphinx `"sqlalchemy": ("https://docs.sqlalchemy.org/en/21/", None)`; its `objects.inv` exists).
- Create `src/steam_manager/archive.py`; test `tests/steam_manager/test_archive.py`.

**Interfaces (produces):**

- `ARCHIVE_VERSION: Final = 1`.

- `class ArchiveVersionError(RuntimeError)` with `found: int` and `supported: int`.

- `class Archive`, a context manager:

  - `__init__(self, path: Path) -> None`. It creates the file and table when missing; the parent folder must exist (the profile stage creates it). It turns on WAL on every connection and checks `user_version`.
  - `put(self, answers: Iterable[Answer]) -> None`.
  - `get(self, source: str, kind: Kind, key: str, country: str = "") -> Answer | None`.
  - `close(self) -> None`, which disposes of the engine.
  - `__enter__` returns the archive, and `__exit__` closes it.

- Private helpers: `_micros(moment: datetime) -> int`, which raises `ValueError` on a naive datetime, and `_moment(micros: int) -> datetime`.

- [ ] **Step 1: failing tests** (with `tmp_path`, and `Answer` instances built by a test helper `answer(key="620", *, country="BR", body='{"id":620}', at=AT)` with `AT = datetime(2026, 11, 15, 12, 0, 0, 123456, UTC)`):

```python
def test_an_answer_comes_back_as_it_was_put() -> None:
    archive.put([answer()])
    assert archive.get("steam", Kind.STORE_ITEM, "620", "BR") == answer()

def test_a_missing_answer_is_none() -> None:
    assert archive.get("steam", Kind.STORE_ITEM, "620", "BR") is None

def test_the_body_is_stored_compressed() -> None:
    # put a 50 kB body; read the raw blob with sqlite3
    assert blob[:4] == bytes.fromhex("28b52ffd")  # zstd's magic number
    assert len(blob) < 5_000

def test_text_outside_ascii_comes_back_exactly() -> None:  # Review Focus 5
    body = '{"name": "ポータル2 🎮 \ud83d"}'  # CJK, an emoji, and a lone surrogate
    archive.put([answer(body=body)])
    assert archive.get(...).body == body

def test_the_table_is_strict_without_rowid() -> None:
    assert "STRICT" in sql and "WITHOUT ROWID" in sql   # from sqlite_master

def test_the_archive_runs_in_wal_mode() -> None:
    assert sqlite3.connect(path).execute("PRAGMA journal_mode").fetchone()[0] == "wal"

def test_a_new_archive_has_this_version() -> None:
    assert ... "PRAGMA user_version" ... == ARCHIVE_VERSION

def test_a_newer_archive_is_refused() -> None:
    # create, close, set user_version = 2 with sqlite3, reopen
    with pytest.raises(ArchiveVersionError) as caught: Archive(path)
    assert (caught.value.found, caught.value.supported) == (2, 1)

def test_a_naive_time_is_refused() -> None:
    with pytest.raises(ValueError, match="UTC"): archive.put([answer(at=datetime(2026, 11, 15))])
```

- [ ] **Step 2:** run; expect `ModuleNotFoundError: No module named 'steam_manager.archive'`.
- [ ] **Step 3:** `uv add "sqlalchemy~=2.1.8"`; implement it with a `DeclarativeBase` subclass and an `ArchivedAnswer` model: `__tablename__ = "answer"`, `__table_args__ = {"sqlite_strict": True, "sqlite_with_rowid": False}`. Turn on WAL in an `event.listens_for(engine, "connect")` hook.
- [ ] **Step 4:** whole suite passes. **Step 5:** commit `feat(archive): keep answers compressed in a per-profile SQLite file`.

### Task 2: The latest answer wins, a batch at a time

**Files:** modify `src/steam_manager/archive.py`; test `tests/steam_manager/test_archive.py`.

**Interfaces:** Consumes Task 1. Produces no new names. `put` now upserts with the `WHERE excluded.fetched_at > answer.fetched_at` rule, in one transaction (`engine.begin()`).

- [ ] **Step 1: failing tests**

```python
def test_a_newer_answer_replaces_the_older() -> None
def test_an_older_answer_never_replaces_a_newer() -> None      # Review Focus 1: put new, then old
def test_the_country_and_the_kind_keep_answers_apart() -> None  # same key: BR vs US, store_item vs store_item_light
def test_a_bad_answer_writes_nothing_of_its_batch() -> None     # Review Focus 2: [good, naive time, good]
def test_another_archive_on_the_file_sees_each_batch() -> None  # Review Focus 3: two Archive objects
def test_the_archive_works_from_worker_threads() -> None        # put and get through asyncio.to_thread
```

- [ ] **Step 2:** run; expect the "older" test to fail (a plain insert raises `IntegrityError`, or an upsert without the `WHERE` replaces the row). Record which in the ledger.
- [ ] **Step 3:** implement with `sqlalchemy.dialects.sqlite.insert(...).on_conflict_do_update(index_elements=[...4 key columns], set_={"fetched_at": excluded.fetched_at, "body": excluded.body}, where=excluded.fetched_at > ArchivedAnswer.fetched_at)`. All of a batch's rows go in one `execute` inside `engine.begin()`. Each row's time is converted to microseconds before anything is written, so a bad answer fails the whole batch before it touches the file.
- [ ] **Step 4:** pass. **Step 5:** commit `feat(archive): keep the latest answer, writing batches whole`.

### Task 3: Reading for the loader and the sync

**Files:** modify `src/steam_manager/archive.py`; test `tests/steam_manager/test_archive.py`.

**Interfaces (produces):**

- `answers(self, *, source: str | None = None, kind: Kind | None = None) -> Iterator[Answer]`: every matching answer, ordered by `(source, kind, key, country)`. They are streamed with `execution_options(yield_per=500)`, so a 200,000-app catalog is never held whole.

- `fetched_at(self, source: str, kind: Kind, *, country: str = "") -> dict[str, datetime]`: key → time, the sync's staleness input.

- `class CorruptAnswerError(ValueError)` with `source`, `kind`, `key` and `country`. It is raised by `get` and `answers` for a body that won't decompress, and its message names those four.

- [ ] **Step 1: failing tests**

```python
def test_answers_come_in_key_order() -> None             # put keys "70", "400", "620" (any order) → ["400", "620", "70"] (text order, as stored)
def test_answers_filter_by_kind_and_source() -> None
def test_answers_are_streamed() -> None                   # a generator: islice(archive.answers(), 1) yields one of 1,200 stored answers
def test_fetched_at_maps_each_key_to_its_time() -> None   # only the asked kind and country
def test_a_corrupt_body_names_its_answer() -> None        # Review Focus 4: overwrite a blob with b"oops" via sqlite3
@given(body=st.text(), at=st.datetimes(timezones=st.just(UTC)))
def test_any_text_and_time_come_back_exactly(body: str, at: datetime) -> None  # Review Focus 5; tmp_path_factory, since hypothesis forbids function-scoped fixtures
```

- [ ] **Step 2:** run; expect `AttributeError: 'Archive' object has no attribute 'answers'`.
- [ ] **Step 3:** implement. `Kind(row.kind)` rebuilds the enum. A `compression.zstd.ZstdError` is re-raised as `CorruptAnswerError ... from None`.
- [ ] **Step 4:** pass, `just check`, `just docs`. **Step 5:** commit `feat(archive): read answers for the loader and the sync`.

### Task 4: Spec, changelog and the pull request

**Files:** modify the spec's *Raw archive* (the decisions table above, as builder's calls) and `CHANGELOG.md` (Added: "Raw archive: the latest answer per source, kind, key and country, compressed, in a per-profile SQLite file."). Add this plan as `docs/superpowers/plans/2026-11-15-m1-part4-raw-archive.md`.

- [ ] **Step 1:** `just check`, `just docs`. **Step 2:** commit `docs: record the raw archive's decisions`; push `feat/raw-archive`; open the pull request; CI green; final reviewer on the most capable model; fix pass; merge by rebase.

## Verification

- Per task: named tests seen failing, then passing; `uv run pytest` green with 100% branch coverage.
- `just check`, `just docs`; CI on Ubuntu, Windows and macOS (the WAL and threads tests run on all three).
- No live test: the archive touches no network.

## Execution

Inline (`superpowers:executing-plans`), then one fresh reviewer on the most capable model before the merge. The ledger is `.superpowers/sdd/2026-11-15-m1-part4-raw-archive/progress.md`.
