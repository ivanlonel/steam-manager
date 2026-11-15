"""Send the application's HTTP requests: paced per host, retried, and never showing a secret."""

import asyncio
import email.utils
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import httpx

from steam_manager import __version__

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Mapping

TIMEOUT_SECONDS: Final = 120.0
"""How long connecting, sending or reading may take before an attempt fails."""
MAX_RETRIES: Final = 5
"""Retries after the first attempt, as in the notebooks' ``Retry(total=5)``."""
FIRST_BACKOFF_SECONDS: Final = 10.0
"""The wait before the first retry when the server gives no ``Retry-After``; it then doubles."""
MAX_BACKOFF_SECONDS: Final = 120.0
"""The longest wait between two attempts when the server gives no ``Retry-After``."""
MAX_RETRY_AFTER_SECONDS: Final = 300.0
"""A ``Retry-After`` longer than this fails the request instead of stalling the sync."""
RETRYABLE_ERRORS: Final = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
"""Network errors a later attempt can get past; any other httpx error fails at once."""
FAILURE_STREAK_LIMIT: Final = 10
"""Failed requests in a row to one host that stop the step that was running."""

_LOGGER: Final = logging.getLogger(__name__)


class FetchError(Exception):
    """A request, or a run of them, failed. The message names the endpoint, never the full URL."""


class RequestFailedError(FetchError):
    """A request failed for good: an unexpected status, or a network error that didn't clear."""

    def __init__(
        self,
        method: str,
        endpoint: str,
        *,
        status: int | None,
        reason: str,
        attempts: int,
        refused_wait: float | None = None,
    ) -> None:
        """
        Describe the failure without the query string, the headers or the answer's body.

        :param method: The HTTP method, such as ``GET``.
        :param endpoint: The URL without its query string, fragment or user info.
        :param status: The last answer's HTTP status, or ``None`` when no answer came.
        :param reason: ``HTTP <status>``, or the name of the network error's class.
        :param attempts: How many times the request was sent.
        :param refused_wait: The ``Retry-After`` seconds the server asked for, when that was
            longer than :data:`MAX_RETRY_AFTER_SECONDS`.
        """
        noun = "attempt" if attempts == 1 else "attempts"
        super().__init__(f"{method} {endpoint} failed: {reason} after {attempts} {noun}")
        self.method: str = method
        """The HTTP method, such as ``GET``."""
        self.endpoint: str = endpoint
        """The URL without its query string, fragment or user info."""
        self.status: int | None = status
        """The last answer's HTTP status, or ``None`` when no answer came."""
        self.reason: str = reason
        """``HTTP <status>``, or the name of the network error's class."""
        self.attempts: int = attempts
        """How many times the request was sent."""
        self.refused_wait: float | None = refused_wait
        """The ``Retry-After`` seconds the server asked for, when too long to honour."""


class FailureStreakError(FetchError):
    """A host failed too often in a row, or asked for a long pause: the step must stop."""

    def __init__(self, host: str, count: int, reason: str) -> None:
        """
        Describe why requests to *host* stop.

        :param host: The host that kept failing.
        :param count: How many of its requests failed in a row, this one included.
        :param reason: Why the last one failed, as :attr:`RequestFailedError.reason`.
        """
        noun = "request" if count == 1 else "requests"
        super().__init__(f"stopping requests to {host}: {reason} ({count} failed {noun} in a row)")
        self.host: str = host
        """The host that kept failing."""
        self.count: int = count
        """How many of its requests failed in a row, this one included."""
        self.reason: str = reason
        """Why the last one failed, as :attr:`RequestFailedError.reason`."""


def endpoint_of(url: httpx.URL) -> str:
    """
    Name a URL the way errors and logs show it: scheme, host and path only.

    :param url: The full URL, possibly with credentials in its query string or user info.
    :return: ``scheme://host/path``.
    """
    return f"{url.scheme}://{url.host}{url.path}"


