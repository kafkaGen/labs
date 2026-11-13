"""The API runtime: the hand-written agent loop, with in-memory sessions and MCP tools."""

import uuid
from collections.abc import Mapping
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from labs_logging import bound_context

from weather_agents.agent_loop.errors import RunError, UnknownSessionError
from weather_agents.agent_loop.loop import CreateMessage, run_agent
from weather_agents.agent_loop.tools import ToolProvider
from weather_agents.mcp_client import McpClientPool
from weather_agents.runtimes.base import AgentResult
from weather_agents.runtimes.mcp_tools import McpToolProvider
from weather_agents.settings import Settings

__all__ = ["SYSTEM_PROMPT", "ApiRuntime", "RuntimeNotOpenError"]

# Lives here until the SDK runtime needs the same prompt; then it moves to `agents`.
SYSTEM_PROMPT = """\
You answer weather questions. Use the tools to get the data before you answer, and answer from \
their results, not from memory. If a tool returns an error, read it and correct the call.

Your final answer is JSON that matches the given schema. In `resources`, list every tool call \
and URL your answer is built from, and nothing else. An answer built from tool results always \
has at least one resource. Every tool result starts with `[source id: ...]`: cite \
that tool call by copying the id exactly into `tool_use_id`. Cite a URL exactly as it appeared \
in a tool result. Give each resource a short title."""


class RuntimeNotOpenError(Exception):
    """`send` was called outside `async with ApiRuntime(...)`."""


class ApiRuntime:
    """Answers questions with the agent loop on the Claude API.

    Use it as `async with ApiRuntime(settings) as runtime:`. Entering opens every server in the
    MCP config file, and leaving closes them, in the same task as the MCP client requires.
    Sessions live only in this object's memory and end on `clear`, on `close`, or with the
    process. Two concurrent `send` calls to one session are not supported.

    Args:
        settings: Settings for every run. `send` can override them for one run.
        create_message: Sends one Messages API request. Defaults to an `AsyncAnthropic` client
            built from `settings`. Tests pass a fake.
        tools: Supplies the tools. Defaults to the MCP servers in `settings.mcp_config`.
            Tests pass a fake.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        create_message: CreateMessage | None = None,
        tools: ToolProvider | None = None,
    ) -> None:
        self._settings = settings
        self._create_message = create_message
        self._tools = tools
        self._sessions: dict[str, list[MessageParam]] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        if self._create_message is None:
            key = self._settings.anthropic_api_key
            client = AsyncAnthropic(api_key=key.get_secret_value() if key else None)
            self._stack.push_async_callback(client.close)
            self._create_message = client.messages.create
        if self._tools is None:
            pool = McpClientPool.from_file(self._settings.mcp_config)
            self._tools = McpToolProvider(await self._stack.enter_async_context(pool))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def send(
        self,
        question: str,
        session_id: str | None = None,
        *,
        overrides: Mapping[str, object] | None = None,
    ) -> AgentResult:
        """Answer `question`, continuing `session_id` or starting a new session.

        Args:
            question: The user's question.
            session_id: A session from an earlier result, or `None` for a new one.
            overrides: Settings to change for this run only, such as `{"usd_cap": 0.05}`.

        Raises:
            UnknownSessionError: The runtime holds no session `session_id`. No model call.
            ConfigurationError: The settings cannot run, such as an unpriced model.
            UnknownSettingError: An override names no setting.
            pydantic.ValidationError: An override is invalid.
            RuntimeNotOpenError: The runtime was not entered with `async with`.
            RunError: The run stopped without an answer. Its `session_id` names the session,
                which now holds the question and the error.
        """
        if session_id is not None and session_id not in self._sessions:
            raise UnknownSessionError(session_id)
        if self._create_message is None or self._tools is None:
            raise RuntimeNotOpenError("use the runtime as `async with ApiRuntime(settings)`")
        settings = self._settings.with_overrides(**overrides) if overrides else self._settings
        session_id = session_id or uuid.uuid4().hex
        history = self._sessions.get(session_id, [])
        with bound_context(session_id=session_id):
            try:
                outcome = await run_agent(
                    create_message=self._create_message,
                    tools=self._tools,
                    history=history,
                    question=question,
                    settings=settings,
                    system=SYSTEM_PROMPT,
                )
            except RunError as error:
                # Keep the question and what failed, never the failed request's partial turns.
                self._sessions[session_id] = [
                    *history,
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": f"The request failed: {error}"},
                ]
                error.session_id = session_id
                raise
        self._sessions[session_id] = outcome.messages
        return AgentResult(
            answer=outcome.answer.text,
            resources=outcome.answer.resources,
            session_id=session_id,
            usage=outcome.usage,
            cost_usd=outcome.cost_usd,
        )

    async def clear(self, session_id: str) -> None:
        """Forget one session. Clearing an unknown id does nothing."""
        self._sessions.pop(session_id, None)

    async def close(self) -> None:
        """Forget every session, and close the MCP servers and API client this runtime opened."""
        self._sessions.clear()
        await self._stack.aclose()
