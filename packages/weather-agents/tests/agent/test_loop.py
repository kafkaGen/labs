import logging
import time

import anthropic
import httpx2
import pytest

from tests.agent.fakes import FakeTools, ScriptedMessages, text_reply, tool_reply
from weather_agents.agent_loop import MessagesApi, RunError, ToolOutcome, ToolProvider, run_loop

pytestmark = pytest.mark.anyio

SYSTEM = "You answer weather questions."
OK = ToolOutcome(text='{"ok": true}')


async def run(api: MessagesApi, tools: ToolProvider, question: str = "weather?") -> str:
    return await run_loop(
        api, tools, model="claude-haiku-5-5", max_tokens=1000, system=SYSTEM, question=question
    )


def tool_results(request: dict[str, object]) -> list[dict[str, object]]:
    last = request["messages"][-1]  # ty: ignore[not-subscriptable]
    assert last["role"] == "user"
    return list(last["content"])


async def test_scripted_messages_returns_its_reply_and_records_the_request():
    api = ScriptedMessages(text_reply("hi"))

    reply = await api.create(
        model="m",
        max_tokens=1,
        system="s",
        tools=[],
        messages=[{"role": "user", "content": "q"}],
        cache_control={"type": "ephemeral"},
    )

    assert reply.content[0].type == "text"
    assert api.requests[0]["messages"] == [{"role": "user", "content": "q"}]


async def test_no_tool_needed():
    api = ScriptedMessages(text_reply("Sunny."))
    tools = FakeTools({"open-meteo__forecast": OK})

    assert await run(api, tools) == "Sunny."
    assert tools.calls == []
    assert len(api.requests) == 1


async def test_two_tool_rounds_then_an_answer():
    api = ScriptedMessages(
        tool_reply(("geocode", {"name": "Lviv"})),
        tool_reply(("forecast", {"latitude": 49.8, "longitude": 24.0})),
        text_reply("Tomorrow in Lviv: 12°C."),
    )
    tools = FakeTools(
        {"geocode": ToolOutcome(text="49.8,24.0"), "forecast": ToolOutcome(text="12C")}
    )

    answer = await run(api, tools, "weather in Lviv tomorrow?")

    assert answer == "Tomorrow in Lviv: 12°C."
    assert [name for name, _ in tools.calls] == ["geocode", "forecast"]
    assert tools.calls[1][1] == {"latitude": 49.8, "longitude": 24.0}
    assert tool_results(api.requests[1])[0]["content"] == "49.8,24.0"
    assert tool_results(api.requests[2])[0]["content"] == "12C"


async def test_the_request_offers_the_providers_tools_and_the_question():
    api = ScriptedMessages(text_reply("ok"))

    await run(api, FakeTools({"alpha": OK, "beta": OK}), "is it raining?")

    request = api.requests[0]
    assert [tool["name"] for tool in request["tools"]] == ["alpha", "beta"]
    assert request["tools"][0]["input_schema"] == {"type": "object"}
    assert request["system"] == SYSTEM
    assert request["messages"] == [{"role": "user", "content": "is it raining?"}]


async def test_caching_on_every_request():
    api = ScriptedMessages(tool_reply(("alpha", {})), text_reply("done"))

    await run(api, FakeTools({"alpha": OK}))

    assert [request["cache_control"] for request in api.requests] == [
        {"type": "ephemeral", "ttl": "5m"}
    ] * 2


async def test_thinking_blocks_survive_a_tool_round():
    first = tool_reply(("alpha", {}), thinking=True)
    api = ScriptedMessages(first, text_reply("done"))

    await run(api, FakeTools({"alpha": OK}))

    assistant = api.requests[1]["messages"][1]
    assert assistant["role"] == "assistant"
    assert list(assistant["content"]) == first.content
    assert assistant["content"][0].type == "thinking"
    assert assistant["content"][0].signature == "sig-abc"


