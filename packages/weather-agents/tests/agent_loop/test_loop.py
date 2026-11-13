import asyncio
import time

import pytest
from labs_logging import bound_context

from tests.agent_loop.fakes import (
    FakeMessages,
    FakeToolProvider,
    final,
    message,
    spec,
    text,
    thinking,
    tool_use,
    usage,
)
from tests.logs import CapturedLogs
from weather_agents.agent_loop.answer import ToolCallSource
from weather_agents.agent_loop.errors import ConfigurationError, RunError, RunLimit
from weather_agents.agent_loop.loop import run_agent
from weather_agents.agent_loop.tools import ToolOutcome
from weather_agents.settings import Settings

pytestmark = pytest.mark.anyio

QUESTION = "What is the weather in Lviv tomorrow?"


def settings(**changes: object) -> Settings:
    return Settings.model_validate({"ANTHROPIC_API_KEY": None, **changes})


async def run(api: FakeMessages, tools: FakeToolProvider | None = None, **changes: object):
    return await run_agent(
        create_message=api.create,
        tools=tools or FakeToolProvider([spec()]),
        history=[],
        question=QUESTION,
        settings=settings(**changes),
        system="You answer weather questions.",
    )


def tool_round(*calls: tuple[str, str, dict[str, object]]):
    return message(thinking(), *(tool_use(*call) for call in calls), stop_reason="tool_use")


async def test_one_end_turn_returns_the_answer():
    api = FakeMessages(final("Sunny."))
    outcome = await run(api)
    assert outcome.answer.text == "Sunny."
    assert outcome.turns == 1
    assert outcome.tool_calls == 0
    request = api.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["messages"] == [{"role": "user", "content": QUESTION}]
    assert request["output_config"]["format"]["type"] == "json_schema"


async def test_tools_are_sent_with_their_schema_and_not_strict():
    api = FakeMessages(final())
    await run(api)
    (tool,) = api.requests[0]["tools"]
    assert tool["name"] == "open-meteo__forecast"
    assert tool["input_schema"]["properties"]["latitude"]["maximum"] == 90
    assert "strict" not in tool


async def test_a_tool_round_resolves_the_cited_call():
    api = FakeMessages(
        tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84})),
        final("Sunny, 21 C.", "toolu_1"),
    )
    outcome = await run(api)
    assert outcome.answer.resources[0].source == ToolCallSource(
        tool="open-meteo__forecast", arguments={"latitude": 49.84}
    )
    assert (outcome.turns, outcome.tool_calls) == (2, 1)
    assert outcome.usage.total == 240


async def test_two_calls_run_concurrently_and_return_in_one_message():
    tools = FakeToolProvider([spec()], delay=0.1)
    api = FakeMessages(
        tool_round(
            ("toolu_1", "open-meteo__forecast", {"latitude": 49.84}),
            ("toolu_2", "open-meteo__forecast", {"latitude": 50.45}),
        ),
        final(),
    )
    await run(api, tools)
    (first_start, first_end), (second_start, second_end) = tools.timings
    assert second_start < first_end and first_start < second_end
    results = api.requests[1]["messages"][-1]
    assert results["role"] == "user"
    assert [block["tool_use_id"] for block in results["content"]] == ["toolu_1", "toolu_2"]


async def test_error_outcomes_and_raising_tools_reach_the_model_as_errors():
    tools = FakeToolProvider(
        [spec("a__bad"), spec("a__broken")],
        outcomes={
            "a__bad": ToolOutcome(text="latitude: must be <= 90", is_error=True),
            "a__broken": RuntimeError("server gone"),
        },
    )
    api = FakeMessages(
        tool_round(("toolu_1", "a__bad", {"latitude": 120}), ("toolu_2", "a__broken", {})),
        final(),
    )
    outcome = await run(api, tools)
    blocks = api.requests[1]["messages"][-1]["content"]
    assert [(block["is_error"], block["content"]) for block in blocks] == [
        (True, "[source id: toolu_1]\nlatitude: must be <= 90"),
        (True, "[source id: toolu_2]\ntool call failed: server gone"),
    ]
    assert outcome.answer.text


async def test_assistant_content_goes_back_unchanged_thinking_included():
    first = tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84}))
    api = FakeMessages(first, final())
    outcome = await run(api)
    assistant = api.requests[1]["messages"][1]
    assert assistant == {"role": "assistant", "content": first.content}
    assert assistant["content"][0].signature == "sig-1"
    assert len(outcome.messages) == 4


async def test_pause_turn_continues_without_a_user_turn():
    paused = message(text("Looking that up"), stop_reason="pause_turn")
    api = FakeMessages(paused, final())
    outcome = await run(api)
    assert outcome.turns == 2
    assert [m["role"] for m in api.requests[1]["messages"]] == ["user", "assistant"]


async def test_an_answer_off_its_schema_raises_a_run_error():
    api = FakeMessages(message(text("It will be sunny.")))
    with pytest.raises(RunError, match="did not match its schema") as caught:
        await run(api)
    assert caught.value.stop_reason == "end_turn"
    assert caught.value.partial_text == "It will be sunny."


