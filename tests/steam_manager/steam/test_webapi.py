"""Tests for Steam's Web API call and the answers built from what it returns."""

import asyncio
import json
from datetime import UTC

import httpx
import pytest

from steam_manager.answers import Kind
from steam_manager.steam.webapi import call, has_response, item_answer, response_answer
from tests._fakes import FakeClock, answers, transport_for


def test_item_answer_keeps_the_item_compact_and_unchanged() -> None:
    """An item's share of a batched answer keeps its content; only the whitespace goes."""
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


def test_item_answer_keeps_non_ascii_text_as_it_is() -> None:
    """Names in other scripts stay readable in the archive, not escaped."""
    answer = item_answer(Kind.STORE_ITEM, {"name": "ポータル2"}, key="620", country="JP")

    assert answer.body == '{"name":"ポータル2"}'


def test_response_answer_keeps_the_body_verbatim() -> None:
    """A whole answer is archived byte for byte as text, whitespace included."""
    response = httpx.Response(200, text='{"response": {"tags": []}}')

    answer = response_answer(Kind.TAGS, response, key="english")

    assert answer.body == '{"response": {"tags": []}}'
    assert answer.country == ""


def test_call_sends_input_json_to_the_versioned_method() -> None:
    """A Web API method is asked at /<interface>/<method>/v1/ with its input as compact JSON."""
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"response": {}})

    transport = transport_for(handler, FakeClock())

    asyncio.run(
        call(
            transport,
            "IStoreQueryService",
            "Query",
            interval=0,
            input_json={"query": {"start": 0}},
        )
    )

    assert seen[0].host == "api.steampowered.com"
    assert seen[0].path == "/IStoreQueryService/Query/v1/"
    assert seen[0].params["input_json"] == '{"query":{"start":0}}'


def test_call_sends_plain_params_without_input_json() -> None:
    """Methods that take plain parameters get them as they are."""
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"response": {}})

    transport = transport_for(handler, FakeClock())

    asyncio.run(
        call(transport, "IStoreService", "GetTagList", interval=0, params={"language": "english"})
    )

    assert dict(seen[0].params) == {"language": "english"}


def test_an_answer_without_a_response_object_is_retried() -> None:
    """Steam's error pages come back as 200 HTML; they are retried like a server error."""
    clock = FakeClock()
    steps = [httpx.Response(200, text="<html>"), httpx.Response(200, json={"response": {}})]
    transport = transport_for(answers(steps), clock)

    asyncio.run(call(transport, "IStoreService", "GetTagList", interval=0))

    assert clock.sleeps == [10.0]


def test_a_caller_check_runs_after_the_response_check() -> None:
    """A caller's own check sees only answers that have a response object."""
    clock = FakeClock()
    steps = [
        httpx.Response(200, json={"response": {}}),
        httpx.Response(200, json={"response": {"tags": []}}),
    ]
    transport = transport_for(answers(steps), clock)

    def has_tags(response: httpx.Response) -> str | None:
        return None if "tags" in response.json()["response"] else "no tags"

    response = asyncio.run(
        call(transport, "IStoreService", "GetTagList", interval=0, check=has_tags)
    )

    assert response.json() == {"response": {"tags": []}}
    assert clock.sleeps == [10.0]


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ('{"response": {}}', None),
        ("<html>", "not JSON"),
        ('{"other": {}}', "no response object"),
        ('{"response": []}', "no response object"),
        ("[]", "no response object"),
    ],
)
def test_has_response(body: str, problem: str | None) -> None:
    """A Web API answer must be JSON holding a ``response`` object."""
    assert has_response(httpx.Response(200, text=body)) == problem
