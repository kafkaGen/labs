import pytest
from mcp.types import CallToolResult, ImageContent, TextContent, Tool

from tests.client.fakes import FakeClient, FakeFactory
from weather_agents.mcp_client import McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.runtimes.mcp_tools import McpToolProvider

pytestmark = pytest.mark.anyio

SCHEMA = {"type": "object", "properties": {"latitude": {"type": "number", "maximum": 90}}}


def pool_with(client: FakeClient) -> McpClientPool:
    return McpClientPool(
        {"open-meteo": StdioServerConfig(command="fake")},
        client_factory=FakeFactory({"fake": client}),
    )


async def test_tools_keep_their_schema_and_description_under_the_prefixed_name():
    client = FakeClient(tools=[Tool(name="forecast", description="Forecast.", input_schema=SCHEMA)])

    async with pool_with(client) as pool:
        specs = await McpToolProvider(pool).list_tools()

    assert [(spec.name, spec.description, spec.input_schema) for spec in specs] == [
        ("open-meteo__forecast", "Forecast.", SCHEMA)
    ]


async def test_a_call_reaches_the_server_by_its_unprefixed_name():
    client = FakeClient()

    async with pool_with(client) as pool:
        await McpToolProvider(pool).call("open-meteo__forecast", {"latitude": 49.8})

    assert client.calls[-1] == ("call_tool", ("forecast", {"latitude": 49.8}))


async def test_structured_content_wins_over_text():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="rendered")],
        structured_content={"temperature": 12, "place": "Львів"},
    )

    async with pool_with(client) as pool:
        outcome = await McpToolProvider(pool).call("open-meteo__forecast", {})

    assert outcome.text == '{"temperature": 12, "place": "Львів"}'
    assert outcome.is_error is False


async def test_text_blocks_are_joined_and_other_blocks_skipped():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[
            TextContent(type="text", text="one"),
            ImageContent(type="image", data="AAAA", mime_type="image/png"),
            TextContent(type="text", text="two"),
        ]
    )

    async with pool_with(client) as pool:
        outcome = await McpToolProvider(pool).call("open-meteo__forecast", {})

    assert outcome.text == "one\ntwo"


async def test_a_server_error_result_stays_an_error():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="latitude must be <= 90")], is_error=True
    )

    async with pool_with(client) as pool:
        outcome = await McpToolProvider(pool).call("open-meteo__forecast", {"latitude": 200})

    assert outcome.is_error is True
    assert outcome.text == "latitude must be <= 90"
