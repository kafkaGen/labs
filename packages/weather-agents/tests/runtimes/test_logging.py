import json
import logging

import pytest
from labs_logging import LoggingConfig, configure
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
from weather_agents.runtimes import ApiRuntime

pytestmark = pytest.mark.anyio

RUN_EVENTS = {"model call", "model replied", "tool call", "tool result", "run finished"}


@pytest.fixture
def log_lines(tmp_path):
    # Importing the MCP server (tests/conftest.py) leaves a RichHandler on the root logger, and
    # labs-logging refuses to configure over it. Park it for the test.
    root = logging.getLogger()
    parked = root.handlers[:]
    root.handlers.clear()
    config = LoggingConfig(
        app="weather-agents-test",
        family="weather_agents",
        level=logging.DEBUG,
        log_dir=tmp_path,
        console=False,
        synchronous=True,
    )
    with configure(config):

        def read():
            paths = sorted(tmp_path.glob("weather_agents/*/main.jsonl"))
            return [
                json.loads(line) for path in paths for line in path.read_text().splitlines() if line
            ]

        yield read
    root.handlers[:] = parked


def named(lines, event):
    return [line for line in lines if line["event"] == event]


def tool_turn_then_answer(**answer):
    return FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply(**answer)
    )


async def test_every_line_of_a_run_names_its_session(log_lines):
    async with ApiRuntime(
        make_settings(), model_caller=tool_turn_then_answer(), pool=FakePool()
    ) as rt:
        result = await rt.send("Weather in Berlin?")
    run_lines = [line for line in log_lines() if line["event"] in RUN_EVENTS]
    assert len(run_lines) == 7
    assert {line["context"]["session_id"] for line in run_lines} == {result.session_id}


async def test_debug_lines_carry_each_step_cut_to_the_truncation_length(log_lines):
    pool = FakePool(
        results={FORECAST: CallToolResult(content=[TextContent(type="text", text="x" * 100)])}
    )
    settings = make_settings(log_truncate=20)
    async with ApiRuntime(settings, model_caller=tool_turn_then_answer(), pool=pool) as rt:
        await rt.send("Weather in Berlin, please, as soon as you can?")
    lines = log_lines()
    first_call = named(lines, "model call")[0]
    assert first_call["level"] == "debug"
    assert first_call["context"]["step"] == 1
    assert "[cut " in first_call["context"]["input"]
    replied = named(lines, "model replied")[0]["context"]
    assert replied["stop_reason"] == "tool_use"
    assert replied["tool_uses"] == [FORECAST]
    assert replied["tokens"]["input"] == 10
    assert "elapsed_s" in replied
    tool_call = named(lines, "tool call")[0]["context"]
    assert tool_call["tool"] == FORECAST
    assert tool_call["arguments"].startswith('{"latitude": 52.52')
    tool_result = named(lines, "tool result")[0]["context"]
    assert tool_result["result"] == "x" * 20 + "… [cut 80 chars]"
    assert tool_result["is_error"] is False


async def test_the_end_of_a_run_logs_a_summary_at_info(log_lines):
    async with ApiRuntime(
        make_settings(), model_caller=tool_turn_then_answer(), pool=FakePool()
    ) as rt:
        await rt.send("Weather in Berlin?")
    (summary,) = named(log_lines(), "run finished")
    assert summary["level"] == "info"
    assert summary["context"]["turns"] == 2
    assert summary["context"]["tool_calls"] == 1
    assert summary["context"]["tokens"]["input"] == 20
    assert "elapsed_s" in summary["context"]


async def test_a_failed_run_logs_one_error_line(log_lines):
    caller = FakeModelCaller(reply(text("No."), stop_reason="refusal"))
    async with ApiRuntime(make_settings(), model_caller=caller, pool=FakePool()) as rt:
        with pytest.raises(StopReasonError):
            await rt.send("Weather in Berlin?")
    (failure,) = named(log_lines(), "run failed")
    assert failure["level"] == "error"
    assert failure["context"]["stop_reason"] == "refusal"
    assert "refusal" in failure["context"]["error"]


async def test_a_dropped_resource_logs_a_warning(log_lines):
    invented = {"kind": "url", "url": "https://example.com", "title": "Invented page"}
    caller = FakeModelCaller(answer_reply(resources=[invented]))
    async with ApiRuntime(make_settings(), model_caller=caller, pool=FakePool()) as rt:
        await rt.send("Weather in Berlin?")
    (warning,) = named(log_lines(), "resource dropped")
    assert warning["level"] == "warning"
    assert warning["context"]["resource"]["url"] == "https://example.com"


async def test_a_server_that_failed_to_open_logs_a_warning(log_lines):
    pool = FakePool([], failures={"open-meteo": McpClientError("open-meteo", "spawn failed")})
    async with ApiRuntime(make_settings(), model_caller=FakeModelCaller(), pool=pool):
        pass
    (warning,) = named(log_lines(), "MCP server failed to open")
    assert warning["level"] == "warning"
    assert warning["context"]["server"] == "open-meteo"
    assert "spawn failed" in warning["context"]["reason"]
