from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.agent_loop.fakes import (
    FakeMessages,
    FakeToolProvider,
    final,
    message,
    spec,
    text,
    tool_use,
)
from tests.client.fakes import FakeClient, FakeFactory
from weather_agents.mcp_client import McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.agent_loop.errors import RunError, RunLimit, UnknownSessionError
from weather_agents.runtimes.api import ApiRuntime, RuntimeNotOpenError
from weather_agents.runtimes.base import AgentRuntime
from weather_agents.settings import Settings

pytestmark = pytest.mark.anyio

LVIV = "What is the weather in Lviv tomorrow?"


def settings(**changes: object) -> Settings:
    return Settings.model_validate({"ANTHROPIC_API_KEY": None, **changes})


def forecast_round(tool_use_id: str = "toolu_1"):
    return message(
        tool_use(tool_use_id, "open-meteo__forecast", {"latitude": 49.84}), stop_reason="tool_use"
    )


def runtime(api: FakeMessages, tools: FakeToolProvider | None = None, **changes: object):
    return ApiRuntime(
        settings(**changes),
        create_message=api.create,
        tools=tools or FakeToolProvider([spec()]),
    )


async def test_the_runtime_meets_the_interface():
    api = FakeMessages(final("Sunny."))
    async with runtime(api) as api_runtime:
        agent: AgentRuntime = api_runtime
        result = await agent.send(LVIV)
        await agent.clear(result.session_id)
    assert result.answer == "Sunny."


async def test_a_question_without_an_id_starts_a_new_session():
    api = FakeMessages(forecast_round(), final("Sunny, 21 C.", "toolu_1"))
    async with runtime(api) as agent:
        result = await agent.send(LVIV)
    assert result.session_id
    assert result.answer == "Sunny, 21 C."
    assert [resource.source.type for resource in result.resources] == ["tool_call"]
    assert result.usage.total == 240
    assert result.cost_usd > 0


async def test_a_follow_up_sends_the_earlier_exchange_tool_turns_included():
    api = FakeMessages(forecast_round(), final("Sunny.", "toolu_1"), final("Rain the day after."))
    async with runtime(api) as agent:
        first = await agent.send(LVIV)
        second = await agent.send("and the day after?", first.session_id)
    assert second.session_id == first.session_id
    sent = api.requests[2]["messages"]
    assert [turn["role"] for turn in sent] == ["user", "assistant", "user", "assistant", "user"]
    assert sent[2]["content"][0]["type"] == "tool_result"
    assert sent[-1] == {"role": "user", "content": "and the day after?"}


async def test_two_sessions_do_not_share_history():
    api = FakeMessages(final("A."), final("B."))
    async with runtime(api) as agent:
        first = await agent.send("Lviv?")
        second = await agent.send("Kyiv?")
    assert first.session_id != second.session_id
    assert api.requests[1]["messages"] == [{"role": "user", "content": "Kyiv?"}]


async def test_an_unknown_id_fails_before_any_call():
    api = FakeMessages(final())
    async with runtime(api) as agent:
        with pytest.raises(UnknownSessionError, match="nope"):
            await agent.send(LVIV, "nope")
    assert api.requests == []


async def test_a_cleared_session_is_unknown():
    api = FakeMessages(final())
    async with runtime(api) as agent:
        result = await agent.send(LVIV)
        await agent.clear(result.session_id)
        with pytest.raises(UnknownSessionError, match=result.session_id):
            await agent.send("and tomorrow?", result.session_id)
    assert len(api.requests) == 1


async def test_close_forgets_every_session():
    api = FakeMessages(final(), final())
    agent = runtime(api)
    async with agent:
        first = await agent.send("Lviv?")
        second = await agent.send("Kyiv?")
    for session_id in (first.session_id, second.session_id):
        with pytest.raises(UnknownSessionError):
            await agent.send("again?", session_id)


async def test_a_failed_request_keeps_the_question_and_the_error_only():
    tools = FakeToolProvider([spec()], delay=10)
    api = FakeMessages(forecast_round(), final("Too slow before, sorry."))
    async with runtime(api, tools, deadline_seconds=0.2) as agent:
        with pytest.raises(RunError) as caught:
            await agent.send(LVIV)
        session_id = caught.value.session_id
        assert session_id is not None
        tools.delay = 0
        await agent.send("try again?", session_id)
    assert caught.value.limit is RunLimit.DEADLINE
    sent = api.requests[1]["messages"]
    assert sent[:2] == [
        {"role": "user", "content": LVIV},
        {"role": "assistant", "content": f"The request failed: {caught.value}"},
    ]
    assert sent[2] == {"role": "user", "content": "try again?"}
    assert not any(isinstance(turn["content"], list) for turn in sent)


async def test_overrides_apply_to_one_run_only():
    api = FakeMessages(final(), final())
    async with runtime(api) as agent:
        await agent.send(LVIV, overrides={"model": "claude-sonnet-5-5"})
        await agent.send(LVIV)
    assert [request["model"] for request in api.requests] == [
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    ]


async def test_an_invalid_override_fails_before_any_call():
    api = FakeMessages(final())
    async with runtime(api) as agent:
        with pytest.raises(ValidationError, match="usd_cap"):
            await agent.send(LVIV, overrides={"usd_cap": -1})
    assert api.requests == []


async def test_send_outside_the_context_manager_fails():
    with pytest.raises(RuntimeNotOpenError):
        await ApiRuntime(settings(), create_message=FakeMessages().create).send(LVIV)


async def test_the_runtime_opens_and_closes_the_mcp_servers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config = tmp_path / "mcp.json"
    client = FakeClient()

    def from_file(path: Path) -> McpClientPool:
        assert path == config
        servers = {"meteo": StdioServerConfig(command="meteo")}
        return McpClientPool(servers, client_factory=FakeFactory({"meteo": client}))

    monkeypatch.setattr(McpClientPool, "from_file", staticmethod(from_file))
    api = FakeMessages(message(text('{"answer": "Hi.", "resources": []}')))
    async with ApiRuntime(settings(mcp_config=config), create_message=api.create) as agent:
        await agent.send(LVIV)
        assert not client.closed
    assert client.closed
