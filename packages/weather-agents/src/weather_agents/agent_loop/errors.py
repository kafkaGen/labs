"""Errors a run raises. The loop attaches what the run had spent and said before it stopped."""

from anthropic.types import MessageParam

from weather_agents.agent_loop.models import TokenUsage

__all__ = ["ApiCallError", "InvalidAnswerError", "RunError", "StopReasonError"]


class RunError(Exception):
    """A run stopped without an answer.

    The loop fills in `usage` and `messages` before the error leaves it. The runtime fills in
    `session_id` before the caller sees it.

    Args:
        message: What went wrong, in one sentence.
        partial_text: The text of the last assistant reply, if any.

    Attributes:
        usage: Tokens spent before the failure.
        messages: The whole conversation up to the failure: the history, the question, and every
            reply and tool result the run produced.
    """

    def __init__(self, message: str, *, partial_text: str = "") -> None:
        super().__init__(message)
        self.partial_text = partial_text
        self.usage = TokenUsage()
        self.messages: list[MessageParam] = []
        self.session_id = ""


class StopReasonError(RunError):
    """The model stopped for a reason the loop does not continue on, such as `max_tokens`."""

    def __init__(self, stop_reason: str, *, partial_text: str = "") -> None:
        super().__init__(f"the model stopped with '{stop_reason}'", partial_text=partial_text)
        self.stop_reason = stop_reason


class InvalidAnswerError(RunError):
    """The model ended its turn with text that is not a valid answer."""


class ApiCallError(RunError):
    """The SDK raised, after its own retries. `status_code` is `None` for a connection error."""

    def __init__(self, message: str, *, status_code: int | None) -> None:
        super().__init__(message)
        self.status_code = status_code
