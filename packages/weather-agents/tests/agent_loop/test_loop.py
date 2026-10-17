import pytest

from tests.agent_loop.fakes import (
    BERLIN,
    FORECAST,
    FakeModelCaller,
    FakeToolProvider,
    answer_reply,
    content_of,
    make_settings,
    reply,
    text,
    thinking,
    tool_use,
)
from weather_agents.agent_loop import (
    ApiCallError,
    InvalidAnswerError,
    RunFinished,
    SourceLedger,
    StopReasonError,
    ToolCallFinished,
    ToolOutcome,
)
from weather_agents.agent_loop.loop import run_agent
from weather_agents.agents import WEATHER_AGENT

pytestmark = pytest.mark.anyio

QUESTION = "Weather in Berlin?"


async def run(caller, tools=None, *, history=None, ledger=None):
    tools = tools if tools is not None else FakeToolProvider()
    events = []
    async for event in run_agent(
        caller=caller,
        tools=tools,
        tool_specs=await tools.list_tools(),
        agent=WEATHER_AGENT,
        settings=make_settings(),
        history=history if history is not None else [],
        question=QUESTION,
        ledger=ledger if ledger is not None else SourceLedger(),
    ):
        events.append(event)
    return events


async def test_an_end_turn_reply_finishes_the_run_with_its_answer():
    caller = FakeModelCaller(answer_reply("Sunny."))
    events = await run(caller)
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    assert finished.result.answer.answer == "Sunny."
    assert (finished.result.turns, finished.result.tool_calls) == (1, 0)
    assert finished.result.usage.input == 10
    assert caller.requests[0].system == WEATHER_AGENT.system_prompt
    assert caller.requests[0].messages == [{"role": "user", "content": QUESTION}]
    assert [m["role"] for m in finished.messages] == ["user", "assistant"]


async def test_tool_calls_from_one_turn_run_at_once_and_return_in_one_message():
    marine, flood = "open-meteo__marine", "open-meteo__flood"
    tools = FakeToolProvider(
        {
            FORECAST: ToolOutcome(content="21 °C"),
            marine: ToolOutcome(content="calm"),
            flood: ToolOutcome(content="low"),
        },
        barrier=3,
    )
    caller = FakeModelCaller(
        reply(
            tool_use("t1", FORECAST, BERLIN),
            tool_use("t2", marine, BERLIN),
            tool_use("t3", flood, BERLIN),
            stop_reason="tool_use",
        ),
        answer_reply(),
    )
    events = await run(caller, tools)
    results = content_of(caller.requests[1].messages[-1])
    assert [r["tool_use_id"] for r in results] == ["t1", "t2", "t3"]
    assert [r["content"] for r in results] == ["21 °C", "calm", "low"]
    assert [r["is_error"] for r in results] == [False, False, False]
    assert [type(e).__name__ for e in events] == [
        "ModelTurn",
        "ToolCallStarted",
        "ToolCallStarted",
        "ToolCallStarted",
        "ToolCallFinished",
        "ToolCallFinished",
        "ToolCallFinished",
        "ModelTurn",
        "RunFinished",
    ]
    assert (events[-1].result.turns, events[-1].result.tool_calls) == (2, 3)


async def test_pause_turn_calls_again_with_nothing_added():
    caller = FakeModelCaller(reply(text("Searching"), stop_reason="pause_turn"), answer_reply())
    events = await run(caller)
    assert len(caller.requests) == 2
    assert caller.requests[1].messages[-1]["role"] == "assistant"
    assert isinstance(events[-1], RunFinished)


@pytest.mark.parametrize(
    "stop_reason", ["max_tokens", "stop_sequence", "refusal", "model_context_window_exceeded"]
)
async def test_a_stop_reason_the_loop_cannot_continue_on_raises(stop_reason):
    caller = FakeModelCaller(reply(text('{"answer": "Sun'), stop_reason=stop_reason))
    with pytest.raises(StopReasonError) as caught:
        await run(caller)
    assert caught.value.stop_reason == stop_reason
    assert caught.value.partial_text == '{"answer": "Sun'
    assert caught.value.usage.input == 10
    assert caught.value.session_id == ""


async def test_thinking_and_tool_use_blocks_go_back_unchanged():
    caller = FakeModelCaller(
        reply(
            thinking("Need the forecast.", "sig-1"),
            tool_use("t1", FORECAST, BERLIN),
            stop_reason="tool_use",
        ),
        answer_reply(),
    )
    await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assistant = content_of(caller.requests[1].messages[1])
    assert assistant[0] == {
        "type": "thinking",
        "thinking": "Need the forecast.",
        "signature": "sig-1",
    }
    assert assistant[1] == {"type": "tool_use", "id": "t1", "name": FORECAST, "input": BERLIN}


async def test_a_final_reply_that_is_not_an_answer_raises():
    caller = FakeModelCaller(reply(text("It is sunny.")))
    with pytest.raises(InvalidAnswerError) as caught:
        await run(caller)
    assert caught.value.partial_text == "It is sunny."


async def test_resources_the_session_never_touched_are_dropped():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        answer_reply(
            resources=[
                {
                    "kind": "tool_call",
                    "tool": FORECAST,
                    "arguments": '{"longitude": 13.41, "latitude": 52.52}',
                    "title": "Forecast",
                },
                {
                    "kind": "tool_call",
                    "tool": FORECAST,
                    "arguments": '{"latitude": 0, "longitude": 0}',
                    "title": "Invented call",
                },
                {"kind": "url", "url": "https://example.com", "title": "Invented page"},
            ]
        ),
    )
    events = await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assert [r.title for r in events[-1].result.answer.resources] == ["Forecast"]


async def test_a_resource_from_earlier_in_the_session_is_kept():
    ledger = SourceLedger()
    ledger.record_tool_call(FORECAST, BERLIN)
    resource = {
        "kind": "tool_call",
        "tool": FORECAST,
        "arguments": '{"latitude": 52.52, "longitude": 13.41}',
        "title": "Earlier forecast",
    }
    events = await run(FakeModelCaller(answer_reply(resources=[resource])), ledger=ledger)
    assert [r.title for r in events[-1].result.answer.resources] == ["Earlier forecast"]


async def test_a_tool_that_raises_becomes_an_error_result():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply()
    )
    events = await run(caller, FakeToolProvider({FORECAST: RuntimeError("boom")}))
    (finished,) = [e for e in events if isinstance(e, ToolCallFinished)]
    assert finished.is_error
    assert "RuntimeError: boom" in finished.content
    assert content_of(caller.requests[1].messages[-1])[0]["is_error"] is True


async def test_the_history_passed_in_is_not_changed():
    history = [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]
    snapshot = list(history)
    events = await run(FakeModelCaller(answer_reply()), history=history)
    assert history == snapshot
    assert [m["role"] for m in events[-1].messages] == ["user", "assistant", "user", "assistant"]


async def test_an_api_error_carries_the_usage_so_far():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        ApiCallError("the API returned 529: overloaded", status_code=529),
    )
    with pytest.raises(ApiCallError) as caught:
        await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assert caught.value.usage.input == 10
