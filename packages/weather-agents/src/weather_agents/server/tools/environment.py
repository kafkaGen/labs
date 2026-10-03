"""Tools for the sea, the air, rivers, and terrain."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from weather_agents.server.models import (
    Coordinates,
    ElevationPoint,
    ElevationResult,
    Latitude,
    Longitude,
    WeatherResult,
)
from weather_agents.server.openmeteo.client import AIR_QUALITY, ELEVATION, FLOOD, MARINE
from weather_agents.server.openmeteo.tables import (
    Agg,
    Table,
    by_day,
    drop_empty,
    rollup,
    table_from_block,
)
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

MARINE_DAILY: dict[str, Agg] = {
    "wave_height": "max",
    "wave_period": "max",
    "swell_wave_height": "max",
    "ocean_current_velocity": "max",
    "sea_surface_temperature": "mean",
    "sea_level_height_msl": "max",
}
AIR_HOURLY = [
    "pm10",
    "pm2_5",
    "ozone",
    "nitrogen_dioxide",
    "european_aqi",
    "us_aqi",
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "ragweed_pollen",
]
FLOOD_NOTE = (
    "River discharge at the nearest river grid cell, from the largest river within about "
    "5 km. Open-Meteo gives no river name or distance."
)
INLAND_NOTE = "No marine data at this point. It is inland or too far from the sea."


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def marine(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=7, description="Days ahead, starting today.")] = 5,
    ) -> WeatherResult:
        """Sea conditions for up to 7 days ahead: waves, swell, currents, sea surface temperature.

        Also sea level height. One row per day: the daily maximum, except sea surface
        temperature, which is the daily mean. Only coastal and open-water points have data. An
        inland point returns an empty table with a note.
        """
        data = await state_of(ctx).openmeteo.get(
            MARINE,
            latitude=latitude,
            longitude=longitude,
            hourly=list(MARINE_DAILY),
            forecast_days=days,
            timezone="auto",
        )
        hourly = table_from_block(data, "hourly")
        kept, _ = drop_empty(hourly)
        if not kept.columns:
            return WeatherResult(
                location=location_of(data),
                kind="daily",
                table=Table(time=[], units={}, columns={}),
                notes=[INLAND_NOTE],
            )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=rollup(hourly, by_day, MARINE_DAILY),
        )

    @mcp.tool()
    @upstream_errors
    async def air_quality(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=7, description="Days ahead, starting today.")] = 3,
    ) -> WeatherResult:
        """Air quality for up to 7 days ahead: pollutants, European and US AQI, and pollen.

        One row per day, the daily maximum. Pollen exists only for Europe in season, and
        columns with no data are left out with a note.
        """
        data = await state_of(ctx).openmeteo.get(
            AIR_QUALITY,
            latitude=latitude,
            longitude=longitude,
            hourly=AIR_HOURLY,
            forecast_days=days,
            timezone="auto",
        )
        table, empty = drop_empty(rollup(table_from_block(data, "hourly"), by_day, default="max"))
        notes = [f"No data for: {', '.join(empty)}."] if empty else []
        return WeatherResult(location=location_of(data), kind="daily", table=table, notes=notes)

    @mcp.tool()
    @upstream_errors
    async def flood(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=92, description="Days ahead, starting today.")] = 30,
    ) -> WeatherResult:
        """River discharge in m3/s for up to 92 days ahead, one row per day."""
        data = await state_of(ctx).openmeteo.get(
            FLOOD,
            latitude=latitude,
            longitude=longitude,
            daily="river_discharge",
            forecast_days=days,
        )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=table_from_block(data, "daily"),
            notes=[FLOOD_NOTE],
        )

    @mcp.tool()
    @upstream_errors
    async def elevation(
        ctx: Context[AppState],
        points: Annotated[
            list[Coordinates],
            Field(min_length=1, max_length=100, description="1 to 100 points."),
        ],
    ) -> ElevationResult:
        """Terrain height in metres for one or more points. It does not change over time."""
        data = await state_of(ctx).openmeteo.get(
            ELEVATION,
            latitude=[point.latitude for point in points],
            longitude=[point.longitude for point in points],
        )
        return ElevationResult(
            points=[
                ElevationPoint(latitude=point.latitude, longitude=point.longitude, elevation=height)
                for point, height in zip(points, data["elevation"], strict=True)
            ]
        )
