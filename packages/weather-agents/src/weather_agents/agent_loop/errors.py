"""The one error a run raises when it cannot produce an answer."""

__all__ = ["RunError"]


class RunError(Exception):
    """A run ended without an answer. The underlying API or tool error, if any, is `__cause__`.

    Args:
        message: What went wrong, in one sentence.
        stop_reason: The model's stop reason, when the model stopped other than on `end_turn`.
        tool: The tool's name, when a tool call raised.
    """

    def __init__(
        self, message: str, *, stop_reason: str | None = None, tool: str | None = None
    ) -> None:
        super().__init__(message)
        self.stop_reason = stop_reason
        self.tool = tool
