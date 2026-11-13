"""A scripted Messages API and a scripted tool provider, so loop tests need no network."""

import asyncio
import json
import time
from collections.abc import Sequence
from typing import Any

from anthropic.types import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)

from weather_agents.agent_loop.tools import ToolOutcome, ToolSpec

MODEL = "claude-haiku-5-5"


def usage(input_tokens: int = 100, output_tokens: int = 20) -> Usage:
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def message(
    *content: TextBlock | ToolUseBlock | ThinkingBlock,
    stop_reason: str = "end_turn",
    tokens: Usage | None = None,
) -> Message:
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=MODEL,
        content=list(content),
        stop_reason=stop_reason,  # ty: ignore[invalid-argument-type]
        stop_sequence=None,
        usage=tokens or usage(),
    )


def text(value: str) -> TextBlock:
    return TextBlock(type="text", text=value)


def thinking(signature: str = "sig-1") -> ThinkingBlock:
    return ThinkingBlock(type="thinking", thinking="", signature=signature)


def tool_use(tool_use_id: str, name: str, arguments: dict[str, object]) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=tool_use_id, name=name, input=arguments)


def answer_json(answer: str = "Sunny, 21 C.", *tool_use_ids: str) -> str:
    resources = [
        {
            "title": f"call {tool_use_id}",
            "source": {"kind": "tool_call", "tool_use_id": tool_use_id},
        }
        for tool_use_id in tool_use_ids
    ]
    return json.dumps({"answer": answer, "resources": resources})


def final(answer: str = "Sunny, 21 C.", *tool_use_ids: str, tokens: Usage | None = None) -> Message:
    return message(text(answer_json(answer, *tool_use_ids)), tokens=tokens)


class FakeMessages:
    """Returns the scripted messages in order and records every request.

    `delay` makes each call wait that many seconds first, to test the deadline.
    """

    def __init__(self, *script: Message, delay: float = 0.0) -> None:
        self.script = list(script)
        self.delay = delay
        # Any, not object: requests are SDK-shaped wire data that assertions index freely.
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: object) -> Message:
        snapshot: dict[str, Any] = dict(kwargs)
        snapshot["messages"] = list(snapshot["messages"])
        self.requests.append(snapshot)
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.script:
            raise AssertionError("the fake API ran out of scripted messages")
        return self.script.pop(0)


class FakeToolProvider:
    """Serves `specs` and answers calls from `outcomes` by tool name.

    A name mapped to an exception raises it. `delay` makes every call wait first. Each call's
    start and end times land in `timings`, to prove calls overlap.
    """

    def __init__(
        self,
        specs: Sequence[ToolSpec] = (),
        outcomes: dict[str, ToolOutcome | Exception] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.specs = list(specs)
        self.outcomes = outcomes if outcomes is not None else {}
        self.delay = delay
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.timings: list[tuple[float, float]] = []

    async def tool_specs(self) -> list[ToolSpec]:
        return list(self.specs)

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        started = time.monotonic()
        self.calls.append((name, arguments))
        if self.delay:
            await asyncio.sleep(self.delay)
        self.timings.append((started, time.monotonic()))
        outcome = self.outcomes.get(name, ToolOutcome(text=f"{name} ok"))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def spec(name: str = "open-meteo__forecast") -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Daily forecast",
        input_schema={
            "type": "object",
            "properties": {"latitude": {"type": "number", "minimum": -90, "maximum": 90}},
            "required": ["latitude"],
        },
    )
