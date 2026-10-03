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
from weather_agents.mcp_client.errors import ConfigError, McpClientError
from weather_agents.mcp_client.session import ClientFactory, McpSession

__all__ = ["TOOL_SEPARATOR", "McpClientPool"]

# Joins a server name to a tool name in the names the model sees: `open-meteo__forecast`.
TOOL_SEPARATOR = "__"


class McpClientPool:
    """A set of open MCP sessions, one per configured server.

    A server that fails to open is recorded in `failures` and the others still open, so one
    broken server does not stop the chat. Open and close the pool in the same task. An exception
    raised in the `async with` body that is not a `McpClientError` leaves the pool wrapped in one
    `ExceptionGroup` per open server, because the SDK client runs a task group.

    The per-server methods take the server first. For a model, `list_all_tools` returns every
    open server's tools named `<server>__<tool>`, and `call_namespaced_tool` takes that name back
    and finds the server in it, so the model never sees the server as a separate argument.

    Args:
        servers: The servers to open, by name. A name may not contain `__`.
        client_factory: Builds each SDK client. Tests pass a fake.

    Raises:
        ConfigError: A server name contains `__`, which would make a prefixed tool name ambiguous.
    """

    def __init__(
        self,
        servers: Mapping[str, StdioServerConfig],
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        for name in servers:
            if TOOL_SEPARATOR in name:
                raise ConfigError(f"server '{name}': the name may not contain '{TOOL_SEPARATOR}'")
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

    async def list_all_tools(self) -> list[Tool]:
        """List the tools of every open server, named `<server>__<tool>` for the model.

        Each tool is a copy of the SDK's `Tool` with only `name` changed, so `input_schema` is
        still the server's JSON Schema. A server that failed to open adds nothing here. See
        `failures`. The model's provider may limit tool names to a length or a character set.
        This method does not check that.

        Raises:
            McpClientError: A call to one of the open servers failed.
        """
        tools: list[Tool] = []
        for server in self._sessions:
            for tool in await self._session(server).list_tools():
                prefixed = f"{server}{TOOL_SEPARATOR}{tool.name}"
                tools.append(tool.model_copy(update={"name": prefixed}))
        return tools

    async def call_namespaced_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Call the tool a model asked for by its `<server>__<tool>` name.

        The name splits at the first `__`, so a tool name may hold `__` and a server name may not.
        A result with `is_error=True` is a normal return, not an exception.

        Args:
            name: A name from `list_all_tools`.
            arguments: Optional JSON arguments for the tool.

        Raises:
            McpClientError: The name has no server or no tool part, the server is unknown or
                failed to open, or the call failed.
        """
        server, separator, tool = name.partition(TOOL_SEPARATOR)
        if not separator or not tool:
            raise McpClientError(name, f"tool name must look like <server>{TOOL_SEPARATOR}<tool>")
        return await self._session(server).call_tool(tool, arguments)

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
