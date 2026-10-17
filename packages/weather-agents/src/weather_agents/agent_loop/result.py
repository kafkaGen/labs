"""What a finished run reports: the answer, the session, and the tokens it took."""

from typing import Self

from anthropic.types import Usage
from pydantic import BaseModel, ConfigDict

from weather_agents.agent_loop.answer import Answer

__all__ = ["RunResult", "TokenUsage"]


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
