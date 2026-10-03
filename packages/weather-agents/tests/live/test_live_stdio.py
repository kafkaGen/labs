"""Spawns the real server and calls the real Open-Meteo. Run with `make test-live`."""

import sys

import pytest
from mcp import Client, StdioServerParameters

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_geocode_then_forecast_against_the_real_open_meteo():
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        geocoded = await client.call_tool(
            "geocode_search", {"name": "Berlin", "country_code": "DE"}
        )
        assert not geocoded.is_error
        place = geocoded.structured_content["results"][0]
        forecast = await client.call_tool(
            "forecast",
            {"latitude": place["latitude"], "longitude": place["longitude"], "days": 3},
        )
        assert not forecast.is_error
        assert len(forecast.structured_content["table"]["time"]) == 3
