"""Spawns the real server as a child process. No tool is called, so no network is needed."""

import sys

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import TextContent, TextResourceContents

pytestmark = pytest.mark.anyio


async def test_the_stdio_server_lists_everything_and_serves_a_resource_and_a_prompt():
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        prompts = {prompt.name for prompt in (await client.list_prompts()).prompts}
        guide = await client.read_resource("open-meteo://guide")
        prompt = await client.get_prompt("weekend_check")
    guide_part = guide.contents[0]
    prompt_part = prompt.messages[0].content
    assert isinstance(guide_part, TextResourceContents)
    assert isinstance(prompt_part, TextContent)
    assert len(tools) == 11
    assert prompts == {"weekend_check", "compare_places"}
    assert guide_part.text.startswith("# Open-Meteo guide")
    assert "geocode_search" in prompt_part.text
