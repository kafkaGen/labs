"""The API runtime: our MCP tools and the hand-written loop on the Claude Messages API."""

from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self
from uuid import uuid4

from anthropic import AsyncAnthropic
from mcp import Client
from pydantic import BaseModel, ConfigDict

from weather_agents.agent_loop import MessagesApi, run_loop
from weather_agents.agents import WEATHER_SYSTEM_PROMPT
from weather_agents.mcp_client import McpClientPool
from weather_agents.mcp_client.session import ClientFactory
from weather_agents.runtimes.mcp_tools import McpToolProvider
from weather_agents.settings import Settings

__all__ = ["AgentResult", "ApiRuntime"]


class AgentResult(BaseModel):
    """The answer to one question, and the session it belongs to."""

    model_config = ConfigDict(frozen=True)

    answer: str
    session_id: str


class ApiRuntime:
    """Answers weather questions with the MCP servers in `settings.mcp_config`.

    Use it as an async context manager, entered and left in the same task, because the MCP
    sessions require it. Every server in the config opens on entry. One that fails to open is
    skipped and the rest still serve tools.

    Args:
        settings: Model, output cap, MCP config file, and API key.
        messages_api: The Messages API. Tests pass a fake. By default a client is built from
            the settings' key and closed with the runtime.
        mcp_client_factory: Builds each MCP SDK client. Tests pass a fake.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        messages_api: MessagesApi | None = None,
        mcp_client_factory: ClientFactory = Client,
    ) -> None:
        self._settings = settings
        self._messages_api = messages_api
        self._mcp_client_factory = mcp_client_factory
        self._stack = AsyncExitStack()
        self._tools: McpToolProvider | None = None
        self._api: MessagesApi | None = None

    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as stack:
            pool = McpClientPool.from_file(
                self._settings.mcp_config, client_factory=self._mcp_client_factory
            )
            await stack.enter_async_context(pool)
            if self._messages_api is None:
                # The SDK reads only os.environ, and the key may have come from `.env`.
                client = AsyncAnthropic(api_key=self._settings.anthropic_api_key.get_secret_value())
                stack.push_async_callback(client.close)
                self._api = client.messages
            else:
                self._api = self._messages_api
            self._tools = McpToolProvider(pool)
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close every MCP session and the API client. Safe to call twice."""
        self._tools = None
        self._api = None
        await self._stack.aclose()

    async def send(self, question: str) -> AgentResult:
        """Answer one question in a new session.

        Raises:
            RunError: The run could not produce an answer. The runtime stays usable.
            RuntimeError: The runtime is not open.
        """
        if self._tools is None or self._api is None:
            raise RuntimeError("the runtime is not open; use it with 'async with'")
        answer = await run_loop(
            self._api,
            self._tools,
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            system=WEATHER_SYSTEM_PROMPT,
            question=question,
        )
        return AgentResult(answer=answer, session_id=uuid4().hex)
