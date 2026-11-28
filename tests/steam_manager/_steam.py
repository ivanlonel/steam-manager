"""A fake Steam for the sync's tests: recorded answers, and made-up ones, routed by path."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import httpx

from tests._fakes import FakeClock, transport_for

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from steam_manager.transport import Transport

FIXTURES: Final = Path(__file__).parents[1] / "fixtures" / "steam"
"""The recorded Steam answers."""

type Item = dict[str, object]
"""A store item, as ``GetItems`` or ``Query`` sends it."""


def recorded(name: str) -> Any | None:  # noqa: ANN401  # JSON of any shape
    """
    Read a recorded answer, when there is one.

    :param name: Its path under the fixtures, such as ``store_item/620-BR.json``.
    :return: Its JSON, or ``None`` when nothing was recorded under that name.
    """
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def not_sold(appid: int) -> Item:
    """
    Make the answer a store gives for an app it doesn't sell, as 12170's recorded one is.

    :param appid: The app.
    :return: The item, with ``success`` 15.
    """
    return {
        "item_type": 0,
        "id": appid,
        "success": 15,
        "visible": False,
        "name": "",
        "store_url_path": "app/0/",
        "store_url_slug": "",
        "appid": 0,
    }


def sold(appid: int, **fields: object) -> Item:
    r"""
    Make a short store item for an app a store sells.

    :param appid: The app.
    :param \*\*fields: Fields to add or replace, such as ``reviews``.
    :return: The item.
    """
    return {
        "item_type": 0,
        "id": appid,
        "success": 1,
        "visible": True,
        "name": f"App {appid}",
        "appid": appid,
        "type": 0,
    } | fields


# One attribute per endpoint it shapes, and the requests it was sent.
class FakeSteam:  # pylint: disable=too-many-instance-attributes
    """Answers every endpoint the sync asks, and keeps what it was asked."""

    def __init__(  # each argument shapes one endpoint's answers
        self,
        *,
        wishlist: Sequence[int] | None = None,
        followed: Sequence[int] | None = None,
        listings: Mapping[str, Sequence[int]] | None = None,
        totals: Mapping[str, int] | None = None,
        items: Mapping[tuple[int, str], Item] | None = None,
        reviews: Mapping[int, tuple[int, int]] | None = None,
        fail: Callable[[httpx.Request], int | None] | None = None,
    ) -> None:
        """
        Shape the answers.

        :param wishlist: The wishlist's apps in order; the recorded wishlist when ``None``.
        :param followed: The followed apps; the recorded ones when ``None``.
        :param listings: The apps each country lists.
        :param totals: The total a country's listing reports, when not its length.
        :param items: Full entries by app and country, before the recorded ones; an app with
            neither isn't sold there.
        :param reviews: Each app's exact positive and negative totals; zero when missing.
        :param fail: Gives a status to answer a request with instead, or ``None``.
        """
        self.wishlist = wishlist
        """The wishlist's apps in order; the recorded wishlist when ``None``."""
        self.followed = followed
        """The followed apps; the recorded ones when ``None``."""
        self.listings: dict[str, Sequence[int]] = dict(listings or {})
        """The apps each country lists."""
        self.totals: dict[str, int] = dict(totals or {})
        """The total a country's listing reports, when not its length."""
        self.items: dict[tuple[int, str], Item] = dict(items or {})
        """Full entries by app and country, before the recorded ones."""
        self.reviews: dict[int, tuple[int, int]] = dict(reviews or {})
        """Each app's exact positive and negative totals."""
        self.fail: Callable[[httpx.Request], int | None] = fail or (lambda _request: None)
        """Gives a status to answer a request with instead, or ``None``."""
        self.asked: list[tuple[str, dict[str, Any]]] = []
        """Each request's path and parameters, ``input_json`` decoded, in order."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """
        Answer a request, unless :attr:`fail` gives a status for it.

        :param request: The request.
        :return: The answer.
        """
        params: dict[str, Any] = dict(request.url.params)
        if "input_json" in params:
            params["input_json"] = json.loads(params["input_json"])
        path = request.url.path
        self.asked.append((path, params))
        if (status := self.fail(request)) is not None:
            return httpx.Response(status, json={"response": {}})
        return httpx.Response(200, json=self._answer(path, params))

    def methods(self) -> list[str]:
        """
        Name each request's method or page, such as ``GetItems`` or ``appdetails``, in order.

        :return: The names.
        """
        parts = [path.strip("/").split("/") for path, _ in self.asked]
        return [part[0] if part[0] == "appreviewhistogram" else part[1] for part in parts]

    def items_asked(self, country: str) -> list[int]:
        """
        List the apps whose full entries were asked in one country, in order.

        :param country: The country.
        :return: The appids, a batch after another.
        """
        return [
            entry["appid"]
            for path, params in self.asked
            if path.endswith("/GetItems/v1/")
            and params["input_json"]["context"]["country_code"] == country
            for entry in params["input_json"]["ids"]
        ]

    def _answer(self, path: str, params: Mapping[str, Any]) -> object:
        """
        Make the answer of one endpoint.

        :param path: The request's path.
        :param params: Its parameters.
        :return: The answer's JSON.
        """
        if path.startswith("/appreviewhistogram/"):
            return self._histogram(int(path.rsplit("/", 1)[1]))
        routes: dict[str, Callable[[], object]] = {
            "/IStoreBrowseService/GetStoreCategories/v1/": lambda: recorded(
                "store_categories.json"
            ),
            "/IStoreService/GetTagList/v1/": lambda: recorded("tags.json"),
            "/IWishlistService/GetWishlist/v1/": self._wishlist,
            "/IStoreService/GetGamesFollowed/v1/": self._followed,
            "/IStoreBrowseService/GetItems/v1/": lambda: self._items(params["input_json"]),
            "/IStoreQueryService/Query/v1/": lambda: self._page(params["input_json"]),
            "/api/appdetails": lambda: self._genres(params["appids"]),
            "/IUserReviewsService/GetAppReviews/v1/": lambda: self._reviews(params["input_json"]),
            "/ISteamUserStats/GetNumberOfCurrentPlayers/v1/": lambda: {
                "response": {"player_count": 7, "result": 1}
            },
        }
        return routes[path]()

    def _wishlist(self) -> object:
        """
        Make the wishlist's answer.

        :return: The recorded wishlist, or one of :attr:`wishlist`'s apps in order.
        """
        if self.wishlist is None:
            return recorded("wishlist.json")
        items = [
            {"appid": appid, "priority": place, "date_added": 1700000000}
            for place, appid in enumerate(self.wishlist, start=1)
        ]
        return {"response": {"items": items}}

    def _followed(self) -> object:
        """
        Make the followed apps' answer.

        :return: The recorded one, or one of :attr:`followed`'s apps.
        """
        if self.followed is None:
            return recorded("followed_apps.json")
        return {"response": {"appids": list(self.followed)}}

    @staticmethod
    def _genres(appid: str) -> object:
        """
        Make an ``appdetails`` answer for genres.

        :param appid: The app asked.
        :return: The recorded one, or one with no genre.
        """
        empty = {appid: {"success": True, "data": {"genres": []}}}
        return recorded(f"app_genres-{appid}.json") or empty

    def _items(self, asked: Mapping[str, Any]) -> object:
        """
        Make a ``GetItems`` answer.

        :param asked: The request's ``input_json``.
        :return: Each app's full entry in the country asked.
        """
        country = asked["context"]["country_code"]
        found = []
        for entry in asked["ids"]:
            appid = entry["appid"]
            item = self.items.get((appid, country)) or recorded(
                f"store_item/{appid}-{country}.json"
            )
            found.append(item or not_sold(appid))
        return {"response": {"store_items": found}}

    def _page(self, asked: Mapping[str, Any]) -> object:
        """
        Make one ``Query`` page from :attr:`listings`.

        :param asked: The request's ``input_json``.
        :return: The page.
        """
        country = asked["context"]["country_code"]
        start, count = asked["query"]["start"], asked["query"]["count"]
        listed = self.listings.get(country, [])
        ids = listed[start : start + count]
        total = self.totals.get(country, len(listed))
        metadata = {"total_matching_records": total, "start": start, "count": len(ids)}
        found = {
            "metadata": metadata,
            "ids": [{"appid": appid} for appid in ids],
            "store_items": [sold(appid) for appid in ids],
        }
        return {"response": found}

    def _reviews(self, asked: Mapping[str, Any]) -> object:
        """
        Make a ``GetAppReviews`` answer.

        :param asked: The request's ``input_json``.
        :return: The app's totals from :attr:`reviews`, else the recorded ones, else zero.
        """
        appid, kind = asked["appid"], asked["purchase_type"]
        if appid not in self.reviews and (found := recorded(f"app_reviews-{appid}-{kind}.json")):
            return found
        positive, negative = self.reviews.get(appid, (0, 0))
        summary = {
            "num_reviews": 1,
            "total_positive": positive,
            "total_negative": negative,
            "total_reviews": positive + negative,
        }
        return {"response": {"query_summary": summary, "reviews": []}}

    @staticmethod
    def _histogram(appid: int) -> object:
        """
        Make a review histogram.

        :param appid: The app.
        :return: The recorded one, or an empty one.
        """
        results = {
            "start_date": 1700000000,
            "end_date": 1700000000,
            "weeks": [],
            "rollups": [],
            "rollup_type": "month",
            "recent": [],
        }
        return recorded(f"review_histogram-{appid}.json") or {"success": 1, "results": results}


def fake_transport(steam: FakeSteam) -> Transport:
    """
    Build a transport whose answers come from *steam*, and whose waits take no time.

    :param steam: The fake Steam.
    :return: The transport.
    """
    return transport_for(steam, FakeClock())
