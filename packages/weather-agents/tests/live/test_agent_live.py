"""The API runtime against the real Anthropic API and the real stdio server.

Run with `make test-live`. Needs ANTHROPIC_API_KEY in packages/weather-agents/.env. The server
calls the real Open-Meteo.
"""

import json
import sys

import pytest

from weather_agents.agent_loop import ToolCallResource
from weather_agents.runtimes import ApiRuntime
from weather_agents.settings import Settings

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_a_question_and_a_follow_up_through_the_real_api(tmp_path):
    config = tmp_path / "mcp.json"
    entry = {"command": sys.executable, "args": ["-m", "weather_agents.server"]}
    config.write_text(json.dumps({"mcpServers": {"open-meteo": entry}}))
    async with ApiRuntime(Settings(mcp_config=config)) as runtime:
        first = await runtime.send("What is tomorrow's forecast high in Berlin, in Celsius?")
        second = await runtime.send("Which city did I just ask about?", first.session_id)
    assert first.answer.answer
    assert first.tool_calls >= 1
    assert any(isinstance(r, ToolCallResource) for r in first.answer.resources)
    assert second.session_id == first.session_id
    assert "Berlin" in second.answer.answer
