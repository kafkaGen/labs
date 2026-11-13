"""Token totals for one request, summed over its model calls."""

from anthropic.types import Usage
from pydantic import BaseModel

__all__ = ["TokenUsage"]


class TokenUsage(BaseModel):
    """Input and output tokens across every model call of one request."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        """Input plus output tokens."""
        return self.input_tokens + self.output_tokens

    def add(self, usage: Usage) -> None:
        """Add one model call's usage."""
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
