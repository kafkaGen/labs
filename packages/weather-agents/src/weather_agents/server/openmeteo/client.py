"""The only code that calls Open-Meteo. It knows HTTP and error shapes, nothing about MCP."""

from typing import Any, Literal

import httpx

FORECAST = "https://api.open-meteo.com/v1/forecast"
ELEVATION = "https://api.open-meteo.com/v1/elevation"
ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"
SEASONAL = "https://seasonal-api.open-meteo.com/v1/seasonal"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
CLIMATE = "https://climate-api.open-meteo.com/v1/climate"
MARINE = "https://marine-api.open-meteo.com/v1/marine"
AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
GEOCODING_SEARCH = "https://geocoding-api.open-meteo.com/v1/search"
GEOCODING_GET = "https://geocoding-api.open-meteo.com/v1/get"

Cause = Literal["rejected", "rate_limited", "server_error", "timeout", "unreachable"]


class OpenMeteoError(Exception):
    """Open-Meteo did not give a usable answer. `cause` says why, `detail` says more."""

    def __init__(self, cause: Cause, detail: str) -> None:
        super().__init__(f"{cause}: {detail}")
        self.cause = cause
        self.detail = detail


def _param(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return value


class OpenMeteoClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get(self, url: str, **params: Any) -> Any:
        """GET `url` and return the parsed JSON. Lists become comma-separated, None is dropped."""
        query = {key: _param(value) for key, value in params.items() if value is not None}
        try:
            response = await self._http.get(url, params=query)
        except httpx.TimeoutException as error:
            raise OpenMeteoError("timeout", "no answer within the time limit") from error
        except httpx.HTTPError as error:
            raise OpenMeteoError("unreachable", type(error).__name__) from error
        status = response.status_code
        if status == 429:
            raise OpenMeteoError("rate_limited", "too many requests, try again later")
        if status >= 500:
            raise OpenMeteoError("server_error", f"HTTP {status}")
        if status >= 400:
            raise OpenMeteoError("rejected", self._reason(response))
        return response.json()

    @staticmethod
    def _reason(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return f"HTTP {response.status_code}"
        return str(body.get("reason", f"HTTP {response.status_code}"))
