import pytest
from mcp.types import CallToolResult, TextContent

from tests.agent_loop.fakes import (
    BERLIN,
    FORECAST,
    FakeModelCaller,
    answer_reply,
    make_settings,
    reply,
    text,
    tool_use,
)
from tests.runtimes.fakes import FakePool
from weather_agents.agent_loop import StopReasonError
from weather_agents.mcp_client import McpClientError
from weather_agents.runtimes import ApiRuntime, SessionNotFoundError

pytestmark = pytest.mark.anyio


def runtime(caller, pool=None) -> ApiRuntime:
    return ApiRuntime(
        make_settings(), model_caller=caller, pool=pool if pool is not None else FakePool()
    )


async def test_a_question_without_a_session_id_starts_a_session():
    caller = FakeModelCaller(answer_reply("Sunny."))
    async with runtime(caller) as rt:
        result = await rt.send("Weather in Berlin?")
    assert result.answer.answer == "Sunny."
    assert len(result.session_id) == 32
    (tool,) = caller.requests[0].tools
    assert tool.name == FORECAST
    assert "minimum" not in tool.input_schema["properties"]["latitude"]
    assert tool.input_schema["additionalProperties"] is False


async def test_a_follow_up_sends_the_earlier_conversation():
    caller = FakeModelCaller(answer_reply("Sunny."), answer_reply("Rain."))
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        second = await rt.send("And tomorrow?", first.session_id)
    assert second.session_id == first.session_id
    messages = caller.requests[1].messages
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "Weather in Berlin?"
    assert messages[2]["content"] == "And tomorrow?"


async def test_two_sessions_do_not_share_history():
    caller = FakeModelCaller(answer_reply(), answer_reply())
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        second = await rt.send("Weather in Paris?")
    assert second.session_id != first.session_id
    assert caller.requests[1].messages == [{"role": "user", "content": "Weather in Paris?"}]


async def test_an_unknown_session_id_fails_before_any_model_call():
    caller = FakeModelCaller()
    async with runtime(caller) as rt:
        with pytest.raises(SessionNotFoundError, match="nope") as caught:
            await rt.send("Hi", "nope")
    assert caught.value.session_id == "nope"
    assert caller.requests == []


async def test_a_failed_request_leaves_the_question_and_the_error_in_the_session():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        reply(text("I can't"), stop_reason="refusal"),
        answer_reply("Sorry about that."),
    )
    async with runtime(caller) as rt:
        with pytest.raises(StopReasonError) as caught:
            await rt.send("Weather in Berlin?")
        assert len(caught.value.session_id) == 32
        await rt.send("Try again?", caught.value.session_id)
    assert caller.requests[2].messages == [
        {"role": "user", "content": "Weather in Berlin?"},
        {
            "role": "assistant",
            "content": "The previous request failed: the model stopped with 'refusal'",
        },
        {"role": "user", "content": "Try again?"},
    ]


async def test_a_tool_call_reaches_the_pool_by_its_prefixed_name():
    pool = FakePool(
        results={FORECAST: CallToolResult(content=[TextContent(type="text", text="21")])}
    )
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply()
    )
    async with runtime(caller, pool) as rt:
        result = await rt.send("Weather in Berlin?")
    assert pool.calls == [(FORECAST, BERLIN)]
    assert result.tool_calls == 1


async def test_clear_forgets_the_session():
    caller = FakeModelCaller(answer_reply())
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        await rt.clear(first.session_id)
        with pytest.raises(SessionNotFoundError):
            await rt.send("And tomorrow?", first.session_id)
        with pytest.raises(SessionNotFoundError):
            await rt.clear(first.session_id)


async def test_closing_forgets_every_session_and_closes_the_pool():
    pool = FakePool()
    rt = runtime(FakeModelCaller(answer_reply()), pool)
    async with rt:
        first = await rt.send("Weather in Berlin?")
    assert pool.entered and pool.exited
    with pytest.raises(SessionNotFoundError):
        await rt.send("And tomorrow?", first.session_id)


async def test_close_then_exit_closes_the_pool_once():
    pool = FakePool()
    async with runtime(FakeModelCaller(), pool) as rt:
        await rt.close()
    assert pool.exited


async def test_the_agent_runs_without_tools_when_every_server_failed():
    pool = FakePool([], failures={"open-meteo": McpClientError("open-meteo", "spawn failed")})
    caller = FakeModelCaller(answer_reply())
    async with runtime(caller, pool) as rt:
        await rt.send("Weather in Berlin?")
    assert caller.requests[0].tools == []
