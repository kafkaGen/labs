import json

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from tests.runtimes.fakes import FakePool
from weather_agents.mcp_client import McpClientError
from weather_agents.runtimes.mcp_tools import McpToolProvider

pytestmark = pytest.mark.anyio

STRICT_FORBIDDEN = {"minimum", "maximum", "minLength", "maxItems", "pattern"}
PREFIX = "open-meteo__"


class ServerPool:
    """The real server's tools behind the pool's two model-facing methods."""

    def __init__(self, client: Client) -> None:
        self.client = client

    async def list_all_tools(self):
        tools = (await self.client.list_tools()).tools
        return [tool.model_copy(update={"name": f"{PREFIX}{tool.name}"}) for tool in tools]

    async def call_namespaced_tool(self, name, arguments=None):
        return await self.client.call_tool(name.removeprefix(PREFIX), arguments)


def keys_in(node: object) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {key for value in node.values() for key in keys_in(value)}
    if isinstance(node, list):
        return {key for item in node for key in keys_in(item)}
    return set()


def objects_in(node: object) -> list[dict]:
    found = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append(node)
        for value in node.values():
            found.extend(objects_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(objects_in(item))
    return found


async def test_the_real_servers_schemas_come_out_strict(client):
    original = {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}
    specs = await McpToolProvider(ServerPool(client)).list_tools()
    assert len(specs) == 11
    for spec in specs:
        assert not keys_in(spec.input_schema) & STRICT_FORBIDDEN, spec.name
        assert all(o["additionalProperties"] is False for o in objects_in(spec.input_schema)), (
            spec.name
        )
        assert spec.input_schema.get("required") == original[spec.name.removeprefix(PREFIX)].get(
            "required"
        )
    forecast = next(spec for spec in specs if spec.name == f"{PREFIX}forecast")
    assert "minimum" in forecast.input_schema["properties"]["latitude"]["description"]


async def test_an_out_of_range_argument_still_comes_back_as_a_server_error(client):
    outcome = await McpToolProvider(ServerPool(client)).call(
        f"{PREFIX}forecast", {"latitude": 95, "longitude": 0}
    )
    assert outcome.is_error
    assert "latitude" in outcome.content


async def test_text_blocks_are_joined_with_newlines():
    result = CallToolResult(
        content=[TextContent(type="text", text="a"), TextContent(type="text", text="b")]
    )
    pool = FakePool(results={f"{PREFIX}forecast": result})
    outcome = await McpToolProvider(pool).call(f"{PREFIX}forecast", {"latitude": 1})
    assert outcome.content == "a\nb"
    assert outcome.is_error is False
    assert pool.calls == [(f"{PREFIX}forecast", {"latitude": 1})]


async def test_structured_content_is_sent_as_json_when_there_is_no_text():
    result = CallToolResult(content=[], structured_content={"temperature": 21})
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": result})).call(
        f"{PREFIX}forecast", {}
    )
    assert json.loads(outcome.content) == {"temperature": 21}


async def test_the_error_flag_is_copied():
    result = CallToolResult(content=[TextContent(type="text", text="bad date")], is_error=True)
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": result})).call(
        f"{PREFIX}forecast", {}
    )
    assert outcome.is_error


async def test_a_client_error_becomes_an_error_result():
    error = McpClientError("open-meteo", "session dropped")
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": error})).call(
        f"{PREFIX}forecast", {}
    )
    assert outcome.is_error
    assert outcome.content == "MCP server 'open-meteo': session dropped"
