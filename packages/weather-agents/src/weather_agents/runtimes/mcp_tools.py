"""Adapts an open `McpClientPool` to the loop's `ToolProvider`."""

import json

from mcp.types import CallToolResult, TextContent

from weather_agents.agent_loop import ToolOutcome, ToolSpec
from weather_agents.mcp_client import McpClientPool

__all__ = ["McpToolProvider"]


class McpToolProvider:
    """Offers every open server's tools, named `<server>__<tool>`, and calls them by that name.

    `McpClientError` is not caught here. The loop turns any raised call into a run error.

    Args:
        pool: An open pool. The provider does not open or close it.
    """

    def __init__(self, pool: McpClientPool) -> None:
        self._pool = pool

    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name=tool.name, description=tool.description, input_schema=tool.input_schema)
            for tool in await self._pool.list_all_tools()
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        result = await self._pool.call_namespaced_tool(name, arguments)
        return ToolOutcome(text=_as_text(result), is_error=bool(result.is_error))


def _as_text(result: CallToolResult) -> str:
    # Structured content is the server's own data. Its text blocks are a rendering of it.
    if result.structured_content is not None:
        return json.dumps(result.structured_content, ensure_ascii=False)
    return "\n".join(block.text for block in result.content if isinstance(block, TextContent))
