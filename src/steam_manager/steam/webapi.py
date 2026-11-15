"""Call Steam's Web API, and turn what Steam returns into answers for the raw archive."""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from steam_manager.answers import Answer, Kind

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    import httpx

    from steam_manager.transport import Transport

WEB_API: Final = "https://api.steampowered.com"
"""The host of Steam's Web API."""
STEAM: Final = "steam"
"""The source name of every answer Steam gives."""


def item_answer(kind: Kind, item: Mapping[str, object], *, key: str, country: str) -> Answer:
    """
    Make an answer from one item of a batched answer, such as one app of a ``GetItems`` batch.

    :param kind: What the item is.
    :param item: The item, as Steam sent it.
    :param key: What the item is about, such as its appid.
    :param country: The store country it was asked in, or ``""``.
    :return: The answer, with the item as compact JSON.
    """
    body = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    return Answer(STEAM, kind, key, country, body, datetime.now(UTC))


def response_answer(
    kind: Kind, response: httpx.Response, *, key: str, country: str = ""
) -> Answer:
    """
    Make an answer from a whole response, keeping its text as it came.

    :param kind: What the response is about.
    :param response: The response.
    :param key: What it is about within its kind.
    :param country: The store country it was asked in, or ``""``.
    :return: The answer.
    """
    return Answer(STEAM, kind, key, country, response.text, datetime.now(UTC))


def has_response(response: httpx.Response) -> str | None:
    """
    Tell whether a Web API answer is JSON holding a ``response`` object.

    :param response: The answer.
    :return: ``None`` when it does, else what is wrong with it.
    """
    try:
        body = response.json()
    except ValueError:
        return "not JSON"
    if isinstance(body, dict) and isinstance(body.get("response"), dict):
        return None
    return "no response object"


async def call(
    transport: Transport,
    interface: str,
    method: str,
    *,
    interval: float,
    input_json: Mapping[str, object] | None = None,
    params: Mapping[str, str] | None = None,
    allow: Collection[int] = (),
    check: Callable[[httpx.Response], str | None] | None = None,
) -> httpx.Response:
    """
    Ask a Web API method, retrying any answer that isn't a JSON ``response`` object.

    :param transport: Sends the request.
    :param interface: The interface, such as ``IStoreBrowseService``.
    :param method: The method, such as ``GetItems``.
    :param interval: The seconds to leave after the previous request to the host ended.
    :param input_json: The method's input, sent as the ``input_json`` parameter.
    :param params: Plain parameters, for methods that take them.
    :param allow: Statuses besides 2xx that are answers rather than failures.
    :param check: Rejects an answer that has a response object but not what was asked for.
    :return: The answer.
    """
    query = dict(params or {})
    if input_json is not None:
        query["input_json"] = json.dumps(input_json, separators=(",", ":"))

    def checked(response: httpx.Response) -> str | None:
        return has_response(response) or (None if check is None else check(response))

    return await transport.get(
        f"{WEB_API}/{interface}/{method}/v1/",
        interval=interval,
        params=query,
        allow=allow,
        check=checked,
    )
