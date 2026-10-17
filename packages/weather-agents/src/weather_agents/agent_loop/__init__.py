"""The API runtime's agent loop. It depends on a model caller and a tool provider, not on MCP."""

from weather_agents.agent_loop.answer import Answer, Resource, ToolCallResource, UrlResource
from weather_agents.agent_loop.errors import (
    ApiCallError,
    InvalidAnswerError,
    RunError,
    StopReasonError,
)
from weather_agents.agent_loop.events import (
    Event,
    ModelTurn,
    RunFinished,
    ToolCallFinished,
    ToolCallStarted,
)
from weather_agents.agent_loop.interfaces import (
    ModelCaller,
    ModelRequest,
    ToolOutcome,
    ToolProvider,
    ToolSpec,
)
from weather_agents.agent_loop.ledger import SourceLedger
from weather_agents.agent_loop.loop import run_agent
from weather_agents.agent_loop.model import AnthropicModelCaller
from weather_agents.agent_loop.result import RunResult, TokenUsage

__all__ = [
    "Answer",
    "AnthropicModelCaller",
    "ApiCallError",
    "Event",
    "InvalidAnswerError",
    "ModelCaller",
    "ModelRequest",
    "ModelTurn",
    "Resource",
    "RunError",
    "RunFinished",
    "RunResult",
    "SourceLedger",
    "StopReasonError",
    "TokenUsage",
    "ToolCallFinished",
    "ToolCallResource",
    "ToolCallStarted",
    "ToolOutcome",
    "ToolProvider",
    "ToolSpec",
    "UrlResource",
    "run_agent",
]