class Transport:
    """Every HTTP request the application sends goes through one of these."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """
        Wrap *client*.

        :param client: Sends the requests; :func:`make_client` builds the real one.
        :param clock: A monotonic clock, in seconds.
        :param sleep: Waits the given number of seconds.
        """
        # httpx logs every URL at INFO, query string included, and httpcore logs response
        # headers (Set-Cookie among them) at DEBUG. This class logs its own redacted lines, so
        # theirs are silenced below WARNING. Idempotent: every Transport sets the same levels.
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        self._client = client
        self._clock = clock
        self._sleep = sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_ended: dict[str, float] = {}
        self._failures_in_a_row: dict[str, int] = {}

    async def get(
        self,
        url: str,
        *,
        interval: float,
        params: Mapping[str, str] | None = None,
        allow: Collection[int] = (),
        check: Callable[[httpx.Response], str | None] | None = None,
    ) -> httpx.Response:
        """
        Send a GET request and return its answer.

        :param url: The URL, without its query string.
        :param interval: The seconds to leave after the previous request to the same host ended.
        :param params: The query string's parameters.
        :param allow: Statuses besides 2xx that are answers rather than failures, such as 404.
        :param check: Looks at an answer about to be returned and tells why it is a failure
            after all, such as a 200 without the items asked for, or ``None``. A rejected answer
            is retried and counted like a server error. It must not raise.
        :return: The answer.
        :raise RequestFailedError: When the answer has another status, or none came.
        :raise FailureStreakError: Instead, when the host has now failed ten requests in a row.
        """
        request = self._client.build_request("GET", url, params=params)
        endpoint = endpoint_of(request.url)
        host = request.url.host
        # One request in flight per host, so the interval separates one answer from the next
        # request, as the notebooks' pause after each call did.
        async with self._locks.setdefault(host, asyncio.Lock()):
            try:
                response = await self._send(
                    request, endpoint, host, interval=interval, allow=allow, check=check
                )
            except RequestFailedError as failure:
                count = self._failures_in_a_row.get(host, 0) + 1
                self._failures_in_a_row[host] = count
                # A server asking for a long pause gets it: nothing more goes to it this step.
                if count >= FAILURE_STREAK_LIMIT or failure.refused_wait is not None:
                    raise FailureStreakError(host, count, failure.reason) from failure
                raise
            self._failures_in_a_row[host] = 0
            return response

    async def _send(
        self,
        request: httpx.Request,
        endpoint: str,
        host: str,
        *,
        interval: float,
        allow: Collection[int],
        check: Callable[[httpx.Response], str | None] | None,
    ) -> httpx.Response:
        """
        Send *request*, paced and retried, while the caller holds the host's lock.

        :param request: The request to send.
        :param endpoint: The request's URL without its query string.
        :param host: The host whose lock the caller holds.
        :param interval: The seconds to leave after the previous request to *host* ended.
        :param allow: Statuses besides 2xx that are answers rather than failures.
        :param check: Tells why an answer about to be returned is a failure, or ``None``.
        :return: The answer.
        :raise RequestFailedError: When the answer has another status, or none came.
        """
        attempt = 0
        while True:
            attempt += 1
            await self._pace(host, interval)
            # The httpx exception never leaves this method: its message holds the full URL.
            try:
                response = await self._client.send(request)
            except httpx.HTTPError as error:
                status, reason = None, type(error).__name__
                wait = backoff_seconds(attempt) if isinstance(error, RETRYABLE_ERRORS) else None
            else:
                status, reason = response.status_code, f"HTTP {response.status_code}"
                _LOGGER.debug("%s %s -> %d", request.method, endpoint, status)
                if not (response.is_success or status in allow):
                    wait = retry_wait(response, attempt)
                elif (problem := None if check is None else check(response)) is None:
                    return response
                else:
                    reason = f"{reason}, {problem}"
                    wait = backoff_seconds(attempt)
            finally:
                self._last_ended[host] = self._clock()
            if wait is not None and wait > MAX_RETRY_AFTER_SECONDS:
                raise RequestFailedError(
                    request.method,
                    endpoint,
                    status=status,
                    reason=f"{reason}, Retry-After {wait:.0f} s",
                    attempts=attempt,
                    refused_wait=wait,
                )
            if wait is None or attempt > MAX_RETRIES:
                raise RequestFailedError(
                    request.method, endpoint, status=status, reason=reason, attempts=attempt
                )
            _LOGGER.warning(
                "%s %s: %s, retrying in %.0f s (%d of %d)",
                request.method,
                endpoint,
                reason,
                wait,
                attempt,
                MAX_RETRIES,
            )
            await self._sleep(wait)

    async def _pace(self, host: str, interval: float) -> None:
        """
        Wait until *interval* seconds have passed since the previous request to *host* ended.

        :param host: The host about to be asked.
        :param interval: The seconds to leave between that answer and this request.
        """
        if host in self._last_ended:
            wait = self._last_ended[host] + interval - self._clock()
            if wait > 0:
                await self._sleep(wait)


def backoff_seconds(attempt: int) -> float:
    """
    Tell how long to wait after failed attempt number *attempt* when the server says nothing.

    :param attempt: The attempt that failed, counting from 1.
    :return: 10 seconds, doubling with each attempt, at most 120.
    """
    return min(FIRST_BACKOFF_SECONDS * 2.0 ** (attempt - 1), MAX_BACKOFF_SECONDS)


def retry_after_seconds(value: str) -> float | None:
    """
    Read a ``Retry-After`` header: a number of seconds, or an HTTP date.

    :param value: The header's value.
    :return: The seconds to wait (0 for a date already past), or ``None`` when it is neither.
    """
    if value.isdecimal():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:  # A "-0000" zone: the date is in UTC, but parses without a zone.
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def retry_wait(response: httpx.Response, attempt: int) -> float | None:
    """
    Tell how long to wait before retrying after *response*, or that retrying is pointless.

    :param response: An answer that is neither a success nor allowed.
    :param attempt: The attempt that got it, counting from 1.
    :return: The seconds to wait, which the caller refuses when over
        :data:`MAX_RETRY_AFTER_SECONDS`, or ``None`` when the status isn't worth retrying.
    """
    if response.status_code != httpx.codes.TOO_MANY_REQUESTS and not response.is_server_error:
        return None
    header = response.headers.get("Retry-After")
    asked = None if header is None else retry_after_seconds(header)
    return backoff_seconds(attempt) if asked is None else asked


def make_client() -> httpx.AsyncClient:
    """
    Build the HTTP client the application uses: it names itself and never follows a redirect.

    :return: A client to pass to :class:`Transport`, and to close when done.
    """
    return httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={
            "User-Agent": f"steam-manager/{__version__} (+https://github.com/ivanlonel/steam-manager)"
        },
    )
