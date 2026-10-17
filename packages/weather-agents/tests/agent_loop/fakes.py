"""Fakes and builders for the agent loop and runtime tests."""

import asyncio
import json
from typing import cast

from anthropic.types import (
    ContentBlock,
    Message,
    MessageParam,
    StopReason,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)

from weather_agents.agent_loop import ModelRequest, ToolOutcome, ToolSpec
from weather_agents.settings import Settings

FORECAST = "open-meteo__forecast"
BERLIN: dict[str, object] = {"latitude": 52.52, "longitude": 13.41}


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore `.env` and carry a dummy API key."""
    return Settings(_env_file=None, anthropic_api_key="test-key", **overrides)


def usage(input_tokens: int = 10, output_tokens: int = 5) -> Usage:
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def text(value: str) -> TextBlock:
    return TextBlock(type="text", text=value)


def tool_use(block_id: str, name: str, arguments: dict[str, object]) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=block_id, name=name, input=arguments)


def thinking(value: str, signature: str = "sig") -> ThinkingBlock:
    return ThinkingBlock(type="thinking", thinking=value, signature=signature)


def reply(*content: ContentBlock, stop_reason: StopReason = "end_turn") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-haiku-5-5",
        content=list(content),
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=usage(),
    )


def answer_reply(
    answer: str = "Sunny and 21 °C.", resources: list[dict[str, str]] | None = None
) -> Message:
    return reply(text(json.dumps({"answer": answer, "resources": resources or []})))


def content_of(message: MessageParam) -> list[dict[str, object]]:
    """A message's content blocks as plain dicts, for assertions."""
    return cast(list[dict[str, object]], message["content"])


class FakeModelCaller:
    """Returns scripted replies in order, or raises the scripted exception, and records requests."""

    def __init__(self, *replies: Message | Exception) -> None:
        self._replies = list(replies)
        self.requests: list[ModelRequest] = []

    async def call(self, request: ModelRequest) -> Message:
        self.requests.append(request)
        next_reply = self._replies.pop(0)
        if isinstance(next_reply, Exception):
            raise next_reply
        return next_reply


class FakeToolProvider:
    """Returns scripted outcomes by tool name.

    With `barrier=n`, each call waits until n calls are in flight at once, and gives up after two
    seconds. Calls made one after another never get there, so they time out.
    """

    def __init__(
        self, outcomes: dict[str, ToolOutcome | Exception] | None = None, *, barrier: int = 0
    ) -> None:
        self.outcomes = outcomes or {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._barrier = barrier
        self._arrived = 0
        self._all_arrived = asyncio.Event()

    async def list_tools(self) -> list[ToolSpec]:
        schema: dict[str, object] = {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        return [ToolSpec(name=name, description=name, input_schema=schema) for name in self.outcomes]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        self.calls.append((name, arguments))
        if self._barrier:
            self._arrived += 1
            if self._arrived >= self._barrier:
                self._all_arrived.set()
            await asyncio.wait_for(self._all_arrived.wait(), timeout=2)
        outcome = self.outcomes.get(name, ToolOutcome(content=f"{name} ok"))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
