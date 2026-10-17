"""Fakes and builders for the agent loop and runtime tests."""

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
