"""Final check: every tool, resource, and prompt, through a real server and the real Open-Meteo.

Run with `make test-live`. A tool, resource, or prompt added to the server without a case here
fails `test_every_registered_*_has_a_live_case`.
"""

import pytest
from mcp.types import ResourceTemplateReference, TextContent, TextResourceContents

from weather_agents.server.resources import ENDPOINT_TEMPLATE, ENDPOINTS

pytestmark = [pytest.mark.live, pytest.mark.anyio]

BERLIN = {"latitude": 52.52, "longitude": 13.41}
NORTH_SEA = {"latitude": 54.5, "longitude": 6.0}
RHINE_AT_COLOGNE = {"latitude": 50.94, "longitude": 6.96}

TOOL_CASES = {
    "geocode_search": {"name": "Berlin", "country_code": "DE"},
    "geocode_get": {"id": 2950159},
    "forecast": {**BERLIN, "days": 3},
    "ensemble": {**BERLIN, "days": 3},
    "seasonal": {**BERLIN, "months": 2},
    "historical": {**BERLIN, "start_date": "2024-01-01", "end_date": "2024-01-10"},
    "climate": {"places": [BERLIN], "start_year": 2030, "end_year": 2032},
    "marine": {**NORTH_SEA, "days": 2},
    "air_quality": {**BERLIN, "days": 2},
    "flood": {**RHINE_AT_COLOGNE, "days": 5},
    "elevation": {"points": [BERLIN]},
}

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


@pytest.mark.parametrize("tool", TOOL_CASES)
async def test_the_tool_answers_with_real_data(live_client, tool):
    result = await live_client.call_tool(tool, TOOL_CASES[tool])
    assert not result.is_error, result.content
    assert_has_data(result.structured_content)


async def test_every_registered_tool_has_a_live_case(live_client):
    registered = {tool.name for tool in (await live_client.list_tools()).tools}
    assert registered == set(TOOL_CASES)


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
