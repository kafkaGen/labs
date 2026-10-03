"""Builders for Open-Meteo-shaped responses, and a router that serves them to the server."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx


def iso_days(start: str, count: int) -> list[str]:
    first = date.fromisoformat(start)
    return [(first + timedelta(days=i)).isoformat() for i in range(count)]


def iso_hours(start: str, count: int) -> list[str]:
    return [f"{day}T{hour:02d}:00" for day in iso_days(start, count // 24) for hour in range(24)]


def om_response(
    block: str,
    times: list[str],
    columns: dict[str, list[Any]],
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """An Open-Meteo reply: grid-cell header, `<block>_units`, and `<block>`."""
    return {
        "latitude": 52.52,
        "longitude": 13.41,
        "generationtime_ms": 0.1,
        "utc_offset_seconds": 7200,
        "timezone": "Europe/Berlin",
        "timezone_abbreviation": "GMT+2",
        "elevation": 38.0,
        f"{block}_units": {"time": "iso8601", **(units or {})},
        block: {"time": times, **columns},
    }


def constant_daily(start: date, end: date, values: dict[str, float]) -> dict[str, Any]:
    """A daily reply with one constant value per column for every day from start to end."""
    times = iso_days(start.isoformat(), (end - start).days + 1)
    columns = {name: [value] * len(times) for name, value in values.items()}
    return om_response("daily", times, columns, {name: "u" for name in values})


PLACES = {
    "springfield_mo": {
        "id": 4409896,
        "name": "Springfield",
        "latitude": 37.21533,
        "longitude": -93.29824,
        "elevation": 396.0,
        "timezone": "America/Chicago",
        "country_code": "US",
        "country": "United States",
        "admin1": "Missouri",
        "population": 170188,
        "postcodes": ["65801"],
    },
    "springfield_il": {
        "id": 4250542,
        "name": "Springfield",
        "latitude": 39.80172,
        "longitude": -89.64371,
        "elevation": 182.0,
        "timezone": "America/Chicago",
        "country_code": "US",
        "country": "United States",
        "admin1": "Illinois",
        "population": 114394,
    },
    "berlin": {
        "id": 2950159,
        "name": "Berlin",
        "latitude": 52.52437,
        "longitude": 13.41053,
        "elevation": 74.0,
        "timezone": "Europe/Berlin",
        "country_code": "DE",
        "country": "Germany",
        "admin1": "State of Berlin",
        "population": 3426354,
    },
}


class FakeOpenMeteo:
    """An httpx handler that answers by URL (scheme, host, path) and records every request."""

    def __init__(self) -> None:
        self._routes: dict[str, Callable[[httpx.Request], httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def route(self, url: str, payload: Any = None, *, status: int = 200) -> None:
        self._routes[url] = lambda _request: httpx.Response(status, json=payload)

    def route_with(self, url: str, handler: Callable[[httpx.Request], Any]) -> None:
        """Answer with `handler(request)`, a JSON-serialisable payload."""
        self._routes[url] = lambda request: httpx.Response(200, json=handler(request))

    def route_response(self, url: str, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self._routes[url] = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = f"{request.url.scheme}://{request.url.host}{request.url.path}"
        handler = self._routes.get(url)
        if handler is None:
            raise AssertionError(f"Unrouted request: {request.url}")
        return handler(request)

    def params(self, index: int = -1) -> dict[str, str]:
        return dict(self.requests[index].url.params)
