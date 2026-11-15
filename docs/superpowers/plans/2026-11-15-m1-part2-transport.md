# Milestone 1, part 2: HTTP transport — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One paced, retrying, redacting HTTP client that every source (Steam store, Steam community, HowLongToBeat) goes through, so no later code can hammer a host or leak a secret.

**Architecture:** `src/steam_manager/transport.py` wraps an `httpx.AsyncClient`. A per-host `asyncio.Lock` keeps one request in flight per host and waits the caller's `interval` after the previous request to that host ended (the notebooks' pause-after-call). Retries cover 429, 5xx and network errors, with exponential backoff or `Retry-After`. A per-host count of failures in a row raises a distinct error at ten. Errors and log lines name `METHOD scheme://host/path` only.

**Tech Stack:** Python 3.15, httpx 0.28.1 (`httpx.MockTransport` for tests, no extra test library), pytest, hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md` (sections *Transport*, *Steam endpoints*, *Anti-goals*). Reference: `../steam-collection/steam-games/steam-games.ipynb`, `call()` and `per_app()`.

**Where this fits:** stage 2 of milestone 1 (the approved master plan's pull request 3). The remaining stages follow, each with its own plan: Steam payload models and store endpoints, raw archive, schema part 1, schema part 2 with views, loader, sync, CLI and exports, Kaggle import, HowLongToBeat, usage docs. The milestone list lives in the design doc.

## Global Constraints

- Python `>=3.15`; lines up to 99 characters; complete typing, tests included; Sphinx docstrings without `:type:` / `:rtype:`, attributes with their own docstring.
- Test first (`superpowers:test-driven-development`): every test is seen failing before its code exists.
- Secrets never leak: no token, key, cookie or URL query string in a log line, an exception message, a traceback or an export. "Raise errors that name the endpoint, never the full URL." (CLAUDE.md rule 2)
- A runtime dependency is declared by the change that first imports it: `httpx` joins `dependencies` in Task 1 (deptry fails otherwise).
- Tests mirror `src/`: `src/steam_manager/transport.py` → `tests/steam_manager/test_transport.py`.
- No network in tests: every test uses `httpx.MockTransport`. No global mutable state beyond the logger levels Task 5 sets.
- Conventional Commits; one pull request for the stage, never a draft, `just check` and `just docs` locally first, merged by rebase. Until 2026-11-18 no Sourcery review is expected and the 150,000-character limit is waived.

## Decisions this plan makes (builder's calls; the spec leaves them open)

| Topic              | Decision                                                                                                                                                       | Why                                                                                                                                                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pacing unit        | Per host, at most one request in flight; each `get` waits until its own `interval` has passed since the previous request to that host **ended**                | Matches the notebooks' `sleep(pause)` after each call (30,225 `GetAppReviews` calls at 0.2 s ran with no retries). Lets the store host use 1 s for the histogram and 1.5 s for `appdetails`. |
| `interval`         | Required keyword on every call, no default                                                                                                                     | No endpoint can forget its pacing (anti-goal: hammering). The values come from the spec's endpoint table, in the endpoint modules of the next stage.                                         |
| Retries            | Up to 5 retries (6 attempts) on 429, 5xx, timeouts, network errors and a dropped connection; wait `Retry-After` when present, else 10 s × 2ⁿ⁻¹ capped at 120 s | The notebooks' `Retry(total=5, backoff_factor=10)`.                                                                                                                                          |
| Long `Retry-After` | Over 300 s: no retry, the request fails                                                                                                                        | Honours the server without stalling a sync silently for hours.                                                                                                                               |
| Redirects          | Not followed; a 3xx is a failure unless the caller allows it                                                                                                   | A retired Steam endpoint (`appreviews`) redirects to the store front; following it would archive a web page as an answer.                                                                    |
| Failures in a row  | Counted per host; a success resets the count; the tenth failure raises `FailureStreakError` instead of `RequestFailedError`                                    | "Ten failures in a row stop the step"; a HowLongToBeat outage must not stop a Steam step.                                                                                                    |
| Third-party logs   | `httpx` and `httpcore` loggers set to `WARNING` when a `Transport` is created                                                                                  | httpx logs every URL at INFO, query string included; httpcore logs response headers (`Set-Cookie`) at DEBUG. The transport logs its own redacted lines instead.                              |
| Async tests        | Plain `def` tests calling `asyncio.run(...)`                                                                                                                   | No async pytest plugin to add or configure.                                                                                                                                                  |

## Review Focus

1. Ctrl-C or task cancellation during a retry wait or a pacing wait: `CancelledError` propagates, the host's lock is released (the next `get` to that host proceeds), and nothing is counted as a failure. Test in Task 4.
1. A malformed `Retry-After` (`soon`, `-5`, empty): falls back to the exponential backoff, never raises. Test in Task 3.
1. A 302 from Steam (retired endpoint): a `RequestFailedError` naming `HTTP 302`, the redirect never followed. Test in Task 2.
1. Three tasks calling one host at once: each request starts at least `interval` after the previous one ended, in call order. Test in Task 2.
1. A secret outside the query string: a cookie on the client, a `Set-Cookie` in the answer, a response body that echoes the request. None reaches a message, traceback or log line. Test in Task 5.

______________________________________________________________________

### Task 1: Transport skeleton, error types and the client factory

**Files:**

- Modify: `pyproject.toml` (`dependencies = ["httpx~=0.28.1"]`), `uv.lock`
- Create: `src/steam_manager/transport.py`
- Test: `tests/steam_manager/test_transport.py`

**Interfaces:**

- Produces:

  - `class FetchError(Exception)`: base of both errors below.
  - `class RequestFailedError(FetchError)` with attributes `method: str`, `endpoint: str`, `status: int | None` (None for network errors), `reason: str` (`"HTTP 503"` or the httpx exception's class name), `attempts: int`. Message: `f"{method} {endpoint} failed: {reason} after {attempts} attempt(s)"` (`attempt` when 1).
  - `class FailureStreakError(FetchError)` with `host: str`, `count: int`. Message: `f"{host} failed {count} requests in a row; stopping"`.
  - `class Transport` with `__init__(self, client: httpx.AsyncClient, *, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None` and `async def get(self, url: str, *, interval: float, params: Mapping[str, str] | None = None, allow: Collection[int] = ()) -> httpx.Response`.
  - `def make_client() -> httpx.AsyncClient`.
  - Module constants (`Final`): `TIMEOUT_SECONDS = 120.0`, `MAX_RETRIES = 5`, `FIRST_BACKOFF_SECONDS = 10.0`, `MAX_BACKOFF_SECONDS = 120.0`, `MAX_RETRY_AFTER_SECONDS = 300.0`, `FAILURE_STREAK_LIMIT = 10`.

- Test helpers (in the test module, typed): `FakeClock` with `now: float`, `sleeps: list[float]`, `def __call__(self) -> float` and `async def sleep(self, seconds: float) -> None` (records `seconds` and advances `now`); `def transport_for(handler: Callable[[httpx.Request], httpx.Response], clock: FakeClock) -> Transport` building `Transport(httpx.AsyncClient(transport=httpx.MockTransport(handler)), clock=clock, sleep=clock.sleep)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_get_returns_a_successful_answer() -> None:
    # handler returns httpx.Response(200, json={"response": {}})
    response = asyncio.run(transport.get(URL, interval=0.2))
    assert response.status_code == 200


def test_get_sends_the_params() -> None:
    # handler records request.url.params; get(URL, interval=0.2, params={"input_json": "{}"})
    assert seen_params == {"input_json": "{}"}


def test_an_allowed_status_is_returned() -> None:
    # handler returns 404; get(..., allow={404})
    assert response.status_code == 404


def test_an_unexpected_status_fails_without_retrying() -> None:
    # handler returns 400
    with pytest.raises(RequestFailedError) as caught:
        asyncio.run(transport.get(URL, interval=0.2))
    assert caught.value.status == 400
    assert caught.value.attempts == 1
    assert str(caught.value) == (
        "GET https://api.steampowered.com/IStoreQueryService/Query/v1/ failed: HTTP 400 after 1 attempt"
    )


def test_make_client_identifies_the_application() -> None:
    client = make_client()
    assert client.headers["User-Agent"].startswith("steam-manager/")
    assert client.timeout.read == 120.0
    assert client.follow_redirects is False
```

`URL = "https://api.steampowered.com/IStoreQueryService/Query/v1/"`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/steam_manager/test_transport.py`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'steam_manager.transport'`

- [ ] **Step 3: Add httpx and implement the skeleton**

`uv add "httpx~=0.28.1"`, then write the module. The endpoint is `f"{u.scheme}://{u.host}{u.path}"` of `httpx.URL(url)`: no query, fragment or user info. Wrap every httpx failure `from None`, so the httpx exception (whose message holds the full URL) never joins the traceback. The error objects keep no `httpx.Request` or `httpx.Response`. `make_client()` returns `httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False, headers={"User-Agent": f"steam-manager/{__version__} (+https://github.com/ivanlonel/steam-manager)"})`.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run pytest tests/steam_manager/test_transport.py`
Expected: 5 passed

