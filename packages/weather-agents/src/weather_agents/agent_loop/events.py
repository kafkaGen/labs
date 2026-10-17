"""Events the loop yields while it runs. A non-streamed run reads them and keeps the last."""

from dataclasses import dataclass

from anthropic.types import MessageParam

from weather_agents.agent_loop.result import RunResult, TokenUsage

__all__ = ["Event", "ModelTurn", "RunFinished", "ToolCallFinished", "ToolCallStarted"]


# Dataclasses, not pydantic: `RunFinished.messages` holds the SDK's TypedDicts unvalidated.
@dataclass(frozen=True, slots=True)
class ModelTurn:
    """One model call came back. `usage` is the run's running total."""

    step: int
    stop_reason: str | None
    usage: TokenUsage
    tool_uses: list[str]


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    """A tool call the model asked for is about to run."""

    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCallFinished:
    """A tool call returned."""

    id: str
    name: str
    is_error: bool
    content: str


@dataclass(frozen=True, slots=True)
class RunFinished:
    """The run's last event. `messages` is the whole conversation, the answer included."""

    result: RunResult
    messages: list[MessageParam]


Event = ModelTurn | ToolCallStarted | ToolCallFinished | RunFinished
