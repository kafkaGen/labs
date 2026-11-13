"""Errors a run raises. Each one is meant to be caught by the caller."""

from enum import StrEnum

from weather_agents.agent_loop.usage import TokenUsage

__all__ = ["ConfigurationError", "RunError", "RunLimit", "UnknownSessionError"]


class RunLimit(StrEnum):
    """A per-request limit that can stop a run."""

    USD_CAP = "USD cap"
    DEADLINE = "deadline"


class RunError(Exception):
    """A run stopped without an answer.

    Exactly one of `stop_reason` and `limit` is set: the model's stop reason when the model
    stopped the run, or the limit that stopped it.

    Args:
        stop_reason: The model's stop reason, such as `max_tokens` or `refusal`.
        limit: The limit that stopped the run.
        detail: Extra explanation for the message.
        usage: Tokens used by the request so far.
        cost_usd: What the request cost so far.
        partial_text: Any answer text the model wrote before the run stopped.

    A runtime that holds sessions sets `session_id`, so the caller can continue the session
    the failed request belonged to.
    """

    def __init__(
        self,
        *,
        stop_reason: str | None = None,
        limit: RunLimit | None = None,
        detail: str = "",
        usage: TokenUsage | None = None,
        cost_usd: float = 0.0,
        partial_text: str = "",
    ) -> None:
        if (stop_reason is None) == (limit is None):
            raise ValueError("RunError needs exactly one of stop_reason and limit")
        cause = f"stop reason '{stop_reason}'" if limit is None else f"the {limit} was reached"
        message = f"run stopped: {cause}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.stop_reason = stop_reason
        self.limit = limit
        self.usage = usage if usage is not None else TokenUsage()
        self.cost_usd = cost_usd
        self.partial_text = partial_text
        self.session_id: str | None = None


class ConfigurationError(Exception):
    """A run cannot start with the given settings. Raised before any model call."""


class UnknownSessionError(Exception):
    """A session id the runtime does not hold. Raised before any model call.

    Args:
        session_id: The id the caller sent.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(f"unknown session id '{session_id}'")
        self.session_id = session_id
