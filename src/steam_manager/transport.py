"""Send the application's HTTP requests: paced per host, retried, and never showing a secret."""

import asyncio
import time
from typing import TYPE_CHECKING, Final

import httpx

from steam_manager import __version__

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Mapping

TIMEOUT_SECONDS: Final = 120.0
"""How long connecting, sending or reading may take before an attempt fails."""


class FetchError(Exception):
    """A request, or a run of them, failed. The message names the endpoint, never the full URL."""


class RequestFailedError(FetchError):
    """A request failed for good: an unexpected status, or a network error that didn't clear."""

    def __init__(
        self, method: str, endpoint: str, *, status: int | None, reason: str, attempts: int
    ) -> None:
        """
        Describe the failure without the query string, the headers or the answer's body.

        :param method: The HTTP method, such as ``GET``.
        :param endpoint: The URL without its query string, fragment or user info.
        :param status: The last answer's HTTP status, or ``None`` when no answer came.
        :param reason: ``HTTP <status>``, or the name of the network error's class.
        :param attempts: How many times the request was sent.
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
        self._client = client
        self._clock = clock
        self._sleep = sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_ended: dict[str, float] = {}

    async def get(
        self,
        url: str,
        *,
        interval: float,
        params: Mapping[str, str] | None = None,
        allow: Collection[int] = (),
    ) -> httpx.Response:
        """
        Send a GET request and return its answer.

        :param url: The URL, without its query string.
        :param interval: The seconds to leave after the previous request to the same host ended.
        :param params: The query string's parameters.
        :param allow: Statuses besides 2xx that are answers rather than failures, such as 404.
        :return: The answer.
        :raise RequestFailedError: When the answer has another status, or none came.
        """
        request = self._client.build_request("GET", url, params=params)
        endpoint = endpoint_of(request.url)
        host = request.url.host
        # One request in flight per host, so the interval separates one answer from the next
        # request, as the notebooks' pause after each call did.
        async with self._locks.setdefault(host, asyncio.Lock()):
            return await self._send(request, endpoint, host, interval=interval, allow=allow)

    async def _send(
        self,
        request: httpx.Request,
        endpoint: str,
        host: str,
        *,
        interval: float,
        allow: Collection[int],
    ) -> httpx.Response:
        """
        Send *request* once the host's interval has passed, holding the host's lock.

        :param request: The request to send.
        :param endpoint: The request's URL without its query string.
        :param host: The host whose lock the caller holds.
        :param interval: The seconds to leave after the previous request to *host* ended.
        :param allow: Statuses besides 2xx that are answers rather than failures.
        :return: The answer.
        :raise RequestFailedError: When the answer has another status, or none came.
        """
        if host in self._last_ended:
            wait = self._last_ended[host] + interval - self._clock()
            if wait > 0:
                await self._sleep(wait)
        try:
            response = await self._client.send(request)
        except httpx.HTTPError as error:
            # From None: the httpx exception's message holds the full URL.
            raise RequestFailedError(
                request.method, endpoint, status=None, reason=type(error).__name__, attempts=1
            ) from None
        finally:
            self._last_ended[host] = self._clock()
        if response.is_success or response.status_code in allow:
            return response
        raise RequestFailedError(
            request.method,
            endpoint,
            status=response.status_code,
            reason=f"HTTP {response.status_code}",
            attempts=1,
        )


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
