"""The seam between the loop and whatever supplies its tools."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

__all__ = ["ToolOutcome", "ToolProvider", "ToolSpec"]


class ToolSpec(BaseModel):
    """One tool as the model sees it."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str | None = None
    input_schema: dict[str, object]


class ToolOutcome(BaseModel):
    """What a tool returned, as text. `is_error` means the tool itself reported a failure."""

    model_config = ConfigDict(frozen=True)

    text: str
    is_error: bool = False


class ToolProvider(Protocol):
    """Lists and calls tools. The loop knows tools only through this."""

    async def list_tools(self) -> list[ToolSpec]:
        """Every tool to offer the model, in a stable order."""
        ...

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Call one tool.

        Returns:
            The outcome. A tool's own failure is an outcome with `is_error=True`.

        Raises:
            Exception: The call could not be made at all. The loop ends the run.
        """
        ...
