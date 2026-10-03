"""Final check: every tool, resource, and prompt, through a real server and the real Open-Meteo.

Run with `make test-live`. Each test runs once per transport in `TRANSPORTS` (see conftest.py),
so the test id names the transport, such as `test_the_guide_is_served[stdio]`. A tool or prompt
added to the server without a case here fails the `test_every_registered_*_has_a_live_case` tests.
"""

import pytest
from mcp.types import ResourceTemplateReference, TextContent, TextResourceContents

from weather_agents.server.resources import ENDPOINT_TEMPLATE, ENDPOINTS

pytestmark = [pytest.mark.live, pytest.mark.anyio]

BERLIN = {"latitude": 52.52, "longitude": 13.41}
NORTH_SEA = {"latitude": 54.5, "longitude": 6.0}
RHINE_AT_COLOGNE = {"latitude": 50.94, "longitude": 6.96}

# (tool, arguments, id). A tool may appear more than once, for each branch of its summary.
TOOL_CASES = [
    ("geocode_search", {"name": "Berlin", "country_code": "DE"}, "geocode_search"),
    ("geocode_get", {"id": 2950159}, "geocode_get"),
    ("forecast", {**BERLIN, "days": 3}, "forecast"),
    ("ensemble", {**BERLIN, "days": 3}, "ensemble"),
    ("seasonal", {**BERLIN, "months": 2}, "seasonal"),
    ("seasonal", {**BERLIN, "months": 7}, "seasonal_seven_months"),
    (
        "historical",
        {**BERLIN, "start_date": "2024-01-01", "end_date": "2024-01-10"},
        "historical_daily",
    ),
    (
        "historical",
        {**BERLIN, "start_date": "2023-01-01", "end_date": "2024-06-30"},
        "historical_monthly",
    ),
    (
        "historical",
        {**BERLIN, "start_date": "1991-01-01", "end_date": "2020-12-31"},
        "historical_normals",
    ),
    ("climate", {"places": [BERLIN], "start_year": 2030, "end_year": 2032}, "climate"),
    (
        "climate",
        {"places": [BERLIN, NORTH_SEA], "start_year": 2030, "end_year": 2031},
        "climate_two_places",
    ),
    ("marine", {**NORTH_SEA, "days": 2}, "marine"),
    ("air_quality", {**BERLIN, "days": 2}, "air_quality"),
    ("flood", {**RHINE_AT_COLOGNE, "days": 5}, "flood"),
    ("elevation", {"points": [BERLIN]}, "elevation"),
]

PROMPT_CASES = {
    "weekend_check": {},
    "compare_places": {"places": "Lisbon, Oslo", "month": "July"},
}


def assert_has_data(data: dict) -> None:
    """Each tool answers with real values: a table, a list of tables, places, or points."""
    if "table" in data:
        table = data["table"]
        assert table["time"], "no rows"
        assert any(v is not None for values in table["columns"].values() for v in values)
    elif "places" in data:
        for place in data["places"]:
            assert_has_data(place)
    elif "results" in data:
        assert data["results"], "no places found"
    elif "points" in data:
        assert all(point["elevation"] is not None for point in data["points"])
    else:
        assert data["name"] == "Berlin"


@pytest.mark.parametrize(
    ("tool", "arguments"), [case[:2] for case in TOOL_CASES], ids=[case[2] for case in TOOL_CASES]
)
async def test_the_tool_answers_with_real_data(live_client, tool, arguments):
    result = await live_client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    assert_has_data(result.structured_content)


async def test_every_registered_tool_has_a_live_case(live_client):
    registered = {tool.name for tool in (await live_client.list_tools()).tools}
    assert registered == {tool for tool, _, _ in TOOL_CASES}


async def test_the_guide_is_served(live_client):
    result = await live_client.read_resource("open-meteo://guide")
    part = result.contents[0]
    assert isinstance(part, TextResourceContents)
    assert part.text.startswith("# Open-Meteo guide")


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_the_endpoint_guide_is_served(live_client, endpoint):
    result = await live_client.read_resource(f"open-meteo://endpoints/{endpoint}")
    part = result.contents[0]
    assert isinstance(part, TextResourceContents)
    assert part.text.startswith("# ")


async def test_the_endpoint_name_completes(live_client):
    result = await live_client.complete(
        ref=ResourceTemplateReference(uri=ENDPOINT_TEMPLATE),
        argument={"name": "endpoint", "value": "air"},
    )
    assert result.completion.values == ["air-quality"]


@pytest.mark.parametrize("prompt", PROMPT_CASES)
async def test_the_prompt_renders(live_client, prompt):
    result = await live_client.get_prompt(prompt, PROMPT_CASES[prompt])
    part = result.messages[0].content
    assert isinstance(part, TextContent)
    assert part.text.strip()


async def test_every_registered_prompt_has_a_live_case(live_client):
    registered = {prompt.name for prompt in (await live_client.list_prompts()).prompts}
    assert registered == set(PROMPT_CASES)
