"""
Record the Steam answers in tests/fixtures/steam/: public store data only, never account data.

Run it by hand, on the network: ``uv run python scripts/record_steam_fixtures.py``. It writes
each answer as indented JSON, then prints which case each store item covers, so an app that no
longer shows its case can be swapped. The wishlist and followed-apps fixtures are written by
hand instead: they would hold an account's data.
"""

import asyncio
import contextlib
import json
import sys
from pathlib import Path
from typing import Final

from steam_manager.steam.reviews import app_reviews, review_histogram
from steam_manager.steam.store import (
    app_genres,
    current_players,
    get_items,
    list_apps,
    store_categories,
    tag_list,
)
from steam_manager.transport import Transport, make_client

FIXTURES: Final = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "steam"
"""Where the fixtures go."""
STORE_ITEMS: Final[dict[int, str]] = {
    620: "Portal 2: a paid game with packages, bundles, trailers and requirements",
    570: "Dota 2: a free game",
    2778580: "Elden Ring: Shadow of the Erdtree: a DLC",
    108600: "Project Zomboid: an Early Access game",
    546560: "Half-Life: Alyx: VR only",
    1778820: "Tekken 8: a season pass",
    1172470: "Apex Legends: anticheat details",
    2073850: "The Finals: generative AI declared",
    12170: "Grand Theft Auto (1997): delisted, sold by neither store",
}
"""The apps recorded from the BR store, with the case each stands for."""


def save(name: str, body: str) -> None:
    """
    Write an answer's JSON, indented, under :data:`FIXTURES`.

    :param name: The path below :data:`FIXTURES`, such as ``store_item/620-BR.json``.
    :param body: The answer's JSON text.
    """
    path = FIXTURES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
    path.write_text(f"{text}\n", encoding="utf-8", newline="\n")


def without_reviews(body: str) -> str:
    """
    Empty the review list of a ``GetAppReviews`` answer, keeping its totals.

    :param body: The answer's JSON text.
    :return: The same answer without the review, whose author is another account.
    """
    answer = json.loads(body)
    answer["response"]["reviews"] = []
    return json.dumps(answer)


def cases(item: dict[str, object]) -> list[str]:
    """
    Name the cases a store item shows, so a fixture that stopped showing its case is noticed.

    :param item: A store item.
    :return: The cases, such as ``early access`` or ``success 15``.
    """
    extra = item.get("extra_details")
    details = extra if isinstance(extra, dict) else {}
    platforms = item.get("platforms")
    included = item.get("included_items")
    shown = {
        f"type {item.get('type')}": True,
        f"success {item.get('success')}": item.get("success") != 1,
        "free": bool(item.get("is_free")),
        "early access": bool(item.get("is_early_access")),
        "vr": isinstance(platforms, dict) and "vr_support" in platforms,
        "season pass": "season_pass" in details,
        "anticheat": "anticheat" in details,
        "generative AI": "ai_generation_service" in details,
        "bundles": isinstance(included, dict) and bool(included.get("included_bundles")),
    }
    return [name for name, present in shown.items() if present]


async def record(appids: list[int]) -> None:
    """
    Record every fixture.

    :param appids: The store items to record from the BR store.
    """
    async with make_client() as client:
        transport = Transport(client)
        async for answer in get_items(transport, appids, country="BR"):
            save(f"store_item/{answer.key}-BR.json", answer.body)
            print(answer.key, ", ".join(cases(json.loads(answer.body))))
        async for answer in get_items(transport, [620], country="US"):
            save("store_item/620-US.json", answer.body)
        async with contextlib.aclosing(list_apps(transport, country="BR")) as listing:
            light = await anext(listing)  # the first app of the first page is enough
        save(f"store_item_light/{light.key}-BR.json", light.body)
        save("store_categories.json", (await store_categories(transport)).body)
        save("tags.json", (await tag_list(transport)).body)
        save("app_genres-620.json", (await app_genres(transport, 620)).body)
        reviews = await app_reviews(transport, 620, purchase_type=0)
        save("app_reviews-620-0.json", without_reviews(reviews.body))
        save("review_histogram-620.json", (await review_histogram(transport, 620)).body)
        save("current_players-570.json", (await current_players(transport, 570)).body)


if __name__ == "__main__":
    asyncio.run(record([int(arg) for arg in sys.argv[1:]] or list(STORE_ITEMS)))