- [ ] **Step 5: Commit** `feat(transport): add the HTTP transport and its error types`

### Task 2: Per-host pacing

**Files:** Modify `src/steam_manager/transport.py`; test `tests/steam_manager/test_transport.py`

**Interfaces:** Consumes Task 1's `Transport`, `FakeClock`, `transport_for`. Produces no new names: `get` now waits per host.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_first_request_to_a_host_does_not_wait() -> None:
    assert clock.sleeps == []


def test_a_second_request_waits_the_interval_after_the_first_ended() -> None:
    # handler advances clock.now by 0.5 (the answer takes 0.5 s) and records clock.now at entry
    # two sequential gets with interval=0.2 -> entry times [0.0, 0.7]
    assert entries == [0.0, 0.7]


def test_each_call_uses_its_own_interval() -> None:
    # get(STORE_URL, interval=1.5) then get(STORE_URL, interval=1.0); instant answers
    assert entries == [0.0, 1.0]


def test_different_hosts_do_not_wait_for_each_other() -> None:
    # get(API_URL, interval=10) then get(STORE_URL, interval=10)
    assert clock.sleeps == []


def test_concurrent_calls_to_one_host_run_one_at_a_time_in_call_order() -> None:
    # asyncio.gather of three gets with interval=0.2, ids 1..3 in params; answers take 0.5 s
    assert entry_ids == ["1", "2", "3"]
    assert entries == [0.0, 0.7, 1.4]


