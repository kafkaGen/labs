import pytest
from mcp import MCPError
from mcp.types import CallToolResult, TextContent

from tests.client.fakes import (
    FakeClient,
    FakeFactory,
    make_prompt,
    make_resource,
    make_template,
    make_tool,
)
from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.mcp_client.errors import McpClientError
from weather_agents.mcp_client.session import McpSession

pytestmark = pytest.mark.anyio

CONFIG = StdioServerConfig(command="fake", args=["--flag"], env={"K": "v"})


def session_for(client: FakeClient) -> tuple[McpSession, FakeFactory]:
    factory = FakeFactory({"fake": client})
    return McpSession("weather", CONFIG, client_factory=factory), factory


async def test_the_session_starts_the_sdk_client_in_legacy_mode_with_no_handlers():
    session, factory = session_for(FakeClient())
    async with session:
        pass
    ((params, kwargs),) = factory.calls
    assert kwargs == {"mode": "legacy"}
    assert (params.command, params.args, params.env) == ("fake", ["--flag"], {"K": "v"})


async def test_the_session_closes_the_sdk_client_on_exit():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        assert not client.closed
    assert client.closed


async def test_list_tools_follows_every_page_and_returns_a_flat_list():
    client = FakeClient(tools=[make_tool(name) for name in "abcde"], page_size=2)
    session, _ = session_for(client)
    async with session:
        tools = await session.list_tools()
    assert [tool.name for tool in tools] == list("abcde")
    assert client.calls == [("list_tools", None), ("list_tools", "2"), ("list_tools", "4")]


async def test_the_other_three_lists_are_flat_lists_too():
    client = FakeClient(
        resources=[make_resource("x://1"), make_resource("x://2"), make_resource("x://3")],
        templates=[make_template("x://{a}"), make_template("y://{b}"), make_template("z://{c}")],
        prompts=[make_prompt("p1"), make_prompt("p2"), make_prompt("p3")],
    )
    session, _ = session_for(client)
    async with session:
        resources = await session.list_resources()
        templates = await session.list_resource_templates()
        prompts = await session.list_prompts()
    assert [str(resource.uri) for resource in resources] == ["x://1", "x://2", "x://3"]
    assert [template.uri_template for template in templates] == ["x://{a}", "y://{b}", "z://{c}"]
    assert [prompt.name for prompt in prompts] == ["p1", "p2", "p3"]


async def test_call_tool_returns_an_error_result_as_it_is():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="boom")], is_error=True
    )
    session, _ = session_for(client)
    async with session:
        result = await session.call_tool("forecast", {"latitude": 95})
    assert result is client.tool_result
    assert result.is_error
    assert client.calls == [("call_tool", ("forecast", {"latitude": 95}))]


async def test_read_resource_and_get_prompt_return_the_sdk_results():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        resource = await session.read_resource("x://1")
        prompt = await session.get_prompt("p1", {"month": "June"})
    assert resource is client.resource_result
    assert prompt is client.prompt_result
    assert client.calls == [("read_resource", "x://1"), ("get_prompt", ("p1", {"month": "June"}))]


async def test_a_protocol_error_names_the_server_and_the_operation():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        client.error = MCPError(-32000, "Connection closed")
        with pytest.raises(McpClientError) as caught:
            await session.call_tool("forecast", {})
    assert caught.value.server == "weather"
    assert (
        str(caught.value) == "MCP server 'weather': call_tool 'forecast' failed: Connection closed"
    )
    assert isinstance(caught.value.__cause__, MCPError)


async def test_a_spawn_failure_names_the_server_and_the_command():
    client = FakeClient(open_error=FileNotFoundError(2, "No such file or directory"))
    session, _ = session_for(client)
    with pytest.raises(McpClientError) as caught:
        async with session:
            pass
    assert caught.value.server == "weather"
    assert "could not start 'fake': No such file or directory" in str(caught.value)


async def test_an_exception_group_from_the_sdk_is_unwrapped_to_its_cause():
    nested = ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [
            ExceptionGroup(
                "unhandled errors in a TaskGroup", [MCPError(-32000, "Connection closed")]
            )
        ],
    )
    session, _ = session_for(FakeClient(open_error=nested))
    with pytest.raises(McpClientError) as caught:
        async with session:
            pass
    assert "could not connect: Connection closed" in str(caught.value)


async def test_calling_before_the_session_is_open_is_an_error():
    session, _ = session_for(FakeClient())
    with pytest.raises(McpClientError, match="session is not open"):
        await session.list_tools()


async def test_an_error_raised_in_the_body_comes_out_unwrapped_when_the_sdk_wraps_it():
    client = FakeClient(wrap_exit_errors=True)
    session, _ = session_for(client)
    with pytest.raises(McpClientError) as caught:
        async with session:
            client.error = MCPError(-32000, "Connection closed")
            await session.list_tools()
    assert caught.value.server == "weather"
    assert isinstance(caught.value.__cause__, MCPError)


async def test_an_error_that_is_not_ours_stays_inside_the_group():
    session, _ = session_for(FakeClient(wrap_exit_errors=True))
    with pytest.raises(ExceptionGroup) as caught:
        async with session:
            raise ValueError("boom")
    assert caught.value.exceptions[0].args == ("boom",)
