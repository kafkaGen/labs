import json
from pathlib import Path

import pytest
from mcp.types import Tool

from tests.agent.fakes import ScriptedMessages, text_reply, tool_reply
from tests.client.fakes import FakeClient, FakeFactory
from weather_agents.agent_loop import RunError
from weather_agents.agents import WEATHER_SYSTEM_PROMPT
from weather_agents.runtimes import ApiRuntime
from weather_agents.settings import Settings, load_settings

pytestmark = pytest.mark.anyio


def settings_for(tmp_path: Path, *commands: str) -> Settings:
    servers = {f"server-{command}": {"command": command} for command in commands}
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": servers}))
    return load_settings(anthropic_api_key="sk-test", mcp_config=config)


def forecast_client() -> FakeClient:
    return FakeClient(
        tools=[Tool(name="forecast", description="Forecast.", input_schema={"type": "object"})]
    )


async def test_tools_from_the_config_reach_the_model(tmp_path: Path):
    api = ScriptedMessages(text_reply("Sunny."))
    factory = FakeFactory({"a": forecast_client()})

    async with ApiRuntime(
        settings_for(tmp_path, "a"), messages_api=api, mcp_client_factory=factory
    ) as runtime:
        await runtime.send("weather?")

    tool = api.requests[0]["tools"][0]
    assert tool == {
        "name": "server-a__forecast",
        "description": "Forecast.",
        "input_schema": {"type": "object"},
    }
    assert api.requests[0]["system"] == WEATHER_SYSTEM_PROMPT
    assert api.requests[0]["model"] == "claude-haiku-5-5"


async def test_one_question_one_answer_through_a_tool(tmp_path: Path):
    api = ScriptedMessages(tool_reply(("server-a__forecast", {"days": 2})), text_reply("12°C."))
    client = forecast_client()

    async with ApiRuntime(
        settings_for(tmp_path, "a"), messages_api=api, mcp_client_factory=FakeFactory({"a": client})
    ) as runtime:
        result = await runtime.send("what's the weather in Lviv tomorrow?")

    assert result.answer == "12°C."
    assert result.session_id
    assert ("call_tool", ("forecast", {"days": 2})) in client.calls


async def test_only_servers_that_opened_contribute_tools(tmp_path: Path):
    api = ScriptedMessages(text_reply("ok"))
    factory = FakeFactory({"a": forecast_client(), "b": FakeClient(open_error=OSError("no"))})

    async with ApiRuntime(
        settings_for(tmp_path, "a", "b"), messages_api=api, mcp_client_factory=factory
    ) as runtime:
        result = await runtime.send("weather?")

    assert result.answer == "ok"
    names = [tool["name"] for tool in api.requests[0]["tools"]]
    assert names == ["server-a__forecast"]


async def test_two_sends_get_two_sessions(tmp_path: Path):
    api = ScriptedMessages(text_reply("one"), text_reply("two"))
    factory = FakeFactory({"a": forecast_client()})

    async with ApiRuntime(
        settings_for(tmp_path, "a"), messages_api=api, mcp_client_factory=factory
    ) as runtime:
        first = await runtime.send("q1")
        second = await runtime.send("q2")

    assert first.session_id != second.session_id


async def test_leaving_the_context_closes_the_servers(tmp_path: Path):
    client = forecast_client()

    async with ApiRuntime(
        settings_for(tmp_path, "a"),
        messages_api=ScriptedMessages(),
        mcp_client_factory=FakeFactory({"a": client}),
    ):
        assert client.closed is False

    assert client.closed is True


async def test_close_closes_the_servers_and_is_safe_twice(tmp_path: Path):
    client = forecast_client()
    runtime = ApiRuntime(
        settings_for(tmp_path, "a"),
        messages_api=ScriptedMessages(),
        mcp_client_factory=FakeFactory({"a": client}),
    )

    await runtime.__aenter__()
    await runtime.close()
    await runtime.close()

    assert client.closed is True
    with pytest.raises(RuntimeError, match="not open"):
        await runtime.send("q")


async def test_no_mcp_client_handlers_are_passed(tmp_path: Path):
    factory = FakeFactory({"a": forecast_client()})

    async with ApiRuntime(
        settings_for(tmp_path, "a"), messages_api=ScriptedMessages(), mcp_client_factory=factory
    ):
        pass

    [(_, kwargs)] = factory.calls
    assert kwargs == {"mode": "legacy"}


async def test_a_failed_run_leaves_the_runtime_usable(tmp_path: Path):
    api = ScriptedMessages(text_reply("cut", stop_reason="max_tokens"), text_reply("fine"))
    factory = FakeFactory({"a": forecast_client()})

    async with ApiRuntime(
        settings_for(tmp_path, "a"), messages_api=api, mcp_client_factory=factory
    ) as runtime:
        with pytest.raises(RunError):
            await runtime.send("q1")
        result = await runtime.send("q2")

    assert result.answer == "fine"


async def test_the_default_api_client_opens_and_closes_without_a_call(tmp_path: Path):
    factory = FakeFactory({"a": forecast_client()})

    async with ApiRuntime(settings_for(tmp_path, "a"), mcp_client_factory=factory) as runtime:
        assert runtime._api is not None  # noqa: SLF001

    assert runtime._api is None  # noqa: SLF001