def test_a_redirect_is_a_failure_and_is_not_followed() -> None:
    # handler returns 302 with Location: https://store.steampowered.com/
    assert caught.value.status == 302
    assert handler_calls == 1
```

- [ ] **Step 2: Run them and see the new ones fail** (`uv run pytest tests/steam_manager/test_transport.py -k "wait or interval or hosts or concurrent or redirect"`). Expected: the timing tests FAIL on the entry times or `sleeps`. The redirect test may pass already, because the client doesn't follow redirects and 302 is not 2xx. If it does, record that it pins existing behaviour.

- [ ] **Step 3: Implement**

Use `dict[str, asyncio.Lock]` and `dict[str, float]` (when the last request ended), keyed by `httpx.URL(url).host`. Hold the host's lock for the whole `get`, retries included. Sleep `max(0, last_end + interval - clock())` before each attempt, and record `last_end = clock()` after every attempt, failed ones too.

- [ ] **Step 4: Run the whole module.** Expected: all pass.
- [ ] **Step 5: Commit** `feat(transport): pace requests per host`

### Task 3: Retries and `Retry-After`

**Files:** Modify `src/steam_manager/transport.py`; test `tests/steam_manager/test_transport.py`

**Interfaces:** Consumes Tasks 1–2. Produces `RequestFailedError.attempts` up to `MAX_RETRIES + 1`.

- [ ] **Step 1: Write the failing tests** (interval 0 so `sleeps` holds only retry waits)

```python
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_retryable_status_is_retried(status: int) -> None:
    # handler answers `status` once, then 200
    assert response.status_code == 200
    assert clock.sleeps == [10.0]


def test_the_backoff_doubles_up_to_two_minutes() -> None:
    # handler always 503
    assert caught.value.attempts == 6
    assert clock.sleeps == [10.0, 20.0, 40.0, 80.0, 120.0]


def test_retry_after_seconds_replace_the_backoff() -> None:
    # 429 with Retry-After: 7, then 200
    assert clock.sleeps == [7.0]


