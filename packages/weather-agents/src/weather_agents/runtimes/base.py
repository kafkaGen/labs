"""The interface every agent runtime offers the CLI."""

from types import TracebackType
from typing import Protocol, Self

from weather_agents.agent_loop import RunResult

__all__ = ["AgentRuntime", "SessionNotFoundError"]


class SessionNotFoundError(Exception):
    """A request named a session the runtime does not hold.

    Args:
        session_id: The id that was asked for.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(f"no session '{session_id}'")
        self.session_id = session_id


class AgentRuntime(Protocol):
    """Answers questions in sessions. Open and close it in the same task."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def send(self, question: str, session_id: str | None = None) -> RunResult:
        """Answer a question, in a new session when `session_id` is `None`.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
            RunError: The run stopped without an answer. Its `session_id` is set.
        """
        ...

    async def clear(self, session_id: str) -> None:
        """Forget one session.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
        """
        ...

    async def close(self) -> None:
        """Forget every session and release what the runtime holds."""
        ...
