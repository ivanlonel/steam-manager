"""Stand-ins for the network and the clock, shared by every test that sends requests."""

lazy from collections.abc import Callable, Sequence

import httpx

from steam_manager.transport import Transport


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


type Step = int | httpx.Response | type[httpx.RequestError]
"""One answer of :func:`answers`: a status, a whole response, or a network error to raise."""


def answers(steps: Sequence[Step]) -> Callable[[httpx.Request], httpx.Response]:
    """
    Make a handler that answers each request with the next step, repeating the last one.

    :param steps: The answers, in order.
    :return: The handler.
    """
    remaining = list(steps)

    def handler(request: httpx.Request) -> httpx.Response:
        step = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        if isinstance(step, httpx.Response):
            return step
        if isinstance(step, int):
            return httpx.Response(step)
        message = "a simulated network error"
        raise step(message, request=request)

    return handler
