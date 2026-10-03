"""Builds the Open-Meteo MCP server. `mcp` at module level is what `mcp dev` imports."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

import httpx
from mcp.server import MCPServer

from weather_agents.server import prompts, resources
from weather_agents.server.openmeteo.client import OpenMeteoClient
from weather_agents.server.state import AppState
from weather_agents.server.tools import environment, forecast, geocoding, history

HTTP_TIMEOUT_SECONDS = 30
INSTRUCTIONS = (
    "Weather data from Open-Meteo (https://open-meteo.com), licensed CC BY 4.0. "
    "Pick the tool by the time horizon of the question: forecast for the next 16 days, "
    "ensemble for how sure that forecast is, seasonal beyond 16 days, historical for the past, "
    "climate for long-term change. Call geocode_search to turn a place name into coordinates. "
    "Read the open-meteo://guide resource for how the data behaves."
)


def create_server(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    today: Callable[[], date] = date.today,
) -> MCPServer:
    """Build a server. Tests pass a mock `transport` and a fixed `today`."""

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[AppState]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, transport=transport) as http:
            yield AppState(openmeteo=OpenMeteoClient(http), today=today)

    server = MCPServer("weather", instructions=INSTRUCTIONS, lifespan=lifespan)
    geocoding.register(server)
    forecast.register(server)
    history.register(server)
    environment.register(server)
    resources.register(server)
    prompts.register(server, today)
    return server


mcp = create_server()
