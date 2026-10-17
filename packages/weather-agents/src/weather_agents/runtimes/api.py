"""The API runtime: our own agent loop on the Messages API, with sessions held in memory."""

from types import TracebackType
from typing import Self, cast
from uuid import uuid4

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolResultBlockParam
from labs_logging import bound_context, get_logger

from weather_agents.agent_loop import (
    AnthropicModelCaller,
    ModelCaller,
    RunError,
    RunResult,
    SourceLedger,
    StopReasonError,
    ToolSpec,
    run_agent,
)
from weather_agents.agents import WEATHER_AGENT, AgentDefinition
from weather_agents.mcp_client import McpClientPool
from weather_agents.runtimes.mcp_tools import McpToolProvider, ToolPool
from weather_agents.settings import Settings

__all__ = ["ApiRuntime", "Session", "SessionNotFoundError"]

log = get_logger(__name__)


class SessionNotFoundError(Exception):
    """A request named a session the runtime does not hold.

    Args:
        session_id: The id that was asked for.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(f"no session '{session_id}'")
        self.session_id = session_id


class Session:
    """One conversation: its messages and the sources it touched. Held in memory only."""

    def __init__(self) -> None:
        self.id = uuid4().hex
        self.messages: list[MessageParam] = []
        self.ledger = SourceLedger()


class ApiRuntime:
    """Answers questions with the hand-written loop, the MCP servers' tools, and sessions.

    Open it with `async with`, in the same task that closes it, because the MCP pool requires
    that. Tools are listed once on open and reused for every request.

    Args:
        settings: The model, the MCP config file, and the log truncation length.
        model_caller: Replaces the SDK-backed caller. Tests pass a fake.
        pool: Replaces the pool built from `settings.mcp_config`. Tests pass a fake.
        agent: Supplies the system prompt.

    Raises:
        ConfigError: The MCP config file is unusable.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        model_caller: ModelCaller | None = None,
        pool: ToolPool | None = None,
        agent: AgentDefinition = WEATHER_AGENT,
    ) -> None:
        self._settings = settings
        self._client: AsyncAnthropic | None = None
        if model_caller is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
            model_caller = AnthropicModelCaller(self._client, settings)
        self._caller = model_caller
        self._pool: ToolPool = (
            pool if pool is not None else McpClientPool.from_file(settings.mcp_config)
        )
        self._tools = McpToolProvider(self._pool)
        self._agent = agent
        self._tool_specs: list[ToolSpec] = []
        self._sessions: dict[str, Session] = {}
        self._is_open = False

    async def __aenter__(self) -> Self:
        await self._pool.__aenter__()
        self._is_open = True
        try:
            for server, error in self._pool.failures.items():
                log.warning("MCP server failed to open", server=server, reason=str(error))
            self._tool_specs = await self._tools.list_tools()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def send(self, question: str, session_id: str | None = None) -> RunResult:
        """Answer a question, in a new session when `session_id` is `None`.

        On a `RunError`, the session keeps everything the run did before it failed, then the
        error as the last thing said. Any other exception leaves the session unchanged.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
            RunError: The run stopped without an answer. Its `session_id` is set.
        """
        session = self._find(session_id) if session_id is not None else self._start()
        with bound_context(session_id=session.id):
            try:
                result, messages = await run_agent(
                    caller=self._caller,
                    tools=self._tools,
                    tool_specs=self._tool_specs,
                    agent=self._agent,
                    settings=self._settings,
                    history=session.messages,
                    question=question,
                    ledger=session.ledger,
                )
            except RunError as error:
                error.session_id = session.id
                session.messages = _after_failure(error)
                log.error(
                    "run failed",
                    error=str(error),
                    stop_reason=error.stop_reason if isinstance(error, StopReasonError) else None,
                    tokens=error.usage.model_dump(),
                )
                raise
        session.messages = messages
        return result.model_copy(update={"session_id": session.id})

    async def clear(self, session_id: str) -> None:
        """Forget one session.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
        """
        if self._sessions.pop(session_id, None) is None:
            raise SessionNotFoundError(session_id)

    async def close(self) -> None:
        """Forget every session, then close the MCP pool and the SDK client. Safe to repeat."""
        self._sessions.clear()
        if self._is_open:
            self._is_open = False
            await self._pool.__aexit__(None, None, None)
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _find(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None

    def _start(self) -> Session:
        session = Session()
        self._sessions[session.id] = session
        return session


def _after_failure(error: RunError) -> list[MessageParam]:
    """The conversation a session keeps after a failed run: what happened, then the error.

    The API rejects a `tool_use` with no `tool_result` after it and rejects an empty assistant
    message, so each is repaired before the error is added. An unanswered tool call is answered
    with the error as an error result. Otherwise the error is an assistant message.
    """
    note = f"The previous request failed: {error}"
    messages = list(error.messages)
    last = messages[-1]
    if last["role"] == "assistant":
        blocks = cast(list[dict[str, object]], last["content"])
        open_calls = [block["id"] for block in blocks if block.get("type") == "tool_use"]
        if open_calls:
            results = [
                ToolResultBlockParam(
                    type="tool_result", tool_use_id=str(call_id), content=note, is_error=True
                )
                for call_id in open_calls
            ]
            messages.append({"role": "user", "content": results})
            return messages
        if not blocks:
            messages.pop()
    messages.append({"role": "assistant", "content": note})
    return messages
