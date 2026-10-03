"""Geocoding tools: place name to coordinates and timezone."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from weather_agents.server.models import Place, PlaceList
from weather_agents.server.openmeteo.client import GEOCODING_GET, GEOCODING_SEARCH
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import state_of, upstream_errors


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def geocode_search(
        ctx: Context[AppState],
        name: Annotated[
            str,
            Field(min_length=2, description="Place name, such as 'Springfield' or 'Paris'."),
        ],
        country_code: Annotated[
            str | None,
            Field(
                pattern=r"^[A-Za-z]{2}$",
                description="ISO 3166-1 alpha-2 country code, such as 'US', to narrow the search.",
            ),
        ] = None,
        count: Annotated[int, Field(ge=1, le=100, description="Maximum results.")] = 5,
    ) -> PlaceList:
        """Place name to coordinates and timezone.

        Several results means the name is ambiguous: ask the user which place they mean before
        using any coordinates. Each result has country, region, and population to tell them apart.
        """
        data = await state_of(ctx).openmeteo.get(
            GEOCODING_SEARCH,
            name=name,
            countryCode=country_code.upper() if country_code else None,
            count=count,
            language="en",
        )
        return PlaceList(results=[Place.model_validate(item) for item in data.get("results", [])])

    @mcp.tool()
    @upstream_errors
    async def geocode_get(
        ctx: Context[AppState],
        id: Annotated[int, Field(description="Geocoding id, from a geocode_search result.")],
    ) -> Place:
        """Look up one place by its geocoding id. Returns the same fields as geocode_search."""
        data = await state_of(ctx).openmeteo.get(GEOCODING_GET, id=id, language="en")
        return Place.model_validate(data)
