"""Stand-ins for the Messages API and a tool provider, so loop tests need no network."""

import asyncio
from collections.abc import Iterable, Mapping
from itertools import count

from anthropic.types import CacheControlEphemeralParam, Message, MessageParam, ToolParam

from weather_agents.agent_loop import ToolOutcome, ToolSpec

_ids = count(1)


def text_reply(text: str, *, stop_reason: str = "end_turn") -> Message:
    """A model turn holding one text block."""
    return _message([{"type": "text", "text": text}], stop_reason)


def tool_reply(
    *calls: tuple[str, Mapping[str, object]],
    thinking: bool = False,
    stop_reason: str = "tool_use",
) -> Message:
    """A model turn asking for each `(name, arguments)` call, ids `toolu_<n>` in order."""
    blocks: list[dict[str, object]] = []
    if thinking:
        blocks.append({"type": "thinking", "thinking": "", "signature": "sig-abc"})
    for name, arguments in calls:
        blocks.append(
            {"type": "tool_use", "id": f"toolu_{next(_ids)}", "name": name, "input": arguments}
        )
    return _message(blocks, stop_reason)


def _message(content: list[dict[str, object]], stop_reason: str) -> Message:
    return Message.model_validate(
        {
            "id": f"msg_{next(_ids)}",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )


class ScriptedMessages:
    """Returns queued replies in order and records each request.

    A queued exception is raised instead of returned. Each recorded request holds a copy of
    the message list as it was sent, because the loop keeps appending to its own list.
    """

    def __init__(self, *replies: Message | Exception) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, object]] = []

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
        self.requests.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "tools": list(tools),
                "messages": list(messages),
                "cache_control": cache_control,
            }
        )
        if not self._replies:
            raise AssertionError("the loop made more model calls than the test scripted")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeTools:
    """A tool provider with canned outcomes, optional delays, and optional failures.

    Args:
        outcomes: By tool name, the outcome to return or the exception to raise.
        delay: Seconds each call sleeps before answering.
    """

    def __init__(
        self,
        outcomes: Mapping[str, ToolOutcome | Exception],
        *,
        delay: float = 0.0,
    ) -> None:
        self._outcomes = dict(outcomes)
        self._delay = delay
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.cancelled: list[str] = []

    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name=name, description=f"The {name} tool.", input_schema={"type": "object"})
            for name in self._outcomes
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        self.calls.append((name, arguments))
        try:
            await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            self.cancelled.append(name)
            raise
        outcome = self._outcomes[name]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
