"""Live check of the API runtime: the real Claude API and the real MCP server over stdio.

Run with `make test-live` from `packages/weather-agents`. It needs `ANTHROPIC_API_KEY` in the
workspace `.env` or the environment, and spends real money under the default USD cap, about a
cent per run on Haiku 5.5. The `run.end` lines in the captured log give the exact cost.
"""

from pathlib import Path

import pytest

from tests.logs import CapturedLogs
from weather_agents.runtimes.api import ApiRuntime
from weather_agents.settings import Settings

pytestmark = [pytest.mark.live, pytest.mark.anyio]

PACKAGE = Path(__file__).resolve().parents[2]
WORKSPACE_ENV = PACKAGE.parents[1] / ".env"


@pytest.fixture
def live_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.chdir(PACKAGE)  # mcp.stdio.json and the server command are relative to it
    settings = Settings(_env_file=WORKSPACE_ENV)
    if settings.anthropic_api_key is None:
        pytest.skip("ANTHROPIC_API_KEY is not set")
    return settings


async def test_a_question_and_a_follow_up(live_settings: Settings, logs: CapturedLogs):
    async with ApiRuntime(live_settings) as runtime:
        first = await runtime.send("What is the weather in Lviv tomorrow?")
        follow_up = await runtime.send("and the day after?", first.session_id)

    assert first.answer
    assert any(resource.source.type == "tool_call" for resource in first.resources)
    assert follow_up.session_id == first.session_id
    assert "Lviv" in follow_up.answer

    ends = logs.events("run.end")
    assert [line["outcome"] for line in ends] == ["ok", "ok"]
    total = sum(float(str(line["cost_usd"])) for line in ends)
    print(f"live cost: ${total:.6f} over {sum(int(str(e['turns'])) for e in ends)} turns")
