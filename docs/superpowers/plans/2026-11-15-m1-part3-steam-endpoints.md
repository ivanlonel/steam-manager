# Milestone 1, part 3: Steam payload models and endpoints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch every Steam answer milestone 1 needs, without credentials, as raw **answers** ready for the raw archive. Add Pydantic models that validate those answers and report every field nothing declares.

**Architecture:** Endpoint functions in `src/steam_manager/steam/` call the transport. They split a batched answer into one `Answer` per item and return or yield `Answer` records; they never build rows (ADR 0002: a source only writes raw answers). The payload models in `src/steam_manager/steam/models/` are for the loader stage. This stage proves them against recorded, sanitized fixtures: every fixture must parse with no unknown fields. The transport gains a `check` hook, so that "a 200 without `store_items`" is retried and counted like any other failure.

**Tech Stack:** Python 3.15, httpx (through `steam_manager.transport`), Pydantic 2.13, pytest, hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md` (*Steam endpoints*, *Catalog depth*, *Raw archive*, *Loader*, *Anti-goals*). The field inventory in Appendix A comes from `../steam-collection/steam-database/steam-database.ipynb`, cells 3 to 6. The request shapes come from `steam-games.ipynb`, `steam-wishlist.ipynb` and `steam-owned-games.ipynb`.

**Where this fits:** stage 3 of milestone 1. Next come the raw archive (it stores these `Answer`s), the schema, the loader (it uses these models), then sync.

## Global Constraints

- Python `>=3.15`; lines up to 99; complete typing; Sphinx docstrings without `:type:`/`:rtype:`, attributes documented.
- Test first; tests mirror `src/` (`src/steam_manager/steam/store.py` → `tests/steam_manager/steam/test_store.py`).
- No credentials anywhere in milestone 1. Every request goes through `Transport.get` with an explicit `interval`.
- Report, don't drop: a field no model declares is reported with its full path, never silently discarded.
- Fixtures recorded from Steam are public store data. No account data is committed: the wishlist and followed fixtures are written by hand.
- `pydantic` joins `dependencies` in the task that first imports it.
- Network tests carry `@pytest.mark.live` and run only with `-m live`.
- One pull request, never a draft, `just check` and `just docs` first, merged by rebase. Before 2026-11-18 there is no Sourcery review, and the 150,000-character limit is waived.

## Decisions this plan makes (builder's calls)

| Topic          | Decision                                                                                                                                                                                                                                                                                               | Why                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Seam           | `Answer(source, kind, key, country, body, fetched_at)`, a frozen dataclass in `src/steam_manager/answers.py`. `body` is JSON text: a batched answer's item re-serialized with `json.dumps(item, ensure_ascii=False, separators=(",", ":"))`, a single answer verbatim                                  | The spec's archive row is (source, kind, key, country) holding the latest answer. Re-serializing an item keeps its content; only whitespace changes.   |
| Kinds          | `Kind` StrEnum: `store_item` (full entry), `store_item_light`, `listing`, `store_categories`, `tags`, `app_genres`, `app_reviews`, `review_histogram`, `current_players`, `wishlist`, `followed_apps`                                                                                                  | Light and full answers must not overwrite each other in the archive. The `listing` answer is what tells the loader that an app is listed in a country. |
| Light catalog  | `Query` with `data_request={"include_reviews": true}`, 1,000 per page, `sort: 2`, games, mods and software                                                                                                                                                                                             | A light item carries `name`, `type`, `reviews`, `best_purchase_option`, `categories` and `content_descriptorids` (checked live on 2026-11-15).         |
| Full entries   | Always `GetItems`, 100 ids per batch with the full `data_request`; never `Query` with full data                                                                                                                                                                                                        | Batches by appid make the full catalog resumable. Cost: about 2,000 batches instead of 400 pages.                                                      |
| Streaming      | `list_apps` and `get_items` are async generators yielding answers as pages and batches arrive                                                                                                                                                                                                          | The full catalog holds about 200,000 items. The notebook peaked at 14 GB by holding pages.                                                             |
| Intervals      | `Query` 0.5 s (the notebook's pause between pages); `GetItems` 1.0 s; `appdetails` 1.5 s; `GetAppReviews` and `GetNumberOfCurrentPlayers` 0.2 s; histogram 1.0 s; lookups, wishlist, followed and vanity 1.0 s                                                                                         | From the spec's table and the notebooks; the spec leaves the rest to the builder.                                                                      |
| Languages      | The endpoints take Steam's API language name (`language="english"`) and, for `GetStoreCategories`, the ELanguage number (`elanguage=0`). They don't map one to the other.                                                                                                                              | The profile settings stage owns the language list.                                                                                                     |
| Exact counts   | `exact_review_answers` follows the notebook: `purchase_type` 1 if free else 0; ask the other type too when the total is more than 2% off `review_count`. It returns both answers.                                                                                                                      | The loader picks the closer total, so the choice stays reproducible from the archive.                                                                  |
| Profiles       | `resolve_steamid` accepts a SteamID64, `…/profiles/<id>` or `…/id/<vanity>`. A vanity is resolved through `steamcommunity.com/id/<name>?xml=1`; a missing one answers 200 with `<error>` (checked live).                                                                                               | No notebook resolves vanities. The spec names this endpoint.                                                                                           |
| Unknown fields | `extra="allow"` on every model. `unknown_fields(model)` returns sorted dotted paths (`[]` marks a list element), skipping extras whose value is `None`, `[]` or `{}`, as the notebook's `take()` does. Asset kinds are declared fields, so a new kind is reported.                                     | The notebook never reported new asset kinds.                                                                                                           |
| Fixtures       | `scripts/record_steam_fixtures.py` (live, run by hand) writes public store answers, pretty-printed, to `tests/fixtures/steam/`. Wishlist and followed fixtures are written by hand from the documented shape. `typos` excludes `tests/fixtures/`. `check-json` now has files to check, so it is added. | Store data is public; account data never enters the repo.                                                                                              |

## Review Focus

1. The catalog shifts while it is paged (apps appear or vanish): duplicates are dropped, and a gap within 0.1% of the total is accepted. A bigger gap raises `ListingMismatchError` naming the country, the unique count and the total, after the answers already yielded. Test in Task 5.
1. `GetItems` answers 200 without `store_items`, as Steam does on big answers: retried with the backoff and counted as a failure, finally `RequestFailedError` with reason `HTTP 200, no store_items`. Test in Tasks 1 and 5.
1. A delisted app (`appid` 0, `id` set) and a `success: 15` item (not sold in the country): both yielded, keyed by `id`. Test in Task 5.
1. A vanity that doesn't exist, a malformed URL, or a 17-digit number that isn't a SteamID64: `ProfileNotFoundError` (a `ValueError`) naming the input, never `None` or a crash. Test in Task 7.
1. A field Steam adds tomorrow, deep down (`purchase_options[].active_discounts[].new_field`): reported at that path. An unknown key with an empty value isn't. Test in Task 3.

______________________________________________________________________

### Task 1: The transport's `check` hook

**Files:** Modify `src/steam_manager/transport.py`; test `tests/steam_manager/test_transport.py`. Move `FakeClock`, `transport_for`, `answer` and `answers` to `tests/_fakes.py`; the leading underscore keeps `name-tests-test` off it. Import them from there.

**Interfaces:** Produces `Transport.get(url, *, interval, params=None, allow=(), check: Callable[[httpx.Response], str | None] | None = None) -> httpx.Response`. `check` runs on every answer that would be returned. A non-`None` result is a reason: the answer is treated like a 5xx (retried with the backoff, counted per host), and the final failure's reason is `f"HTTP {status}, {reason}"`.

- [ ] **Step 1: failing tests**

```python
def test_a_failed_check_is_retried() -> None:
    # answers: 200 {"response": {}} then 200 {"response": {"store_items": []}}
    # check = lambda r: None if "store_items" in r.json()["response"] else "no store_items"
    assert response.json()["response"] == {"store_items": []}
    assert clock.sleeps == [10.0]


