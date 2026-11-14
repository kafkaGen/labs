"""The slice of the Messages API the loop calls. `AsyncAnthropic().messages` satisfies it."""

from collections.abc import Iterable
from typing import Protocol

from anthropic.types import CacheControlEphemeralParam, Message, MessageParam, ToolParam

__all__ = ["MessagesApi"]


class MessagesApi(Protocol):
    """A non-streaming `messages.create`. Tests pass a scripted fake."""

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: Iterable[ToolParam],
        messages: Iterable[MessageParam],
        cache_control: CacheControlEphemeralParam,
    ) -> Message: ...
