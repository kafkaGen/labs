from typing import cast

import anthropic
import httpx2
import pytest
from anthropic import AsyncAnthropic, omit

from tests.agent_loop.fakes import FORECAST, answer_reply, make_settings
from weather_agents.agent_loop import ApiCallError, ModelRequest, ToolSpec
from weather_agents.agent_loop.model import ANSWER_SCHEMA, FAST_MODE_BETA, AnthropicModelCaller

pytestmark = pytest.mark.anyio

SCHEMA: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}
REQUEST = ModelRequest(
    system="Be brief.",
    messages=[{"role": "user", "content": "Weather in Berlin?"}],
    tools=[ToolSpec(name=FORECAST, description="Forecast", input_schema=SCHEMA)],
)
API_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeStream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def get_final_message(self):
        return self.message


class FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeStream(self.outcome)


class FakeSdkClient:
    def __init__(self, outcome):
        self.messages = FakeMessages(outcome)


def caller_over(client: FakeSdkClient, **overrides: object) -> AnthropicModelCaller:
    return AnthropicModelCaller(cast(AsyncAnthropic, client), make_settings(**overrides))


async def test_the_request_carries_strict_tools_the_answer_schema_effort_and_thinking():
    client = FakeSdkClient(answer_reply())
    message = await caller_over(client).call(REQUEST)
    assert message.stop_reason == "end_turn"
    (kwargs,) = client.messages.calls
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["max_tokens"] == 32_000
    assert kwargs["system"] == "Be brief."
    assert kwargs["messages"] == REQUEST.messages
    assert kwargs["tools"] == [
        {"name": FORECAST, "description": "Forecast", "input_schema": SCHEMA, "strict": True}
    ]
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
    }
    assert kwargs["speed"] is omit
    assert kwargs["extra_headers"] is None
    assert "output_format" not in kwargs


async def test_no_tools_sends_no_tools_field():
    client = FakeSdkClient(answer_reply())
    await caller_over(client).call(ModelRequest(system="s", messages=REQUEST.messages, tools=[]))
    assert client.messages.calls[0]["tools"] is omit


async def test_thinking_off_and_fast_mode_on_change_the_request():
    client = FakeSdkClient(answer_reply())
    await caller_over(client, thinking=False, fast_mode=True, effort="high").call(REQUEST)
    (kwargs,) = client.messages.calls
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["speed"] == "fast"
    assert kwargs["extra_headers"] == {"anthropic-beta": FAST_MODE_BETA}
    assert kwargs["output_config"]["effort"] == "high"


async def test_an_api_status_error_becomes_an_api_call_error():
    error = anthropic.BadRequestError(
        "fast mode is not supported",
        response=httpx2.Response(400, request=API_REQUEST),
        body=None,
    )
    with pytest.raises(ApiCallError, match="400") as caught:
        await caller_over(FakeSdkClient(error)).call(REQUEST)
    assert caught.value.status_code == 400
    assert caught.value.__cause__ is error


async def test_a_connection_error_becomes_an_api_call_error_without_a_status():
    error = anthropic.APIConnectionError(request=API_REQUEST)
    with pytest.raises(ApiCallError, match="Connection error") as caught:
        await caller_over(FakeSdkClient(error)).call(REQUEST)
    assert caught.value.status_code is None
