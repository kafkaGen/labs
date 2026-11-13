import json

import pytest
from mcp.types import CallToolResult, ImageContent, TextContent, Tool

from tests.client.fakes import FakeClient, FakeFactory
from tests.logs import CapturedLogs
from weather_agents.mcp_client import McpClientError, McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.runtimes.mcp_tools import McpToolProvider

pytestmark = pytest.mark.anyio

LATITUDE_SCHEMA = {
    "type": "object",
    "properties": {"latitude": {"type": "number", "minimum": -90, "maximum": 90}},
    "required": ["latitude"],
}


def pool_of(**clients: FakeClient) -> McpClientPool:
    configs = {name: StdioServerConfig(command=name) for name in clients}
    return McpClientPool(configs, client_factory=FakeFactory(clients))


async def test_specs_keep_the_server_schema_unchanged():
    client = FakeClient(
        tools=[Tool(name="forecast", description="Daily forecast", input_schema=LATITUDE_SCHEMA)]
    )
    async with pool_of(meteo=client) as pool:
        specs = await McpToolProvider(pool).tool_specs()
    assert [spec.name for spec in specs] == ["meteo__forecast"]
    assert specs[0].description == "Daily forecast"
    assert specs[0].input_schema == LATITUDE_SCHEMA


async def test_structured_content_becomes_json_text():
    client = FakeClient(tools=[Tool(name="forecast", input_schema={"type": "object"})])
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="ignored")],
        structured_content={"temperature": 21.5},
    )
    async with pool_of(meteo=client) as pool:
        outcome = await McpToolProvider(pool).call("meteo__forecast", {"latitude": 49.8})
    assert json.loads(outcome.text) == {"temperature": 21.5}
    assert not outcome.is_error
    assert ("call_tool", ("forecast", {"latitude": 49.8})) in client.calls


async def test_an_error_result_keeps_its_text_and_flag():
    client = FakeClient(tools=[Tool(name="forecast", input_schema={"type": "object"})])
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="latitude: must be <= 90")], is_error=True
    )
    async with pool_of(meteo=client) as pool:
        outcome = await McpToolProvider(pool).call("meteo__forecast", {"latitude": 120})
    assert outcome.is_error
    assert outcome.text == "latitude: must be <= 90"


async def test_non_text_blocks_are_named_not_dropped():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[
            TextContent(type="text", text="chart:"),
            ImageContent(type="image", data="AA==", mime_type="image/png"),
        ]
    )
    async with pool_of(meteo=client) as pool:
        outcome = await McpToolProvider(pool).call("meteo__chart", {})
    assert outcome.text == "chart:\n[image content omitted]"


async def test_a_raised_client_error_becomes_an_error_outcome():
    client = FakeClient()
    async with pool_of(meteo=client) as pool:
        client.error = McpClientError("meteo", "connection closed")
        outcome = await McpToolProvider(pool).call("meteo__forecast", {})
    assert outcome.is_error
    assert outcome.text == "MCP server 'meteo': connection closed"


async def test_an_unknown_name_becomes_an_error_outcome():
    async with pool_of(meteo=FakeClient()) as pool:
        outcome = await McpToolProvider(pool).call("nowhere__forecast", {})
    assert outcome.is_error
    assert "nowhere" in outcome.text


async def test_a_failed_server_is_named_in_the_log(logs: CapturedLogs):
    broken = FakeClient(open_error=OSError(2, "No such file or directory"))
    working = FakeClient(tools=[Tool(name="forecast", input_schema={"type": "object"})])
    async with pool_of(broken=broken, meteo=working) as pool:
        specs = await McpToolProvider(pool).tool_specs()
    assert [spec.name for spec in specs] == ["meteo__forecast"]
    warnings = logs.events("mcp server unavailable")
    assert [line["server"] for line in warnings] == ["broken"]
