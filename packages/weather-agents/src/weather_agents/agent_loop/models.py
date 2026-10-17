"""The data a run produces: the structured answer, token counts, and the run's result."""

from typing import Annotated, Literal, Self

from anthropic.types import Usage
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Answer", "Resource", "RunResult", "TokenUsage", "ToolCallResource", "UrlResource"]


class UrlResource(BaseModel):
    """A web page the answer relied on."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["url"]
    url: str
    title: str


class ToolCallResource(BaseModel):
    """A tool call whose result the answer relied on.

    `arguments` is JSON text rather than an object, because strict structured output forbids an
    object with free-form keys.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_call"]
    tool: str
    arguments: str
    title: str


Resource = Annotated[UrlResource | ToolCallResource, Field(discriminator="kind")]


class Answer(BaseModel):
    """What the model must return when it finishes."""

    model_config = ConfigDict(frozen=True)

    answer: str
    resources: list[Resource]


class TokenUsage(BaseModel):
    """Token counts summed over every model call in a run."""

    model_config = ConfigDict(frozen=True)

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add(self, usage: Usage) -> Self:
        """Return these totals plus one reply's usage."""
        return self.model_copy(
            update={
                "input": self.input + usage.input_tokens,
                "output": self.output + usage.output_tokens,
                "cache_read": self.cache_read + (usage.cache_read_input_tokens or 0),
                "cache_write": self.cache_write + (usage.cache_creation_input_tokens or 0),
            }
        )


class RunResult(BaseModel):
    """A successful run. `turns` counts model calls."""

    model_config = ConfigDict(frozen=True)

    answer: Answer
    session_id: str
    usage: TokenUsage
    turns: int
    tool_calls: int
