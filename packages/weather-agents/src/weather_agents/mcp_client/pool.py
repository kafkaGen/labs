"""Opens every server in an `mcpServers` file and routes calls to them by name."""

from collections.abc import Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import Self

from mcp import Client
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    Tool,
)

from weather_agents.mcp_client.config import StdioServerConfig, load_config
from weather_agents.mcp_client.errors import McpClientError
from weather_agents.mcp_client.session import ClientFactory, McpSession

__all__ = ["McpClientPool"]


class McpClientPool:
    """A set of open MCP sessions, one per configured server.

    A server that fails to open is recorded in `failures` and the others still open, so one
    broken server does not stop the chat. Open and close the pool in the same task. An exception
    raised in the `async with` body that is not a `McpClientError` leaves the pool wrapped in one
    `ExceptionGroup` per open server, because the SDK client runs a task group.

    Tool names are not merged or prefixed across servers. Every call names its server, and the
    agent loop decides how to present tools to the model.

    Args:
        servers: The servers to open, by name.
        client_factory: Builds each SDK client. Tests pass a fake.
    """

    def __init__(
        self,
        servers: Mapping[str, StdioServerConfig],
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        self._servers = dict(servers)
        self._client_factory = client_factory
        self._sessions: dict[str, McpSession] = {}
        self._stack = AsyncExitStack()
        self.failures: dict[str, McpClientError] = {}

    @classmethod
    def from_file(cls, path: Path, *, client_factory: ClientFactory = Client) -> Self:
        """Build a pool from an `mcpServers` file.

        Raises:
            ConfigError: The file or one of its entries is unusable.
        """
        return cls(load_config(path), client_factory=client_factory)

    @property
    def server_names(self) -> list[str]:
        """The servers that opened, in the file's order."""
        return list(self._sessions)

    async def __aenter__(self) -> Self:
        self._sessions.clear()
        self.failures.clear()
        async with AsyncExitStack() as stack:
            for name, config in self._servers.items():
                session = McpSession(name, config, client_factory=self._client_factory)
                try:
                    self._sessions[name] = await stack.enter_async_context(session)
                except McpClientError as error:
                    self.failures[name] = error
            # Sessions stay open past this block. `pop_all` hands them to the pool's own stack.
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._sessions.clear()
        return await self._stack.__aexit__(exc_type, exc, tb)

    async def list_tools(self, server: str) -> list[Tool]:
        """List every tool on one server.

        Args:
            server: The server's name in the `mcpServers` file.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).list_tools()

    async def list_resources(self, server: str) -> list[Resource]:
        """List every resource on one server.

        Args:
            server: The server's name in the `mcpServers` file.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).list_resources()

    async def list_resource_templates(self, server: str) -> list[ResourceTemplate]:
        """List every resource template on one server.

        Args:
            server: The server's name in the `mcpServers` file.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).list_resource_templates()

    async def list_prompts(self, server: str) -> list[Prompt]:
        """List every prompt on one server.

        Args:
            server: The server's name in the `mcpServers` file.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).list_prompts()

    async def call_tool(
        self, server: str, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Call a tool on one server.

        A result with `is_error=True` is a normal return, not an exception.

        Args:
            server: The server's name in the `mcpServers` file.
            name: The tool name on that server.
            arguments: Optional JSON arguments for the tool.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).call_tool(name, arguments)

    async def read_resource(self, server: str, uri: str) -> ReadResourceResult:
        """Read a resource on one server.

        Args:
            server: The server's name in the `mcpServers` file.
            uri: The resource URI.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).read_resource(uri)

    async def get_prompt(
        self, server: str, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        """Fetch a prompt on one server.

        Args:
            server: The server's name in the `mcpServers` file.
            name: The prompt name on that server.
            arguments: Optional prompt arguments.

        Raises:
            McpClientError: The server is unknown, failed to open, or the call failed.
        """
        return await self._session(server).get_prompt(name, arguments)

    def _session(self, server: str) -> McpSession:
        if server in self._sessions:
            return self._sessions[server]
        if server in self.failures:
            raise self.failures[server]
        raise McpClientError(server, "no such server")