def test_a_past_retry_after_date_retries_at_once() -> None:
    # Retry-After: "Wed, 21 Oct 2015 07:28:00 GMT", then 200
    assert clock.sleeps == [0.0]


@pytest.mark.parametrize("value", ["301", "Fri, 01 Jan 2100 00:00:00 GMT"])
def test_a_retry_after_over_five_minutes_fails_without_waiting(value: str) -> None:
    assert caught.value.status == 429
    assert caught.value.attempts == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("value", ["soon", "-5", ""])
def test_a_malformed_retry_after_falls_back_to_the_backoff(value: str) -> None:
    assert clock.sleeps == [10.0]


@pytest.mark.parametrize(
    "error", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError]
)
def test_a_network_error_is_retried(error: type[httpx.HTTPError]) -> None:
    # handler raises error("boom") once, then 200
    assert response.status_code == 200


def test_a_network_error_that_never_clears_fails_naming_its_type() -> None:
    # handler always raises httpx.ConnectError
    assert caught.value.status is None
    assert caught.value.reason == "ConnectError"
    assert caught.value.attempts == 6
```

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL; the retryable statuses raise `RequestFailedError` after 1 attempt.
- [ ] **Step 3: Implement** the loop. Retryable: status 429 or ≥ 500; exceptions `httpx.TimeoutException`, `httpx.NetworkError`, `httpx.RemoteProtocolError`. Any other `httpx.HTTPError` fails at once. Parse `Retry-After` as delta-seconds (a non-negative integer) or an HTTP-date (`email.utils.parsedate_to_datetime`, minus `datetime.now(UTC)`, floored at 0). Anything else falls back to the backoff. A retry always awaits `sleep(wait)`, 0 included, while pacing calls `sleep` only when there is time left to wait, which keeps Task 2's `sleeps == []` and this task's `[0.0]` consistent. Log each retry at WARNING: `"%s %s: %s, retrying in %.0f s (%d of %d)"` with method, endpoint, reason, wait, retry, `MAX_RETRIES`.
- [ ] **Step 4: Run the whole module.** Expected: all pass.
- [ ] **Step 5: Commit** `feat(transport): retry throttled and failed requests`

### Task 4: Failures in a row, and cancellation

**Files:** Modify `src/steam_manager/transport.py`; test `tests/steam_manager/test_transport.py`

**Interfaces:** Consumes Tasks 1–3. Produces `FailureStreakError` raised from `get`, chained `from` the tenth `RequestFailedError`.

- [ ] **Step 1: Write the failing tests** (handler answers 400 so each failure is one attempt)

```python
def test_the_tenth_failure_in_a_row_stops() -> None:
    # nine gets raise RequestFailedError; the tenth raises FailureStreakError
    assert (caught.value.host, caught.value.count) == ("api.steampowered.com", 10)
    assert isinstance(caught.value.__cause__, RequestFailedError)

def test_a_success_resets_the_count() -> None:
    # 9 failures, 1 success, 9 failures: no FailureStreakError

def test_failures_on_another_host_do_not_count() -> None:
    # 9 failures on api.steampowered.com, 9 on store.steampowered.com: no FailureStreakError

def test_the_count_keeps_stopping_until_a_success() -> None:
    # after the FailureStreakError, the next failure raises FailureStreakError with count 11

def test_cancelling_a_waiting_call_releases_the_host() -> None:
    # first get hits 503 and is cancelled during its retry sleep (FakeClock.sleep awaits an
    # asyncio.Event the test never sets, then the test cancels the task)
    # then a get to the same host with a 200 handler completes
    assert response.status_code == 200
    # and the cancelled call counted no failure: nine 400s after it still don't stop
