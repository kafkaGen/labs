import httpx
import pytest

from tests.fakes import iso_days, om_response
from weather_agents.server.openmeteo.client import FORECAST

pytestmark = pytest.mark.anyio

ARGS = {"latitude": 52.52, "longitude": 13.41, "days": 2}


def ok_forecast() -> dict:
    return om_response("daily", iso_days("2026-10-03", 2), {"temperature_2m_max": [1.0, 2.0]}, {})


async def test_an_open_meteo_rejection_names_the_cause_and_the_reason(client, fake):
    fake.route(FORECAST, {"error": True, "reason": "Latitude must be in range"}, status=400)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "rejected" in result.content[0].text
    assert "Latitude must be in range" in result.content[0].text


async def test_a_server_error_names_the_status(client, fake):
    fake.route(FORECAST, {}, status=503)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "server_error" in result.content[0].text
    assert "503" in result.content[0].text


async def test_a_timeout_is_an_error_result_naming_the_cause(client, fake):
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    fake.route_response(FORECAST, slow)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "timeout" in result.content[0].text


async def test_an_unreachable_open_meteo_is_an_error_result(client, fake):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    fake.route_response(FORECAST, down)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "unreachable" in result.content[0].text


async def test_the_server_keeps_serving_after_a_failed_call(client, fake):
    answers = iter([httpx.Response(500), httpx.Response(200, json=ok_forecast())])
    fake.route_response(FORECAST, lambda request: next(answers))
    first = await client.call_tool("forecast", ARGS)
    second = await client.call_tool("forecast", ARGS)
    assert first.is_error
    assert not second.is_error


async def test_an_out_of_range_latitude_names_the_argument_and_skips_open_meteo(client, fake):
    result = await client.call_tool("forecast", {**ARGS, "latitude": 95})
    assert result.is_error
    assert "latitude" in result.content[0].text
    assert fake.requests == []