def test_a_check_that_never_passes_fails_naming_its_reason() -> None:
    assert caught.value.reason == "HTTP 200, no store_items"
    assert caught.value.attempts == 6
```

- [ ] **Step 2:** run; expect `TypeError: ... unexpected keyword argument 'check'`.
- [ ] **Step 3:** implement inside `_send`: after `is_success or status in allow`, `problem = check(response) if check else None`. If there is a problem, `reason = f"{reason}, {problem}"` and `wait = backoff_seconds(attempt)`; otherwise return the response.
- [ ] **Step 4:** the whole suite passes. **Step 5:** commit `feat(transport): let callers reject a 2xx answer`.

### Task 2: `Answer`, `Kind` and the Web API call

**Files:** Create `src/steam_manager/answers.py`, `src/steam_manager/steam/__init__.py`, `src/steam_manager/steam/webapi.py`; tests `tests/steam_manager/test_answers.py`, `tests/steam_manager/steam/__init__.py`, `tests/steam_manager/steam/test_webapi.py`.

**Interfaces (produces):**

- `class Kind(StrEnum)` with the members in the decisions table.
- `@dataclass(frozen=True, slots=True) class Answer`: `source: str`, `kind: Kind`, `key: str`, `country: str` (`""` when the answer doesn't depend on one), `body: str`, `fetched_at: datetime` (UTC).
- `def item_answer(kind: Kind, item: Mapping[str, JsonValue], *, key: str, country: str) -> Answer`: compact JSON, `source="steam"`, `fetched_at=datetime.now(UTC)`.
- `def response_answer(kind: Kind, response: httpx.Response, *, key: str, country: str = "") -> Answer`: body is `response.text`.
- `WEB_API: Final = "https://api.steampowered.com"`.
- `async def call(transport: Transport, interface: str, method: str, *, interval: float, input_json: Mapping[str, JsonValue] | None = None, params: Mapping[str, str] | None = None, allow: Collection[int] = (), check: Callable[[httpx.Response], str | None] | None = None) -> httpx.Response`: GET `f"{WEB_API}/{interface}/{method}/v1/"`, with `input_json` sent as `params["input_json"] = json.dumps(input_json, separators=(",", ":"))`.
- `def has_response(response: httpx.Response) -> str | None`: `"not JSON"` / `"no response object"` / `None`. It is the default check for every Web API call.

`JsonValue` is `pydantic.JsonValue`, so `pydantic~=2.13` is added here.

- [ ] **Step 1: failing tests**

```python
def test_item_answer_keeps_the_item_compact_and_unchanged() -> None:
    item = {"id": 620, "name": "Portal 2", "nested": {"a": [1, 2]}}
    answer = item_answer(Kind.STORE_ITEM, item, key="620", country="BR")
    assert json.loads(answer.body) == item
    assert answer.body == '{"id":620,"name":"Portal 2","nested":{"a":[1,2]}}'
    assert (answer.source, answer.kind, answer.key, answer.country) == (
        "steam",
        "store_item",
        "620",
        "BR",
    )
    assert answer.fetched_at.tzinfo is UTC


