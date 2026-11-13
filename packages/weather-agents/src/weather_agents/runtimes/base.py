"""The contract every agent runtime keeps, so callers never depend on which one runs."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from weather_agents.agent_loop.answer import Resource
from weather_agents.agent_loop.usage import TokenUsage

__all__ = ["AgentResult", "AgentRuntime"]


class AgentResult(BaseModel):
    """One answered question: the answer, its sources, and the session to continue."""

    model_config = ConfigDict(frozen=True)

    answer: str
    resources: list[Resource]
    session_id: str
    usage: TokenUsage
    cost_usd: float


class AgentRuntime(Protocol):
    """Sends questions in sessions, and forgets sessions on demand."""

    async def send(self, question: str, session_id: str | None = None) -> AgentResult:
        """Answer `question`, in a new session when `session_id` is `None`."""
        ...

    async def clear(self, session_id: str) -> None:
        """Forget one session."""
        ...

    async def close(self) -> None:
        """Forget every session and release the runtime's connections."""
        ...