async def test_two_slow_tools_overlap():
    api = ScriptedMessages(tool_reply(("alpha", {}), ("beta", {})), text_reply("done"))
    tools = FakeTools({"alpha": ToolOutcome(text="A"), "beta": ToolOutcome(text="B")}, delay=0.2)

    started = time.perf_counter()
    await run(api, tools)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.35
    results = tool_results(api.requests[1])
    assert [result["content"] for result in results] == ["A", "B"]
    tool_uses = api.requests[1]["messages"][1]["content"]
    assert [result["tool_use_id"] for result in results] == [block.id for block in tool_uses]
    assert len(api.requests[1]["messages"]) == 3


async def test_the_server_rejects_an_argument():
    api = ScriptedMessages(tool_reply(("forecast", {"latitude": 200})), text_reply("Sorry."))
    tools = FakeTools({"forecast": ToolOutcome(text="latitude must be <= 90", is_error=True)})

    assert await run(api, tools) == "Sorry."
    result = tool_results(api.requests[1])[0]
    assert result["is_error"] is True
    assert result["content"] == "latitude must be <= 90"


async def test_a_successful_result_carries_no_error_flag():
    api = ScriptedMessages(tool_reply(("alpha", {})), text_reply("done"))

    await run(api, FakeTools({"alpha": OK}))

    assert "is_error" not in tool_results(api.requests[1])[0]


@pytest.mark.parametrize("stop_reason", ["max_tokens", "stop_sequence", "refusal", "pause_turn"])
async def test_any_other_stop_reason_is_a_run_error(stop_reason: str):
    api = ScriptedMessages(tool_reply(("alpha", {}), stop_reason=stop_reason))
    tools = FakeTools({"alpha": OK})

    with pytest.raises(RunError, match=stop_reason) as caught:
        await run(api, tools)

    assert caught.value.stop_reason == stop_reason
    assert tools.calls == []


async def test_a_raising_tool_is_a_run_error_naming_the_tool():
    api = ScriptedMessages(tool_reply(("broken", {}), ("slow", {})))
    tools = FakeTools({"broken": OSError("pipe closed"), "slow": OK}, delay=0.05)

    with pytest.raises(RunError, match="broken") as caught:
        await run(api, tools)

    assert caught.value.tool == "broken"
    assert isinstance(caught.value.__cause__, OSError)
    assert "pipe closed" in str(caught.value)


async def test_a_raising_tool_cancels_its_siblings():
    api = ScriptedMessages(tool_reply(("broken", {}), ("slow", {})))

    class BrokenFirst(FakeTools):
        async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
            if name == "broken":
                self.calls.append((name, arguments))
                raise OSError("pipe closed")
            return await super().call(name, arguments)

    tools = BrokenFirst({"broken": OK, "slow": OK}, delay=1.0)

    with pytest.raises(RunError):
        await run(api, tools)

    assert tools.cancelled == ["slow"]


async def test_an_api_error_is_a_run_error_with_the_cause():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.AuthenticationError(
        "invalid x-api-key", response=httpx2.Response(401, request=request), body=None
    )
    api = ScriptedMessages(error)

    with pytest.raises(RunError) as caught:
        await run(api, FakeTools({}))

    assert caught.value.__cause__ is error


async def test_one_error_log_record_per_failure(caplog: pytest.LogCaptureFixture):
    api = ScriptedMessages(tool_reply(("broken", {}), ("also_broken", {})))
    tools = FakeTools({"broken": OSError("one"), "also_broken": OSError("two")})

    with caplog.at_level(logging.ERROR), pytest.raises(RunError):
        await run(api, tools)

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "broken" in errors[0].getMessage()


async def test_a_stop_reason_failure_logs_once(caplog: pytest.LogCaptureFixture):
    api = ScriptedMessages(text_reply("cut", stop_reason="max_tokens"))

    with caplog.at_level(logging.ERROR), pytest.raises(RunError):
        await run(api, FakeTools({}))

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "max_tokens" in errors[0].getMessage()