def test_call_sends_input_json_to_the_versioned_method() -> None:
    # handler records request.url
    assert seen.path == "/IStoreQueryService/Query/v1/"
    assert json.loads(seen.params["input_json"]) == {"query": {"start": 0}}


def test_an_answer_without_a_response_object_is_retried() -> None:
    # answers: 200 b"<html>", then 200 {"response": {}}
    assert clock.sleeps == [10.0]
```

- [ ] **Steps 2–5:** run, see `ModuleNotFoundError`; `uv add "pydantic~=2.13"`; implement; whole suite passes; commit `feat(steam): add answers and the Web API call`.

### Task 3: Payload model base and the unknown-field report

**Files:** Create `src/steam_manager/steam/models/__init__.py`, `.../models/base.py`; test `tests/steam_manager/steam/models/test_base.py` (plus `__init__.py` files).

**Interfaces (produces):** `class SteamModel(BaseModel)` with `model_config = ConfigDict(extra="allow", frozen=True)`; `def unknown_fields(model: BaseModel) -> list[str]`. The function walks declared fields holding models, lists of models and dicts of models, and returns the sorted, de-duplicated paths of extras whose value isn't `None`, `[]` or `{}`.

- [ ] **Step 1: failing tests** (with small test-local models `Inner`/`Outer`):

```python
def test_a_declared_payload_has_no_unknown_fields() -> None:
    assert unknown_fields(Outer.model_validate({"name": "x", "items": [{"price": "5"}]})) == []


def test_an_unknown_field_is_reported_at_its_path() -> None:
    payload = {"name": "x", "new": 1, "items": [{"price": "5", "extra": {"a": 1}}]}
    assert unknown_fields(Outer.model_validate(payload)) == ["items[].extra", "new"]


def test_an_unknown_field_with_an_empty_value_is_not_reported() -> None:
    assert unknown_fields(Outer.model_validate({"name": "x", "a": None, "b": [], "c": {}})) == []


def test_int64_strings_become_ints() -> None:
    assert Outer.model_validate({"name": "x", "items": [{"price": "1999"}]}).items[0].price == 1999
