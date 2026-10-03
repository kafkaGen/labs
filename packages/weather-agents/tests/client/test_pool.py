import json
from pathlib import Path

import pytest
from mcp import MCPError

from tests.client.fakes import FakeClient, FakeFactory, make_prompt, make_tool
from weather_agents.mcp_client import McpClientError, McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig

pytestmark = pytest.mark.anyio

CONFIGS = {"a": StdioServerConfig(command="a"), "b": StdioServerConfig(command="b")}


def pool_with(a: FakeClient, b: FakeClient) -> McpClientPool:
    return McpClientPool(CONFIGS, client_factory=FakeFactory({"a": a, "b": b}))


async def test_every_call_goes_to_the_named_server_only():
    a = FakeClient(tools=[make_tool("from_a")], prompts=[make_prompt("pa")])
    b = FakeClient(tools=[make_tool("from_b")])
    async with pool_with(a, b) as pool:
        tools_a = await pool.list_tools("a")
        tools_b = await pool.list_tools("b")
        await pool.call_tool("b", "from_b", {"x": 1})
        prompts_a = await pool.list_prompts("a")
    assert [tool.name for tool in tools_a] == ["from_a"]
    assert [tool.name for tool in tools_b] == ["from_b"]
    assert [prompt.name for prompt in prompts_a] == ["pa"]
    assert ("call_tool", ("from_b", {"x": 1})) in b.calls
    assert all(method != "call_tool" for method, _ in a.calls)


async def test_the_other_routed_methods_reach_the_named_server():
    a, b = FakeClient(), FakeClient()
    async with pool_with(a, b) as pool:
        await pool.list_resources("a")
        await pool.list_resource_templates("a")
        await pool.read_resource("b", "x://1")
        await pool.get_prompt("b", "p1", {"month": "June"})
    assert [method for method, _ in a.calls] == ["list_resources", "list_resource_templates"]
    assert b.calls == [("read_resource", "x://1"), ("get_prompt", ("p1", {"month": "June"}))]


async def test_servers_open_in_file_order_and_close_on_exit():
    a, b = FakeClient(), FakeClient()
    pool = McpClientPool(
        {"b": StdioServerConfig(command="b"), "a": StdioServerConfig(command="a")},
        client_factory=FakeFactory({"a": a, "b": b}),
    )
    async with pool:
        assert pool.server_names == ["b", "a"]
        assert pool.failures == {}
        assert not a.closed
        assert not b.closed
    assert a.closed
    assert b.closed


async def test_a_server_that_fails_to_open_is_recorded_and_the_others_still_work():
    a = FakeClient(tools=[make_tool("from_a")])
    b = FakeClient(open_error=FileNotFoundError(2, "No such file or directory"))
    async with pool_with(a, b) as pool:
        assert pool.server_names == ["a"]
        assert list(pool.failures) == ["b"]
        assert pool.failures["b"].server == "b"
        assert [tool.name for tool in await pool.list_tools("a")] == ["from_a"]
        with pytest.raises(McpClientError, match="'b'.*could not start") as caught:
            await pool.list_tools("b")
    assert caught.value is pool.failures["b"]


async def test_a_name_that_is_not_in_the_file_is_an_error():
    async with pool_with(FakeClient(), FakeClient()) as pool:
        with pytest.raises(McpClientError, match="'ghost': no such server"):
            await pool.list_tools("ghost")


async def test_a_dropped_session_fails_its_calls_and_leaves_the_other_server_working():
    a = FakeClient()
    b = FakeClient(tools=[make_tool("from_b")])
    async with pool_with(a, b) as pool:
        a.error = MCPError(-32000, "Connection closed")
        with pytest.raises(McpClientError, match="'a'.*Connection closed"):
            await pool.list_tools("a")
        assert [tool.name for tool in await pool.list_tools("b")] == ["from_b"]
    assert a.closed
    assert b.closed


async def test_an_error_raised_in_the_body_comes_out_unwrapped_through_every_session():
    a = FakeClient(wrap_exit_errors=True)
    b = FakeClient(wrap_exit_errors=True)
    with pytest.raises(McpClientError) as caught:
        async with pool_with(a, b):
            raise McpClientError("a", "boom")
    assert caught.value.server == "a"
    assert str(caught.value) == "MCP server 'a': boom"
    assert a.closed
    assert b.closed


async def test_from_file_opens_the_servers_in_the_file(tmp_path: Path):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"a": {"command": "a"}}}))
    client = FakeClient(tools=[make_tool("from_a")])
    pool = McpClientPool.from_file(path, client_factory=FakeFactory({"a": client}))
    async with pool:
        assert [tool.name for tool in await pool.list_tools("a")] == ["from_a"]


async def test_entering_again_forgets_the_last_run():
    a = FakeClient()
    b = FakeClient(open_error=OSError(2, "No such file or directory"))
    pool = pool_with(a, b)
    async with pool:
        assert set(pool.failures) == {"b"}
        assert pool.server_names == ["a"]
    b.open_error = None
    async with pool:
        assert pool.failures == {}
        assert pool.server_names == ["a", "b"]
