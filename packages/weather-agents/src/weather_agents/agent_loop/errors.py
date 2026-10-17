"""Errors a run raises. Each carries what the run had spent and said before it stopped."""

from weather_agents.agent_loop.result import TokenUsage

__all__ = ["ApiCallError", "InvalidAnswerError", "RunError", "StopReasonError"]


class RunError(Exception):
    """A run stopped without an answer.

    The loop fills in `usage` with the run's totals so far. The runtime fills in `session_id`
    before the caller sees the error.

    Args:
        message: What went wrong, in one sentence.
        usage: Tokens spent before the failure.
        partial_text: The text of the last assistant reply, if any.
    """

    def __init__(
        self, message: str, *, usage: TokenUsage | None = None, partial_text: str = ""
    ) -> None:
        super().__init__(message)
        self.usage = usage if usage is not None else TokenUsage()
        self.partial_text = partial_text
        self.session_id = ""


class StopReasonError(RunError):
    """The model stopped for a reason the loop does not continue on, such as `max_tokens`."""

    def __init__(
        self, stop_reason: str, *, usage: TokenUsage | None = None, partial_text: str = ""
    ) -> None:
        super().__init__(
            f"the model stopped with '{stop_reason}'", usage=usage, partial_text=partial_text
        )
        self.stop_reason = stop_reason


class InvalidAnswerError(RunError):
    """The model ended its turn with text that is not a valid answer."""


class ApiCallError(RunError):
    """The SDK raised, after its own retries. `status_code` is `None` for a connection error."""

    def __init__(
        self, message: str, *, status_code: int | None, usage: TokenUsage | None = None
    ) -> None:
        super().__init__(message, usage=usage)
        self.status_code = status_code
