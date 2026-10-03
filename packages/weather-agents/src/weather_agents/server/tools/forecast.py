"""Forward-looking tools: forecast, ensemble, seasonal."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from weather_agents.server.models import Latitude, Longitude, WeatherResult
from weather_agents.server.openmeteo.client import ENSEMBLE, FORECAST, SEASONAL
from weather_agents.server.openmeteo.tables import ensemble_stats, head, table_from_block
from weather_agents.server.openmeteo.variables import (
    DEFAULT_BASIC,
    DEFAULT_FORECAST,
    BasicVariable,
    ForecastVariable,
    open_meteo_names,
)
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

HOURLY_MAX_DAYS = 3
ENSEMBLE_MODEL = "ecmwf_ifs025"
SEASONAL_VARIABLES = ["temperature_2m_anomaly", "precipitation_anomaly"]
SEASONAL_MAX_FORECAST_DAYS = 216
SEASONAL_NOTE = (
    "Low confidence. A seasonal forecast shows a tendency against the long-term normal, "
    "not a day-by-day forecast. Anomaly is forecast minus normal."
)
ENSEMBLE_NOTE = (
    "Mean and standard deviation across the ensemble members. A larger standard deviation "
    "means the members disagree and the forecast is less certain."
)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def forecast(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=16, description="Days ahead, starting today.")] = 7,
        hourly: Annotated[
            bool, Field(description="Hourly rows instead of daily. Limited to 3 days.")
        ] = False,
        variables: Annotated[
            list[ForecastVariable] | None,
            Field(
                description="What to include. Defaults to temperature, precipitation, wind, "
                "and weather_code."
            ),
        ] = None,
    ) -> WeatherResult:
        """Weather forecast from today out to 16 days for one point.

        Daily rows carry the weekday of each date, in the place's local timezone. Temperature is
        in degrees Celsius, wind in km/h, precipitation in mm. For how sure the forecast is, call
        ensemble. Beyond 16 days, call seasonal.
        """
        if hourly and days > HOURLY_MAX_DAYS:
            raise ToolError(
                f"Argument 'days': hourly forecasts are limited to {HOURLY_MAX_DAYS} days, "
                f"got {days}. Use hourly=false for longer."
            )
        block = "hourly" if hourly else "daily"
        names = open_meteo_names(variables or DEFAULT_FORECAST, hourly=hourly)
        data = await state_of(ctx).openmeteo.get(
            FORECAST,
            latitude=latitude,
            longitude=longitude,
            forecast_days=days,
            timezone="auto",
            **{block: names},
        )
        return WeatherResult(
            location=location_of(data), kind=block, table=table_from_block(data, block)
        )

    @mcp.tool()
    @upstream_errors
    async def ensemble(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=15, description="Days ahead, starting today.")] = 7,
        variables: Annotated[
            list[BasicVariable] | None,
            Field(description="What to include. Defaults to temperature, precipitation, wind."),
        ] = None,
    ) -> WeatherResult:
        """How sure a forecast is, within 15 days. Daily mean and spread across ensemble members.

        Each variable comes back as `<name>_mean` and `<name>_std`. The raw members are never
        returned. Use it next to forecast: a high standard deviation means low confidence.
        """
        names = open_meteo_names(variables or DEFAULT_BASIC)
        data = await state_of(ctx).openmeteo.get(
            ENSEMBLE,
            latitude=latitude,
            longitude=longitude,
            models=ENSEMBLE_MODEL,
            forecast_days=days,
            timezone="auto",
            daily=names,
        )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=ensemble_stats(table_from_block(data, "daily")),
            notes=[ENSEMBLE_NOTE],
        )

    @mcp.tool()
    @upstream_errors
    async def seasonal(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        months: Annotated[
            int, Field(ge=1, le=7, description="Months ahead, counting the current month.")
        ] = 3,
    ) -> WeatherResult:
        """Seasonal tendency from 16 days to 7 months ahead, one row per month. Low confidence.

        Returns the expected anomaly against normal: temperature in K (degrees above or below
        normal) and precipitation in mm. Do not present it as a forecast for a given day.
        """
        data = await state_of(ctx).openmeteo.get(
            SEASONAL,
            latitude=latitude,
            longitude=longitude,
            monthly=SEASONAL_VARIABLES,
            forecast_days=min(months * 31, SEASONAL_MAX_FORECAST_DAYS),
            timezone="auto",
        )
        return WeatherResult(
            location=location_of(data),
            kind="monthly",
            table=head(table_from_block(data, "monthly"), months),
            notes=[SEASONAL_NOTE],
        )
