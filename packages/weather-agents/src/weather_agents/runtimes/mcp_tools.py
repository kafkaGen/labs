"""Fills the loop's `ToolProvider` from the MCP client pool."""

import json

from labs_logging import get_logger
from mcp.types import CallToolResult, TextContent

from weather_agents.agent_loop.tools import ToolOutcome, ToolSpec
from weather_agents.mcp_client import McpClientError, McpClientPool

__all__ = ["McpToolProvider"]

log = get_logger(__name__)


class McpToolProvider:
    """Offers every open server's tools, named `<server>__<tool>`, and runs calls on them.

    Each tool keeps its server's input schema unchanged and is not marked strict. The server's own
    validation is the only check on arguments, and a violation comes back as an error result.

    Args:
        pool: An open pool. The provider never opens or closes it.
    """

    def __init__(self, pool: McpClientPool) -> None:
        self._pool = pool

    async def tool_specs(self) -> list[ToolSpec]:
        """List the tools of every open server, and log each server that failed to open.

        Raises:
            McpClientError: Listing the tools of an open server failed.
        """
        for server, error in self._pool.failures.items():
            log.warning("mcp server unavailable", server=server, error=str(error))
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=dict(tool.input_schema),
            )
            for tool in await self._pool.list_all_tools()
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Call a tool by its `<server>__<tool>` name. Failures come back as error outcomes."""
        try:
            result = await self._pool.call_namespaced_tool(name, arguments)
        except McpClientError as error:
            return ToolOutcome(text=str(error), is_error=True)
        return ToolOutcome(text=_result_text(result), is_error=result.is_error)


def _result_text(result: CallToolResult) -> str:
    # Structured content is the tool's real payload. Text blocks carry errors and plain tools.
    if result.structured_content is not None and not result.is_error:
        return json.dumps(result.structured_content, ensure_ascii=False)
    parts = [
        block.text if isinstance(block, TextContent) else f"[{block.type} content omitted]"
        for block in result.content
    ]
    return "\n".join(parts)