@pytest.mark.parametrize(
    "stop_reason", ["max_tokens", "stop_sequence", "refusal", "model_context_window_exceeded"]
)
async def test_other_stop_reasons_raise_without_running_tools(stop_reason: str):
    tools = FakeToolProvider([spec()])
    cut = message(
        text("Tomorrow in Lviv"),
        tool_use("toolu_1", "open-meteo__forecast", {"latitude": 49.84}),
        stop_reason=stop_reason,
        tokens=usage(1_000, 500),
    )
    with pytest.raises(RunError, match=stop_reason) as caught:
        await run(FakeMessages(cut), tools)
    error = caught.value
    assert error.stop_reason == stop_reason
    assert error.partial_text == "Tomorrow in Lviv"
    assert error.usage.total == 1_500
    assert error.cost_usd == pytest.approx((1_000 * 0.10 + 500 * 0.50) / 1_000_000)
    assert tools.calls == []


async def test_an_unpriced_model_fails_before_any_call():
    api = FakeMessages(final())
    with pytest.raises(ConfigurationError, match="claude-unknown-1"):
        await run(api, model="claude-unknown-1")
    assert api.requests == []


async def test_the_cap_stops_before_the_next_call():
    api = FakeMessages(
        message(
            tool_use("toolu_1", "open-meteo__forecast", {"latitude": 49.84}),
            stop_reason="tool_use",
            tokens=usage(200_000, 10_000),  # $0.025 on Haiku 5.5
        ),
        final(),
    )
    with pytest.raises(RunError) as caught:
        await run(api, usd_cap=0.02)
    assert caught.value.limit is RunLimit.USD_CAP
    assert "USD cap" in str(caught.value)
    assert len(api.requests) == 1


async def test_the_deadline_cancels_a_slow_tool():
    tools = FakeToolProvider([spec()], delay=10)
    api = FakeMessages(tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84})))
    started = time.monotonic()
    with pytest.raises(RunError) as caught:
        await run(api, tools, deadline_seconds=0.2)
    assert caught.value.limit is RunLimit.DEADLINE
    assert time.monotonic() - started < 1.2
    assert tools.timings == []  # the call never finished


async def test_the_deadline_cancels_a_slow_model_call():
    api = FakeMessages(final(), delay=10)
    with pytest.raises(RunError) as caught:
        await run(api, deadline_seconds=0.2)
    assert caught.value.limit is RunLimit.DEADLINE


async def test_each_step_is_logged_with_the_session(logs: CapturedLogs):
    tools = FakeToolProvider(
        [spec()], outcomes={"open-meteo__forecast": ToolOutcome(text="x" * 5_000)}
    )
    api = FakeMessages(
        tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84})),
        final("Sunny.", "toolu_1"),
    )
    with bound_context(session_id="s-1"):
        await run(api, tools)
    for event in ("model.request", "model.response", "tool.call", "tool.result"):
        lines = logs.events(event)
        assert lines, event
        assert all(line["level"] == "debug" for line in lines)
    for event in ("model.request", "model.response", "tool.result"):
        assert all(
            "tokens_so_far" in line and "seconds_left" in line for line in logs.events(event)
        )
    (result,) = logs.events("tool.result")
    assert result["result_truncated"] is True
    assert result["result_length"] == 5_000
    assert len(result["result"]) == 200
    ours = [r for r in logs.records() if str(r["logger"]).startswith("weather_agents")]
    assert len(ours) >= 7
    assert all(record.get("context", {}).get("session_id") == "s-1" for record in ours)
    (end,) = logs.events("run.end")
    assert (end["level"], end["outcome"], end["turns"], end["tool_calls"]) == ("info", "ok", 2, 1)


async def test_a_failed_run_still_logs_its_end_and_its_cause_once(logs: CapturedLogs):
    api = FakeMessages(
        tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84})),
        message(text("cut"), stop_reason="max_tokens"),
    )
    with pytest.raises(RunError):
        await run(api)
    (end,) = logs.events("run.end")
    assert (end["outcome"], end["turns"], end["tool_calls"]) == ("error", 2, 1)
    (error,) = logs.events("run.error")
    assert "max_tokens" in error["error"]


async def test_the_callers_history_is_not_changed():
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    api = FakeMessages(final())
    outcome = await run_agent(
        create_message=api.create,
        tools=FakeToolProvider(),
        history=history,  # ty: ignore[invalid-argument-type]
        question=QUESTION,
        settings=settings(),
        system="s",
    )
    assert len(history) == 2
    assert len(outcome.messages) == 4


async def test_cancellation_is_not_mistaken_for_a_tool_error():
    tools = FakeToolProvider([spec()], delay=10)
    api = FakeMessages(tool_round(("toolu_1", "open-meteo__forecast", {"latitude": 49.84})))
    task = asyncio.create_task(run(api, tools))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_each_tool_result_shows_its_source_id_first():
    tools = FakeToolProvider(
        [spec()], outcomes={"open-meteo__forecast": ToolOutcome(text='{"temperature": 21}')}
    )
    api = FakeMessages(
        tool_round(("toolu_abc", "open-meteo__forecast", {"latitude": 49.84})), final()
    )
    await run(api, tools)
    (block,) = api.requests[1]["messages"][-1]["content"]
    assert block["content"] == '[source id: toolu_abc]\n{"temperature": 21}'
