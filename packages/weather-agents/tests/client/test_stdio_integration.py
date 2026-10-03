"""Our pool against the real stdio server. Nothing here reaches Open-Meteo."""

import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp.types import TextContent, TextResourceContents

from weather_agents.mcp_client import McpClientError, McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig

pytestmark = pytest.mark.anyio

# A hang fails the test instead of stalling the run.
TIME_LIMIT_SECONDS = 30

REAL_SERVER = StdioServerConfig(command=sys.executable, args=["-m", "weather_agents.server"])

# A child that answers `initialize`, then exits on the next request, like a server that crashes.
DIER_SCRIPT = """
import json, os, sys
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    if message["method"] != "initialize":
        os._exit(0)
    result = {
        "protocolVersion": message["params"]["protocolVersion"],
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "dier", "version": "0"},
    }
    reply = {"jsonrpc": "2.0", "id": message["id"], "result": result}
    sys.stdout.write(json.dumps(reply) + "\\n")
    sys.stdout.flush()
"""


def write_config(tmp_path: Path) -> Path:
    path = tmp_path / "mcp.json"
    entry = {"command": REAL_SERVER.command, "args": REAL_SERVER.args}
    path.write_text(json.dumps({"mcpServers": {"open-meteo": entry}}))
    return path


async def test_the_pool_lists_and_uses_everything_the_real_server_offers(tmp_path):
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool.from_file(write_config(tmp_path)) as pool:
            assert pool.failures == {}
            tools = await pool.list_tools("open-meteo")
            prompts = await pool.list_prompts("open-meteo")
            resources = await pool.list_resources("open-meteo")
            templates = await pool.list_resource_templates("open-meteo")
            guide = await pool.read_resource("open-meteo", "open-meteo://guide")
            prompt = await pool.get_prompt("open-meteo", "weekend_check")
    guide_part = guide.contents[0]
    prompt_part = prompt.messages[0].content
    assert isinstance(guide_part, TextResourceContents)
    assert isinstance(prompt_part, TextContent)
    assert len(tools) == 11
    assert {entry.name for entry in prompts} == {"weekend_check", "compare_places"}
    assert [str(resource.uri) for resource in resources] == ["open-meteo://guide"]
    assert [template.uri_template for template in templates] == [
        "open-meteo://endpoints/{endpoint}"
    ]
    assert guide_part.text.startswith("# Open-Meteo guide")
    assert "geocode_search" in prompt_part.text


async def test_a_tool_error_comes_back_as_a_result_not_an_exception(tmp_path):
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool.from_file(write_config(tmp_path)) as pool:
            result = await pool.call_tool(
                "open-meteo", "forecast", {"latitude": 95, "longitude": 0}
            )
    content = result.content[0]
    assert result.is_error
    assert isinstance(content, TextContent)
    assert "latitude" in content.text


async def test_servers_that_cannot_start_are_named_and_the_real_one_still_works():
    servers = {
        "ghost": StdioServerConfig(command="definitely-not-a-command-xyz"),
        "quitter": StdioServerConfig(command=sys.executable, args=["-c", "pass"]),
        "open-meteo": REAL_SERVER,
    }
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool(servers) as pool:
            assert pool.server_names == ["open-meteo"]
            assert set(pool.failures) == {"ghost", "quitter"}
            assert len(await pool.list_tools("open-meteo")) == 11
            with pytest.raises(McpClientError, match="'ghost'"):
                await pool.list_tools("ghost")
    assert "definitely-not-a-command-xyz" in str(pool.failures["ghost"])
    assert "Connection closed" in str(pool.failures["quitter"])


async def test_a_protocol_error_inside_the_pool_body_surfaces_as_mcp_client_error(tmp_path):
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        with pytest.raises(McpClientError) as caught:
            async with McpClientPool.from_file(write_config(tmp_path)) as pool:
                await pool.read_resource("open-meteo", "open-meteo://endpoints/nope")
    assert caught.value.server == "open-meteo"
    assert "read_resource" in str(caught.value)


async def test_a_server_that_dies_mid_session_is_named_and_the_others_keep_working():
    servers = {
        "dier": StdioServerConfig(command=sys.executable, args=["-c", DIER_SCRIPT]),
        "open-meteo": REAL_SERVER,
    }
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool(servers) as pool:
            assert pool.failures == {}
            for _ in range(2):
                with pytest.raises(McpClientError) as caught:
                    await pool.list_tools("dier")
                assert caught.value.server == "dier"
                assert "Connection closed" in str(caught.value)
            assert len(await pool.list_tools("open-meteo")) == 11
