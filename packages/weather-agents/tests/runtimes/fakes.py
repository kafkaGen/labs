"""A pool stand-in for the runtime tests."""

from mcp.types import CallToolResult, TextContent, Tool

from weather_agents.mcp_client import McpClientError

FORECAST_TOOL = Tool(
    name="open-meteo__forecast",
    description="Forecast for one place.",
    input_schema={
        "type": "object",
        "properties": {"latitude": {"type": "number", "minimum": -90, "maximum": 90}},
        "required": ["latitude"],
    },
)


class FakePool:
    """Serves fixed tools and scripted results, and records calls."""

    def __init__(
        self,
        tools: list[Tool] | None = None,
        *,
        results: dict[str, CallToolResult | Exception] | None = None,
        failures: dict[str, McpClientError] | None = None,
    ) -> None:
        self.tools = tools if tools is not None else [FORECAST_TOOL]
        self.results = results or {}
        self.failures = failures or {}
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> "FakePool":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True

    async def list_all_tools(self) -> list[Tool]:
        return self.tools

    async def call_namespaced_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        self.calls.append((name, arguments))
        result = self.results.get(
            name, CallToolResult(content=[TextContent(type="text", text="ok")])
        )
        if isinstance(result, Exception):
            raise result
        return result