```

- [ ] **Steps 2–5:** run (fail on import); implement; pass; commit `feat(steam): report payload fields nothing declares`.

### Task 4: Store item models, fixtures and the recorder

**Files:**

- Create `src/steam_manager/steam/models/store_item.py`, `offers.py`, `media.py`, `details.py`, `lookups.py`, `reviews.py` and `account.py`.
- Create `scripts/record_steam_fixtures.py` and `tests/fixtures/steam/**`.
- Test `tests/steam_manager/steam/models/test_store_item.py`, `test_lookups.py`, `test_reviews.py` and `test_account.py`.
- Modify `.pre-commit-config.yaml` (`check-json`, excluding `.github/renovate.json`) and `pyproject.toml` (`[tool.typos] files.extend-exclude = ["tests/fixtures/"]`).

**Interfaces (produces):** the models in Appendix A, every field optional (`T | None = None`, lists `list[T] = []`) except `StoreItem.id: int`. The top-level answer models are `StoreItem` (recursive through `included_items.included_apps`), `StoreCategoriesAnswer`, `TagListAnswer`, `AppDetailsGenresAnswer`, `AppReviewsAnswer`, `ReviewHistogramAnswer`, `CurrentPlayersAnswer`, `WishlistAnswer` and `FollowedAppsAnswer`.

- [ ] **Step 1: record the fixtures** (live, by hand).
  - `uv run python scripts/record_steam_fixtures.py` writes `GetItems` answers for one app per case, in BR unless noted. Each is the item's JSON, indented by 2, at `tests/fixtures/steam/store_item/<appid>-<country>.json`. The cases:
    - Portal 2 (620), in BR and in US
    - a free game (570)
    - a DLC
    - an Early Access game
    - an app with VR support
    - an app with a season pass
    - an app with anticheat details
    - an app declaring generative AI
    - a bundle-bearing app
    - a delisted app (12170 or 224060)
    - one app answered with `success: 15` in BR
  - The recorder also writes one light `Query` item, the category list, the tag list, the `appdetails` genres of 620, `GetAppReviews` for 620 (`purchase_type` 0), the histogram of 620 and the current players of 570.
  - A case that no longer holds is swapped for another app, and the swap is noted in the ledger.
  - `wishlist.json` and `followed_apps.json` are written by hand: three items with appids 620, 400 and 70, priorities 1, 2 and 0, and fixed dates.
- [ ] **Step 2: failing tests**

```python
@pytest.mark.parametrize(
    "path", sorted(FIXTURES.glob("store_item/*.json")), ids=attrgetter("stem")
)
def test_a_recorded_store_item_has_no_unknown_fields(path: Path) -> None:
    item = StoreItem.model_validate_json(path.read_bytes())
    assert unknown_fields(item) == []


def test_a_new_field_deep_down_is_reported() -> None:  # Review Focus 5
    payload = json.loads(PORTAL_2_BR.read_bytes())
    payload["purchase_options"][0].setdefault("active_discounts", [{}])[0]["new_field"] = 1
    assert "purchase_options[].active_discounts[].new_field" in unknown_fields(
        StoreItem.model_validate(payload)
    )


def test_portal_2_carries_the_values_the_loader_needs() -> None:
    item = StoreItem.model_validate_json(PORTAL_2_BR.read_bytes())
    assert item.id == 620 and item.reviews.summary_filtered.review_count > 100_000
    assert item.best_purchase_option.final_price_in_cents > 0  # an int64 string, as an int
```

Each other answer model gets one test against its fixture: no unknown fields, and one value read.

- [ ] **Step 3:** run; expect them to fail on import. **Step 4:** write the models from Appendix A. Each fixture's remaining unknown paths name the fields still missing; add each one as declared. **Step 5:** pass; `just check`; commit `feat(steam): add the payload models and recorded fixtures`.

### Task 5: Catalog endpoints

**Files:** Create `src/steam_manager/steam/store.py`; test `tests/steam_manager/steam/test_store.py`.

**Interfaces (produces):**

- `FULL_DATA_REQUEST: Final[Mapping[str, bool | int]]` (the spec's flags plus `include_tag_count: 100`); `LIGHT_DATA_REQUEST: Final = {"include_reviews": True}`.

- `class ListingMismatchError(ValueError)` with `country: str`, `unique: int`, `total: int`.

- `async def list_apps(transport, *, country: str, language: str = "english") -> AsyncIterator[Answer]`: pages of 1,000 with `sort: 2`, `start` advancing by 1,000, type filters `include_games`, `include_mods`, `include_software`, and `context={"language", "country_code"}`. Yields a `store_item_light` answer per new `id`. After the last page, it yields one `listing` answer (key `""`, body `{"total_matching_records": N, "appids": [...]}`), or raises `ListingMismatchError` when `abs(unique - total) > total * 0.001`. Check: `metadata` present.

- `async def get_items(transport, appids: Iterable[int], *, country: str, language: str = "english") -> AsyncIterator[Answer]`: sorted batches of 100, `ids=[{"appid": n}]`, `FULL_DATA_REQUEST`. Check: `store_items` present (Review Focus 2). Yields a `store_item` answer per item, keyed by `str(item["id"])`, `success: 15` included. An asked appid missing from the answer is logged at WARNING with its batch count.

- [ ] **Step 1: failing tests** (MockTransport handlers built from small dicts):

  - `test_list_apps_asks_ascending_appid_pages_of_a_thousand`: the decoded `input_json` of the first request equals the expected dict exactly.
  - `test_list_apps_pages_until_the_total`: total 2,500 → starts `[0, 1000, 2000]`, and `clock.sleeps` between pages are `0.5`.
  - `test_list_apps_drops_repeated_ids`.
  - `test_list_apps_ends_with_the_listing`: last answer's kind is `listing`, `appids` sorted.
  - `test_a_gap_over_a_thousandth_raises_after_yielding` (Review Focus 1): `pytest.raises(ListingMismatchError, match="BR")` and the items already collected are kept.
  - `test_get_items_asks_batches_of_a_hundred` (250 appids → 3 requests of 100, 100, 50).
  - `test_get_items_keys_by_id_even_when_appid_is_zero` and `test_get_items_yields_items_not_sold_in_the_country` (Review Focus 3).
  - `test_get_items_retries_an_answer_without_items` (Review Focus 2).

- [ ] **Steps 2–5:** see them fail, implement, pass, commit `feat(steam): list the catalog and fetch store items`.

### Task 6: Lookups, reviews and per-app figures

**Files:** Modify `src/steam_manager/steam/store.py`; create `src/steam_manager/steam/reviews.py`; tests `test_store.py`, `tests/steam_manager/steam/test_reviews.py`.

**Interfaces (produces):**

- `async def store_categories(transport, *, elanguage: int = 0) -> Answer`: `IStoreBrowseService/GetStoreCategories`, `params={"elanguage": str(elanguage)}`, key `str(elanguage)`.

- `async def tag_list(transport, *, language: str = "english") -> Answer`: `IStoreService/GetTagList`, key `language`.

- `async def app_genres(transport, appid: int, *, language: str = "english") -> Answer`: `store.steampowered.com/api/appdetails?appids=<id>&filters=genres&l=<language>`, interval 1.5 s.

- `async def app_reviews(transport, appid: int, *, purchase_type: int) -> Answer`: `IUserReviewsService/GetAppReviews` with `input_json={"appid", "languages": ["all"], "num_per_page": 1, "purchase_type"}`, key `f"{appid}:{purchase_type}"`, interval 0.2 s.

- `async def exact_review_answers(transport, appid: int, *, is_free: bool, review_count: int) -> list[Answer]`: one or two answers, by the rule in the decisions table.

- `async def review_histogram(transport, appid: int, *, language: str = "english") -> Answer`: `store.steampowered.com/appreviewhistogram/<appid>?l=<language>`, interval 1.0 s.

- `async def current_players(transport, appid: int) -> Answer`: `ISteamUserStats/GetNumberOfCurrentPlayers`, `params={"appid"}`, `allow={404}`, interval 0.2 s.

- [ ] **Step 1: failing tests**, one per function, asserting the request (path and params) and the answer's kind and key. Also:

  - `test_exact_counts_ask_steam_purchases_for_a_paid_app` (one answer, `purchase_type` 0);
  - `test_exact_counts_also_ask_the_other_type_when_three_percent_off` (two answers);
  - `test_exact_counts_ask_all_reviews_for_a_free_app`;
  - `test_a_404_is_an_answer_for_current_players`.

- [ ] **Steps 2–5:** fail, implement, pass, commit `feat(steam): fetch lookups, review counts and player figures`.

### Task 7: Profiles, wishlist and followed apps

**Files:** Create `src/steam_manager/steam/community.py`; test `tests/steam_manager/steam/test_community.py`.

**Interfaces (produces):**

- `class ProfileNotFoundError(ValueError)` with `profile: str`.

- `async def resolve_steamid(transport, profile: str) -> int`:

  - A 17-digit number starting `7656119` is returned as it is.
  - `https://steamcommunity.com/profiles/<id>` gives its `<id>`, under the same rule.
  - `https://steamcommunity.com/id/<vanity>` (with or without a scheme or trailing slash) goes to `steamcommunity.com/id/<vanity>?xml=1` (interval 1.0 s), and the result is read from `<steamID64>(\d{17})</steamID64>` with a regular expression: no XML parser for untrusted input.
  - Anything else raises `ProfileNotFoundError`.

- `async def wishlist(transport, steamid: int) -> Answer`: `IWishlistService/GetWishlist`, `params={"steamid": str(steamid)}`, key `str(steamid)`.

- `async def followed_apps(transport, steamid: int) -> Answer`: `IStoreService/GetGamesFollowed`, same params.

- [ ] **Step 1: failing tests:**

  - `test_a_steamid_is_returned_without_a_request`
  - `test_a_profiles_url_is_read_without_a_request`
  - `test_a_vanity_url_is_resolved_through_the_xml_profile` (handler returns `<profile><steamID64>76561197960287930</steamID64>…`)
  - `test_a_missing_vanity_raises_profile_not_found` (the `<error>` answer)
  - `@pytest.mark.parametrize` over `["https://example.com/id/x", "123", "76561190000000000x", ""]` → `ProfileNotFoundError` (Review Focus 4)
  - `test_wishlist_and_followed_are_keyed_by_steamid`

- [ ] **Steps 2–5:** fail, implement, pass, commit `feat(steam): resolve profiles and fetch public account lists`.

### Task 8: Live tests, docs and the pull request

**Files:**

- Tests `tests/steam_manager/steam/test_live.py`, every test `@pytest.mark.live`. Each `test_*` module mirrors a source module, so live checks for several modules sit in one file named after none. `name-tests-test` accepts any `test_*.py`; the rule is the project's own, and a ruling records the exception.

- Docs: modify the spec's *Steam endpoints* (the intervals, light catalog through `Query` only, full entries through `GetItems` only, the answer kinds) and `GLOSSARY.md` (**Answer**: what one source returned for one key, in one country when it depends on one; *Avoid*: response, payload, record). Modify `CHANGELOG.md`, and add this plan to `docs/superpowers/plans/2026-11-15-m1-part3-steam-endpoints.md`.

- [ ] **Step 1: live tests:**

  - Portal 2 from `GetItems` in BR has `id` 620 and no unknown fields;
  - the first BR page reports more than 150,000 apps;
  - the category and tag lists are not empty;
  - `exact_review_answers(620, …)` gives `total_positive > 300_000`;
  - the histogram of 620 has rollups;
  - `current_players(570)` is above 0;
  - `resolve_steamid("https://steamcommunity.com/id/gabelogannewell")` is `76561197960287930`.
    Run: `uv run pytest -m live`; all pass, or a failure names an endpoint that changed (stop and report).

- [ ] **Step 2:** `just check`, `just docs`; commit `docs: record the Steam endpoints and answers`; push `feat/store-endpoints`; open the pull request; CI green; final reviewer; merge by rebase.

## Verification

- Per task: named tests seen failing, then passing; `uv run pytest` green.
- `uv run pytest -m live` passes on the maintainer's machine (Task 8).
- Every fixture parses with `unknown_fields(...) == []`.
- `just check`, `just docs`; CI on three systems.

## Execution

Inline (`superpowers:executing-plans`), as before. The final fresh review runs on the most capable model; the ledger is `.superpowers/sdd/2026-11-15-m1-part3-steam-endpoints/progress.md`. The CLAUDE.md lesson about prefixed hypothesis secrets is already committed on `feat/store-endpoints` (f5874fd).

______________________________________________________________________

## Appendix A: store item fields (from the notebook's loader, which loaded 200,000 apps)

Types: `int` also accepts Steam's int64-as-string values (lax Pydantic). "Dates" are epoch seconds, and 0 means none. Every field is optional unless marked required.

- **StoreItem:** `id` (required), `appid` (0 on delisted apps), `item_type`, `visible`, `success`, `name`, `type`, `store_url_path`, `store_url_slug`, `store_url_path_override`, `is_free`, `unlisted`, `unvailable_for_country_restriction` (Steam's spelling), `is_early_access`, `is_coming_soon`, `full_description_bbcode`, `tagids: list[int]`, `content_descriptorids: list[int]`.
  - Sub-objects: `categories`, `tags[]`, `supported_languages[]`, `reviews`, `basic_info`, `release`, `free_weekend`, `platforms`, `game_rating`, `links[]`, `purchase_notes[]`, `optin_registration_tags[]`, `package_groups[]`, `purchase_options[]`, `best_purchase_option`, `included_items`, `related_items`, `assets`, `assets_without_overrides`, `screenshots`, `trailers`, `extra_details`.
- **Categories:** `supported_player_categoryids`, `feature_categoryids`, `controller_categoryids`: `list[int]`.
- **Tag:** `tagid`, `weight`.
- **SupportedLanguage:** `elanguage`, `eadditionallanguage`, `supported`, `full_audio`, `subtitles`.
- **Reviews:** `summary_filtered`, `summary_language_specific`, `summary_unfiltered`, each a ReviewSummary of `review_count`, `percent_positive`, `review_score`, `review_score_label`.
- **BasicInfo:** `short_description`, `capsule_headline`, and `developers[]`, `publishers[]`, `franchises[]`, each a Credit of `name` and `creator_clan_account_id`.
- **Release:** the dates `steam_release_date`, `original_release_date`, `original_steam_release_date`, `mac_release_date`, `linux_release_date`, `release_from_early_access_date`; also `release_from_early_access_style`, `coming_soon_display`, `custom_release_date_message`, `is_preload`, `is_early_access`, `is_coming_soon`.
- **FreeWeekend:** `start_time`, `end_time`, `text`, `appid`.
- **Platforms:** `windows`, `mac`, `steamos_linux`, `steam_deck_compat_category`, `steam_machine_compat_category`, `steam_os_compat_category`, `steam_frame_compat_category`, and `vr_support`.
  - **VrSupport:** `vrhmd`, `vrhmd_only`, `htc_vive`, `oculus_rift`, `windows_mr`, `valve_index`, `show_optional_vr_mode_notice`.
- **GameRating:** `type`, `agency`, `rating`, `agency_rating`, `required_age`, `use_age_gate`, `banned`, `esrb_online_music_not_rated`, `esrb_online_interactions_not_rated`, `interactive_elements`, `descriptors: list[str]`, `image_url`, `survey_interactive_elements: list[int]`, `content_survey_notes`.
- **Simple lists:**
  - Link: `link_type`, `url`, `text`.
  - PurchaseNote: `type`, `highlighted`, `text_bbcode`.
  - OptinTag: `optin_name`, `values: list[str]`.
  - PackageGroup: `name`, `display_type`, `heading`, `dropdown_title`, `dropdown_description_bbcode`.
- **PurchaseOption:**
  - Ids and flags: `packageid`, `bundleid`, `purchase_option_name`, `package_group`, `is_edition`, `must_purchase_as_set`, `included_game_count`, `is_free_license`, `free_with_master_sub_appid`.
  - Prices and discounts: `final_price_in_cents`, `original_price_in_cents`, `price_before_bundle_discount`, `discount_pct`, `bundle_discount_pct`, `combined_discount_pct`, `formatted_final_price`, `formatted_original_price`, `formatted_price_before_bundle_discount`.
  - Display flags: `user_can_purchase_as_gift`, `hide_discount_pct_for_compliance`, `price_cannot_be_displayed_as_discount`.
  - `active_discounts[]`, each an ActiveDiscount of `discount_amount`, `discount_description`, `discount_end_date`.
  - `recurrence_info`, a RecurrenceInfo of `packageid`, `billing_agreement_type`, `renewal_time_unit`, `renewal_time_period`, `renewal_price_in_cents`, `formatted_renewal_price`.
- **IncludedItems:**
  - `included_apps: list[StoreItem]` (recursive).
  - `included_packages[]` and `included_bundles[]`, each an IncludedOffer: `id`, `item_type`, `visible`, `success`, `name`, `store_url_path`, `store_url_slug`, `appid`, `type`, `purchase_description_bbcode`, `unvailable_for_country_restriction`, `included_types`, `included_appids`, `categories: Categories`, `content_descriptorids`, `best_purchase_option`, `self_purchase_option`.
  - `included_creators[]`, each an IncludedCreator: `id`, `item_type`, `visible`, `success`, `name`, `store_url_path`, `store_url_slug`, `game_count`.
- **RelatedItems:**
  - `parent_appid`;
  - `demos[]` and `standalone_demos[]`, each a Demo of `appid`, `label`, `show_above_purchase`;
  - `demo_appid`, `standalone_demo_appid`, `dlc_parent_appids`: `list[int]`;
  - `playtests[]`, each a Playtest of `appid`, `is_open`;
  - `related_f2p`, a RelatedF2p of `appid`, `header_text`, `description_text`.
- **Assets** (also used for `assets_without_overrides`):
  - Metadata: `asset_url_format`, `page_background_path`, `last_modified`.
  - Kinds: `community_icon`, `edition_comparison`, `header`, `header_2x`, `hero_capsule`, `hero_capsule_2x`, `library_capsule`, `library_capsule_2x`, `library_hero`, `library_hero_2x`, `main_capsule`, `main_capsule_2x`, `page_background`, `raw_page_background`, `small_capsule`, `small_capsule_2x`.
- **Screenshots:** `all_ages_screenshots[]` and `mature_content_screenshots[]`, each a Screenshot of `filename`, `ordinal`, `alt_text`, `category`.
- **Trailers:** `highlights[]` and `other_trailers[]`, each a Trailer:
  - `trailer_base_id`, `trailer_id`, `trailer_name`, `trailer_url_format`, `trailer_category`, `all_ages`, `screenshot_small`, `screenshot_medium`, `screenshot_full`, `captions_manifest`;
  - `microtrailer[]`, each a TrailerFile of `filename` and `type`;
  - `adaptive_trailers[]`, each an AdaptiveTrailer of `cdn_path` and `encoding`.
- **ExtraDetails:**
  - Flags: `vetted`, `has_community_hub`, `points_shop_eligible`, `controller_wizard_complete`, `item_store_eligible`, `item_store_show_featured`, `no_mouse_keyboard_support`, `refund_checks_ea_playtime`, `user_account_third_party_link_to_steam`.
  - Text: `drm_third_party_type`, `user_account_third_party`, `legal_notice_bbcode`, `partner_awards_bbcode`, `content_survey_notes`, `content_survey_ai_notes`, and `interactive_elements: list[int]`.
  - **LinksAndInfo:** `genreids: list[int]`, `available_documents: list[int]`, `manufacturers: list[str]`, `website`, `stats_url`, `online_manual_url`, `privacy_policy_url`, `health_warning_url`, `achievements_visible`, `achievement_count`.
  - **Metacritic:** `score`, `url`, `always_show`.
  - **Anticheat:** `name`, `name_loc`, `kernel_mode`, `uninstall_completely`, `boot_protection`, `boot_protection_name`.
  - **AiGenerationService:** `name`, `url`.
  - **EarlyAccess:** `description_bbcode`, `why_bbcode`, `how_long_bbcode`, `full_version_bbcode`, `current_state_bbcode`, `pricing_bbcode`, `community_bbcode`.
  - **Lists:**
    - `eula[]`: `name`, `url`.
    - `press_review[]`: `quote`, `score`, `site`, `url`.
    - `section[]`: `label`, `banner`, `content_bbcode`.
    - `sale_pages[]`: `clan_account_id`, `event_gid`.
    - `steam_award[]`: `voteid`, `award_year`, `localization.title`.
  - **SeasonPass:** `appid` and `milestones[]`, each a Milestone of:
    - `milestone_id`, `appid`, `coming_soon_appid`, `event_gid`, `rtime_complete`, `shipped`;
    - `dates[]`, each a MilestoneDate of `coming_soon_display_type` and `rtime`;
    - `title[]` and `milestone_desc[]`, each a LocalizedString of `language` and `localized_string`.
  - **SystemRequirements:** `platforms[]`, each a PlatformRequirements of `platform`, `requires_64bit`, `requires_apple_silicon`, `unsupported_os_note` (int, or a bool), `minimum` and `recommended`.
    - Each tier is a Requirements: `os_version`, `os_version_unsupported`, `processor`, `memory`, `graphics`, `directx`, `storage`, `storage_hq`, `sound_card`, `notes`, `legacy_bbcode`, `broadband`, `vr_support`.
    - `memory`, `storage` and `storage_hq` are each an Amount of `amount` and `units`.
- **Other answers:**
  - `StoreCategoriesAnswer.response.categories[]`: `categoryid`, `type`, `internal_name`, `display_name`, `image_url`, `computed`, `edit_url`, `edit_sort_order`.
  - `TagListAnswer.response.tags[]`: `tagid`, `name`.
  - `AppDetailsGenresAnswer`: a root dict of appid to `{success, data: {genres[]: {id: str, description}}}`.
  - `AppReviewsAnswer.response.query_summary`: `total_positive`, `total_negative`, `total_reviews` and whatever else the fixture shows.
  - `ReviewHistogramAnswer`: `success`, and `results` with `rollup_type`, `start_date`, `end_date`, `rollups[]` and `recent[]` (each `date`, `recommendations_up`, `recommendations_down`), and `weeks[]`.
  - `CurrentPlayersAnswer.response`: `player_count`, `result`.
  - `WishlistAnswer.response.items[]`: `appid`, `priority`, `date_added`.
  - `FollowedAppsAnswer.response.appids: list[int]`.
