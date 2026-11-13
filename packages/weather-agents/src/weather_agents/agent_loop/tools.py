"""The seam between the loop and whatever supplies its tools.

The loop knows tools only through `ToolProvider`. The API runtime fills it from MCP, and tests fill
it with a fake, so nothing here imports `mcp`.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

__all__ = ["ToolOutcome", "ToolProvider", "ToolSpec"]


class ToolSpec(BaseModel):
    """One tool as the model sees it.

    `input_schema` is a JSON Schema object, passed to the API as the provider gave it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, object]


class ToolOutcome(BaseModel):
    """What one tool call returned, as text for the model.

    `is_error` marks a call that failed or that the tool reported as an error. The loop sends
    both kinds back to the model, so a failed call never stops a run.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    is_error: bool = False


class ToolProvider(Protocol):
    """Lists tools for the model and runs the calls it makes."""

    async def tool_specs(self) -> list[ToolSpec]:
        """Return every tool the model may call in this run."""
        ...

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Run one tool call. A failure should come back as `is_error=True`, not raise."""
        ...
