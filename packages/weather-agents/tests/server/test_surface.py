import pytest

pytestmark = pytest.mark.anyio

HORIZONS = {
    "geocode_search": "Place name to coordinates",
    "geocode_get": "Look up one place",
    "forecast": "from today out to 16 days",
    "ensemble": "within 15 days",
    "seasonal": "from 16 days to 7 months",
    "historical": "any period since 1940",
    "climate": "to 2049",
    "marine": "up to 7 days ahead",
    "air_quality": "up to 7 days ahead",
    "flood": "up to 92 days ahead",
    "elevation": "does not change over time",
}


async def test_the_server_exposes_the_eleven_endpoint_tools(client):
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == set(HORIZONS)


async def test_every_tool_states_its_horizon_and_has_an_output_schema(client):
    for tool in (await client.list_tools()).tools:
        assert HORIZONS[tool.name] in tool.description, tool.name
        assert tool.output_schema is not None, tool.name


async def test_the_server_exposes_two_prompts(client):
    prompts = (await client.list_prompts()).prompts
    assert {prompt.name for prompt in prompts} == {"weekend_check", "compare_places"}


async def test_the_server_exposes_the_guide_and_the_endpoint_template(client):
    resources = (await client.list_resources()).resources
    templates = (await client.list_resource_templates()).resource_templates
    assert [str(resource.uri) for resource in resources] == ["open-meteo://guide"]
    assert [template.uri_template for template in templates] == [
        "open-meteo://endpoints/{endpoint}"
    ]
