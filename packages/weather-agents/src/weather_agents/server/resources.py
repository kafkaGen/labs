"""Resources: the Open-Meteo guide and one guide per endpoint, read from markdown files."""

import functools
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp.types import Completion, ResourceTemplateReference

CONTENT_DIR = Path(__file__).parent / "content"
ENDPOINTS = (
    "geocoding",
    "forecast",
    "ensemble",
    "seasonal",
    "historical",
    "climate",
    "marine",
    "air-quality",
    "flood",
    "elevation",
)
ENDPOINT_TEMPLATE = "open-meteo://endpoints/{endpoint}"


@functools.cache
def read_content(relative_path: str) -> str:
    return (CONTENT_DIR / relative_path).read_text(encoding="utf-8")


def register(mcp: MCPServer) -> None:
    @mcp.resource(
        "open-meteo://guide",
        name="open-meteo-guide",
        title="Open-Meteo guide",
        description="The whole service in one read: data sources, trust, conventions, horizons.",
        mime_type="text/markdown",
    )
    def guide() -> str:
        return read_content("guide.md")

    @mcp.resource(
        ENDPOINT_TEMPLATE,
        name="open-meteo-endpoint-guide",
        title="Open-Meteo endpoint guide",
        description="One endpoint in depth: sources, limits, variables, and argument tips.",
        mime_type="text/markdown",
    )
    def endpoint_guide(endpoint: str) -> str:
        if endpoint not in ENDPOINTS:
            raise ResourceNotFoundError(
                f"Unknown endpoint {endpoint!r}. Valid endpoints: {', '.join(ENDPOINTS)}."
            )
        return read_content(f"endpoints/{endpoint}.md")

    @mcp.completion()
    async def complete_endpoint(ref, argument, context):
        if isinstance(ref, ResourceTemplateReference) and argument.name == "endpoint":
            return Completion(values=[n for n in ENDPOINTS if n.startswith(argument.value)])
        return None
