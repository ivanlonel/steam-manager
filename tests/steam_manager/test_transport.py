"""Tests for the HTTP transport: pacing, retries, failures in a row and redaction."""

import asyncio
lazy from collections.abc import Callable

import httpx
import pytest

from steam_manager.transport import RequestFailedError, Transport, make_client

URL = "https://api.steampowered.com/IStoreQueryService/Query/v1/"
"""An endpoint on Steam's Web API host."""
STORE_URL = "https://store.steampowered.com/appreviewhistogram/620"
"""An endpoint on the store's host."""


class FakeClock:
    """A monotonic clock that only moves when the transport sleeps or a handler says so."""

    def __init__(self) -> None:
        """Start at time 0 with no sleeps recorded."""
        self.now: float = 0.0
        """The current time, in seconds."""
        self.sleeps: list[float] = []
        """Every duration the transport slept for, in order."""

    def __call__(self) -> float:
        """
        Tell the current time.

        :return: The current time, in seconds.
        """
        return self.now

    async def sleep(self, seconds: float) -> None:
        """
        Record a sleep and move the clock forward by it.

        :param seconds: How long the transport asked to sleep.
        """
        self.sleeps.append(seconds)
        self.now += seconds


def transport_for(
    handler: Callable[[httpx.Request], httpx.Response], clock: FakeClock
) -> Transport:
    """
    Build a transport whose answers come from *handler* and whose time comes from *clock*.

    :param handler: Answers each request the transport sends.
    :param clock: The clock and sleep the transport uses.
    :return: A transport that never touches the network.
    """
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Transport(client, clock=clock, sleep=clock.sleep)


def answer(status: int) -> Callable[[httpx.Request], httpx.Response]:
    """
    Make a handler that always answers with *status*.

    :param status: The HTTP status of every answer.
    :return: The handler.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"response": {}})

    return handler


def test_get_returns_a_successful_answer() -> None:
    """A 2xx answer comes back as it is."""
    transport = transport_for(answer(200), FakeClock())

    response = asyncio.run(transport.get(URL, interval=0.2))

    assert response.status_code == 200


def test_get_sends_the_params() -> None:
    """The parameters go into the request's query string."""
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200)

    transport = transport_for(handler, FakeClock())

    asyncio.run(transport.get(URL, interval=0.2, params={"input_json": "{}"}))

    assert seen == [{"input_json": "{}"}]


def test_an_allowed_status_is_returned() -> None:
    """A status the caller allows, such as 404 for "no figure", is an answer, not a failure."""
    transport = transport_for(answer(404), FakeClock())

    response = asyncio.run(transport.get(URL, interval=0.2, allow={404}))

    assert response.status_code == 404


def test_an_unexpected_status_fails_without_retrying() -> None:
    """A 4xx the caller didn't allow fails at once, naming the endpoint and the status."""
    transport = transport_for(answer(400), FakeClock())

    with pytest.raises(RequestFailedError) as caught:
        asyncio.run(transport.get(URL, interval=0.2))

    assert caught.value.status == 400
    assert caught.value.attempts == 1
    assert str(caught.value) == f"GET {URL} failed: HTTP 400 after 1 attempt"


def recording(
    clock: FakeClock, *, takes: float = 0.0, status: int = 200
) -> tuple[Callable[[httpx.Request], httpx.Response], list[float], list[str]]:
    """
    Make a handler that records when each request arrived and which ``id`` parameter it had.

    :param clock: The clock the arrival times are read from.
    :param takes: How long each answer takes, in seconds of *clock*.
    :param status: The HTTP status of every answer.
    :return: The handler, the arrival times and the ``id`` parameters, in arrival order.
    """
    arrivals: list[float] = []
    ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        arrivals.append(clock.now)
        ids.append(request.url.params.get("id", ""))
        clock.now += takes
        return httpx.Response(status)

    return handler, arrivals, ids


def test_the_first_request_to_a_host_does_not_wait() -> None:
    """Nothing came before the first request to a host, so it goes out at once."""
    clock = FakeClock()
    transport = transport_for(answer(200), clock)

    asyncio.run(transport.get(URL, interval=0.2))

    assert not clock.sleeps


def test_a_second_request_waits_the_interval_after_the_first_ended() -> None:
    """The interval runs from when the previous answer arrived, not from when it was asked."""
    clock = FakeClock()
    handler, arrivals, _ = recording(clock, takes=0.5)
    transport = transport_for(handler, clock)

    async def two() -> None:
        await transport.get(URL, interval=0.2)
        await transport.get(URL, interval=0.2)

    asyncio.run(two())

    assert arrivals == pytest.approx([0.0, 0.7])


def test_each_call_uses_its_own_interval() -> None:
    """Two endpoints on one host keep their own pacing, as the histogram and appdetails do."""
    clock = FakeClock()
    handler, arrivals, _ = recording(clock)
    transport = transport_for(handler, clock)

    async def two() -> None:
        await transport.get(STORE_URL, interval=1.5)
        await transport.get(STORE_URL, interval=1.0)

    asyncio.run(two())

    assert arrivals == pytest.approx([0.0, 1.0])


def test_different_hosts_do_not_wait_for_each_other() -> None:
    """Pacing is per host: a request to the store doesn't wait for one to the Web API."""
    clock = FakeClock()
    transport = transport_for(answer(200), clock)

    async def two() -> None:
        await transport.get(URL, interval=10)
        await transport.get(STORE_URL, interval=10)

    asyncio.run(two())

    assert not clock.sleeps


def test_concurrent_calls_to_one_host_run_one_at_a_time_in_call_order() -> None:
    """Calls made at once to one host go out one by one, paced, in the order they were made."""
    clock = FakeClock()
    handler, arrivals, ids = recording(clock, takes=0.5)
    transport = transport_for(handler, clock)

    async def three() -> None:
        await asyncio.gather(
            *(transport.get(URL, interval=0.2, params={"id": str(n)}) for n in (1, 2, 3))
        )

    asyncio.run(three())

    assert ids == ["1", "2", "3"]
    assert arrivals == pytest.approx([0.0, 0.7, 1.4])


def test_a_redirect_is_a_failure_and_is_not_followed() -> None:
    """A retired endpoint's redirect fails instead of fetching the page it points to."""
    calls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(302, headers={"Location": "https://store.steampowered.com/"})

    transport = transport_for(handler, FakeClock())

    with pytest.raises(RequestFailedError) as caught:
        asyncio.run(transport.get(URL, interval=0))

    assert caught.value.status == 302
    assert len(calls) == 1


def test_make_client_identifies_the_application() -> None:
    """The real client names the application, waits two minutes at most, and never redirects."""
    client = make_client()

    assert client.headers["User-Agent"].startswith("steam-manager/")
    assert client.timeout.read == 120.0
    assert client.follow_redirects is False
    asyncio.run(client.aclose())
