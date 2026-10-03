"""One MCP server, reached through one SDK client."""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, contextmanager
from types import TracebackType
from typing import Protocol, Self

from mcp import Client, MCPError, StdioServerParameters
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    Tool,
)
from pydantic import ValidationError

from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.mcp_client.errors import McpClientError

__all__ = ["ClientFactory", "McpSession", "SdkClient"]


class SdkClient(Protocol):
    """The part of `mcp.Client` the session uses. Tests satisfy it with a fake."""

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult: ...

    async def list_resources(self, *, cursor: str | None = None) -> ListResourcesResult: ...

    async def list_resource_templates(
        self, *, cursor: str | None = None
    ) -> ListResourceTemplatesResult: ...

    async def list_prompts(self, *, cursor: str | None = None) -> ListPromptsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...

    async def read_resource(self, uri: str) -> ReadResourceResult: ...

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult: ...


# Called as `factory(params, mode="legacy")`. The default is the SDK's own `Client` class.
type ClientFactory = Callable[..., AbstractAsyncContextManager[SdkClient]]


class McpSession:
    """An open connection to one stdio server.

    Use it as an async context manager. Open and close it in the same task, because the SDK's
    client runs a task group.

    Args:
        name: The server's name in the `mcpServers` file. Every error names it.
        config: How to start the server.
        client_factory: Builds the SDK client. Tests pass a fake.
    """

    def __init__(
        self,
        name: str,
        config: StdioServerConfig,
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        self.name = name
        self._config = config
        self._client_factory = client_factory
        self._stack = AsyncExitStack()
        self._client: SdkClient | None = None

    async def __aenter__(self) -> Self:
        params = StdioServerParameters(
            command=self._config.command, args=self._config.args, env=self._config.env
        )
        try:
            # Legacy mode is pinned by ADR-0003. No handlers are passed, so the SDK declares
            # no client capabilities.
            self._client = await self._stack.enter_async_context(
                self._client_factory(params, mode="legacy")
            )
        except (OSError, MCPError, ExceptionGroup) as error:
            raise McpClientError(self.name, _open_failure(error, self._config.command)) from error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._client = None
        try:
            return await self._stack.__aexit__(exc_type, exc, tb)
        except ExceptionGroup as group:
            # The SDK client runs a task group, which wraps whatever escapes the `async with`
            # body. When the group holds only our own errors, hand the first one back as it was
            # raised, so `except McpClientError` works around the `async with`.
            ours, rest = group.split(McpClientError)
            if ours is None or rest is not None:
                raise
            leaf = _root_cause(ours)
            raise leaf from leaf.__cause__

    async def list_tools(self) -> list[Tool]:
        """List every tool, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Tool], str | None]:
            page = await client.list_tools(cursor=cursor)
            return page.tools, page.next_cursor

        return await self._collect("list_tools", fetch)

    async def list_resources(self) -> list[Resource]:
        """List every fixed resource, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Resource], str | None]:
            page = await client.list_resources(cursor=cursor)
            return page.resources, page.next_cursor

        return await self._collect("list_resources", fetch)

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        """List every resource template, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[ResourceTemplate], str | None]:
            page = await client.list_resource_templates(cursor=cursor)
            return page.resource_templates, page.next_cursor

        return await self._collect("list_resource_templates", fetch)

    async def list_prompts(self) -> list[Prompt]:
        """List every prompt, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Prompt], str | None]:
            page = await client.list_prompts(cursor=cursor)
            return page.prompts, page.next_cursor

        return await self._collect("list_prompts", fetch)

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Call a tool.

        Returns:
            The SDK result as it is. A result with `is_error=True` is a normal return, because
            the agent loop feeds it back to the model.

        Raises:
            McpClientError: The call failed at the protocol level, for example a dropped session.
        """
        client = self._open_client()
        with self._named(f"call_tool '{name}'"):
            return await client.call_tool(name, arguments)

    async def read_resource(self, uri: str) -> ReadResourceResult:
        """Read a resource by URI."""
        client = self._open_client()
        with self._named(f"read_resource '{uri}'"):
            return await client.read_resource(uri)

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        """Get a prompt by name."""
        client = self._open_client()
        with self._named(f"get_prompt '{name}'"):
            return await client.get_prompt(name, arguments)

    def _open_client(self) -> SdkClient:
        if self._client is None:
            raise McpClientError(self.name, "session is not open")
        return self._client

    @contextmanager
    def _named(self, operation: str) -> Iterator[None]:
        try:
            yield
        except (MCPError, RuntimeError, ValidationError) as error:
            # The SDK raises RuntimeError for a result that misses or breaks the tool's output
            # schema, and ValidationError for a result that breaks the protocol.
            detail = error.message if isinstance(error, MCPError) else str(error)
            raise McpClientError(self.name, f"{operation} failed: {detail}") from error

    async def _collect[T](
        self,
        operation: str,
        fetch: Callable[[str | None], Awaitable[tuple[list[T], str | None]]],
    ) -> list[T]:
        items: list[T] = []
        cursor: str | None = None
        with self._named(operation):
            while True:
                page, cursor = await fetch(cursor)
                items.extend(page)
                if cursor is None:
                    return items


def _root_cause(error: BaseException) -> BaseException:
    # The SDK client's task group wraps failures in nested ExceptionGroups, on entering and on
    # leaving. Take the first leaf.
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def _open_failure(error: BaseException, command: str) -> str:
    root = _root_cause(error)
    if isinstance(root, OSError):
        return f"could not start '{command}': {root.strerror or root}"
    if isinstance(root, MCPError):
        return f"could not connect: {root.message}"
    return f"could not connect: {root!r}"
