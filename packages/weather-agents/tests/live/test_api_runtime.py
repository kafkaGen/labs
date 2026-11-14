"""F1 against the real Claude API and the real MCP server over stdio. Costs a fraction of a cent."""

from collections.abc import Iterable

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    Message,
    MessageParam,
    ToolParam,
    ToolUseBlock,
)

from weather_agents.runtimes import ApiRuntime
from weather_agents.settings import load_settings

pytestmark = [pytest.mark.live, pytest.mark.anyio]


class RecordingMessages:
    """Passes every call to the real API and keeps every response."""

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client
        self.responses: list[Message] = []

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: Iterable[ToolParam],
        messages: Iterable[MessageParam],
        cache_control: CacheControlEphemeralParam,
    ) -> Message:
        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            cache_control=cache_control,
        )
        self.responses.append(response)
        return response

    def tools_called(self) -> set[str]:
        # A run that reached end_turn sent the model a result for every one of these calls.
        return {
            block.name
            for response in self.responses
            for block in response.content
            if isinstance(block, ToolUseBlock)
        }


async def test_a_weather_question_is_answered_from_mcp_tool_results():
    settings = load_settings()
    async with AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value()) as client:
        api = RecordingMessages(client)
        async with ApiRuntime(settings, messages_api=api) as runtime:
            result = await runtime.send("what's the weather in Lviv tomorrow?")

    assert result.answer.strip()
    assert result.session_id
    called = api.tools_called()
    assert "open-meteo__forecast" in called, called
    print(f"\ntools: {sorted(called)}\nanswer: {result.answer}")
