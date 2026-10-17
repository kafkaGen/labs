"""The two seams the loop depends on: one model call, and the tools it may use."""

from dataclasses import dataclass
from typing import Protocol

from anthropic.types import Message, MessageParam
from pydantic import BaseModel, ConfigDict

__all__ = ["ModelCaller", "ModelRequest", "ToolOutcome", "ToolProvider", "ToolSpec"]


class ToolSpec(BaseModel):
    """A tool as the model sees it. `input_schema` is already strict-compatible."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, object]


class ToolOutcome(BaseModel):
    """A tool's result as text, and whether it is an error the model should read."""

    model_config = ConfigDict(frozen=True)

    content: str
    is_error: bool = False


# A dataclass, not pydantic: the SDK's TypedDicts must pass through unvalidated.
@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Everything one model call sends that changes between calls."""

    system: str
    messages: list[MessageParam]
    tools: list[ToolSpec]


class ModelCaller(Protocol):
    """Sends one request and returns the model's final message."""

    async def call(self, request: ModelRequest) -> Message:
        """Send one request.

        Raises:
            ApiCallError: The call failed.
        """
        ...


class ToolProvider(Protocol):
    """Lists the tools the model may call and runs them by name."""

    async def list_tools(self) -> list[ToolSpec]:
        """Return every tool, with strict schemas."""
        ...

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Run one tool. A failure is an error outcome, not an exception."""
        ...
