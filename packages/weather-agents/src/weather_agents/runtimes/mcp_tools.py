"""MCP tools as the agent loop's tool provider."""

import json
from types import TracebackType
from typing import Protocol, Self

import anthropic
from mcp.types import CallToolResult, TextContent, Tool

from weather_agents.agent_loop import ToolOutcome, ToolSpec
from weather_agents.mcp_client import McpClientError

__all__ = ["McpToolProvider", "ToolPool"]


class ToolPool(Protocol):
    """The part of `McpClientPool` the API runtime uses."""

    failures: dict[str, McpClientError]

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...

    async def list_all_tools(self) -> list[Tool]: ...

    async def call_namespaced_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...


class McpToolProvider:
    """Offers every open server's tools to the model and runs them through the pool.

    Strict mode rejects keywords the Open-Meteo server uses, such as `minimum` and `pattern`.
    `transform_schema` moves them into each property's description, and the server still
    enforces them.

    Args:
        pool: An open pool.
    """

    def __init__(self, pool: ToolPool) -> None:
        self._pool = pool

    async def list_tools(self) -> list[ToolSpec]:
        """Return every open server's tools, named `<server>__<tool>`, with strict schemas.

        Raises:
            McpClientError: Listing failed on an open server.
        """
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=anthropic.transform_schema(tool.input_schema),
            )
            for tool in await self._pool.list_all_tools()
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Run one tool. A client failure becomes an error outcome naming the server."""
        try:
            result = await self._pool.call_namespaced_tool(name, arguments)
        except McpClientError as error:
            return ToolOutcome(content=str(error), is_error=True)
        texts = [block.text for block in result.content if isinstance(block, TextContent)]
        content = "\n".join(texts) if texts else json.dumps(result.structured_content)
        return ToolOutcome(content=content, is_error=result.is_error)