```

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL; no `FailureStreakError` is ever raised.
- [ ] **Step 3: Implement:** `dict[str, int]` of failures in a row per host. Every `RequestFailedError` the transport is about to raise increments it. At `>= FAILURE_STREAK_LIMIT` raise `FailureStreakError(host, count) from failure` instead. A returned response resets it to 0. `CancelledError` touches nothing; the lock's `async with` releases the host.
- [ ] **Step 4: Run the whole module.** Expected: all pass.
- [ ] **Step 5: Commit** `feat(transport): stop after ten failures in a row on a host`

### Task 5: Redaction, enforced with arbitrary secrets

**Files:** Modify `src/steam_manager/transport.py`, `docs/conf.py` (`nitpick_ignore_regex = [("py:class", r"httpx\..*")]`: httpx publishes no Sphinx inventory); test `tests/steam_manager/test_transport.py`

**Interfaces:** Consumes Tasks 1–4. Test helper `def captured_logs(run: Callable[[], object]) -> str`: attaches a list handler to the root logger at DEBUG, sets the root level to DEBUG for the call, and returns every formatted record joined by newlines. It's not caplog: hypothesis forbids function-scoped fixtures.

`SECRETS = st.text(alphabet=string.ascii_letters + string.digits + string.punctuation, min_size=16)`; each test asserts on `forms(secret) = {secret, quote(secret), quote_plus(secret)}`.

- [ ] **Step 1: Write the failing tests**

```python
@given(secret=SECRETS)
def test_a_failure_never_shows_the_query_string(secret: str) -> None:
    # 400 answer; get(URL, interval=0, params={"key": secret, secret: "x"})
    text = str(error) + repr(error) + "".join(traceback.format_exception(error)) + logs
    assert not any(form in text for form in forms(secret))

@given(secret=SECRETS)
def test_retries_and_successes_never_log_the_query_string(secret: str) -> None:
    # 503 then 200, same params; logs only

@given(secret=SECRETS)
def test_a_failure_streak_never_shows_the_query_string(secret: str) -> None:
    # ten 400s with the secret in params; the FailureStreakError's str, repr, traceback, logs

@given(secret=SECRETS)
def test_secrets_outside_the_query_string_never_show(secret: str) -> None:
    # client cookie {"steamLoginSecure": secret}; answer 500 with Set-Cookie: sessionid=<secret>
    # and body f'{{"echo": "{secret}"}}' until retries run out
    # the error's str, repr, traceback and the logs hold no form of the secret
```

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL on the logs, with httpx's own INFO line, `HTTP Request: GET https://api.steampowered.com/...?key=<secret>`. Note in the ledger which assertion failed.
- [ ] **Step 3: Implement:** in `Transport.__init__`, `logging.getLogger("httpx").setLevel(logging.WARNING)` and `logging.getLogger("httpcore").setLevel(logging.WARNING)`. The setting is idempotent, and its comment says why. Add a DEBUG line per answer: `"%s %s -> %d"`.
- [ ] **Step 4: Run the whole suite and the docs.**
  Run: `just check`, then `just docs`.
  Expected: every hook passes, coverage ≥ 90% with `transport.py` at 100% branches, `build succeeded.`
- [ ] **Step 5: Commit** `feat(transport): keep secrets out of errors and logs`

### Task 6: Spec amendment, changelog and the pull request

**Files:** Modify `docs/superpowers/specs/2026-11-14-steam-manager-design.md` (*Transport* gains the decisions table above as builder's calls), `CHANGELOG.md` (Added: "HTTP transport: per-host pacing, retries honouring `Retry-After`, a stop after ten failures in a row, and secrets kept out of errors and logs."); add this plan as `docs/superpowers/plans/2026-11-15-m1-part2-transport.md`.

- [ ] **Step 1:** `just check` and `just docs`. Expected: all pass.
- [ ] **Step 2:** Commit `docs: record the transport's decisions`, push `feat/transport`, open the pull request (not a draft; body in the `mattpocock-skills:pr` shape), wait for CI on all three runners, merge by rebase.

## Verification

- Per task: the named tests are seen failing, then passing; `uv run pytest` stays green.
- Before the pull request: `just check` (every hook, tests with coverage), `just docs` (no warnings), `git diff main...HEAD | Measure-Object -Character` for the record.
- CI: Linting (hooks plus the full-history secret scan), Testing on Ubuntu, Windows and macOS, Build docs.
- No live network test in this stage. The first live calls come with the store endpoints stage, under the `live` marker.

## Execution

Inline (`superpowers:executing-plans`), as for part 1. Then one fresh reviewer on the most capable model checks the whole branch before the merge. The ledger lives at `.superpowers/sdd/2026-11-15-m1-part2-transport/progress.md`.
