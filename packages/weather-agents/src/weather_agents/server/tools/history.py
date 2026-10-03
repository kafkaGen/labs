"""Backward-looking and long-range tools: historical weather and climate projections."""

from datetime import date
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from weather_agents.server.models import (
    ClimateResult,
    Coordinates,
    Latitude,
    Longitude,
    WeatherResult,
)
from weather_agents.server.openmeteo.client import ARCHIVE, CLIMATE
from weather_agents.server.openmeteo.tables import (
    Agg,
    by_month,
    climate_yearly,
    climatology,
    drop_empty_tail,
    rollup,
    table_from_block,
)
from weather_agents.server.openmeteo.variables import DEFAULT_BASIC, BasicVariable, open_meteo_names
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

ARCHIVE_START = date(1940, 1, 1)
DETAIL_DAYS = 31
MONTHLY_DAYS = 730
HISTORICAL_HOW: dict[str, Agg] = {"precipitation_sum": "sum"}

CLIMATE_MODELS = (
    "CMCC_CM2_VHR4",
    "FGOALS_f3_H",
    "HiRAM_SIT_HR",
    "MRI_AGCM3_2_S",
    "EC_Earth3P_HR",
    "MPI_ESM1_2_XR",
    "NICAM16_8S",
)
CLIMATE_VARIABLES: dict[str, Agg] = {
    "temperature_2m_mean": "mean",
    "precipitation_sum": "sum",
    "wind_speed_10m_max": "mean",
}
CLIMATE_NOTE = (
    "Each value is the mean, lowest, and highest of the yearly values across the climate "
    "models. The gap between _min and _max shows how far the models disagree. "
    "precipitation_sum is the total for the year."
)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def historical(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        start_date: Annotated[date, Field(description="First day, from 1940-01-01.")],
        end_date: Annotated[date, Field(description="Last day, not after today.")],
        variables: Annotated[
            list[BasicVariable] | None,
            Field(description="What to include. Defaults to temperature, precipitation, wind."),
        ] = None,
    ) -> WeatherResult:
        """Observed weather for any period since 1940, from reanalysis data.

        Up to 31 days returns one row per day. Up to 2 years returns one row per month. Longer
        returns 12 rows, the average of each calendar month over all the years, which is a
        climate normal: for 30-year normals ask for 1991-01-01 to 2020-12-31. The newest days can
        have no data yet. Those rows are left out and a note says how many.
        """
        today = state_of(ctx).today()
        if start_date < ARCHIVE_START:
            raise ToolError(
                f"Argument 'start_date': {start_date} is before {ARCHIVE_START}, "
                "when the history starts."
            )
        if end_date > today:
            raise ToolError(f"Argument 'end_date': {end_date} is after today, {today}.")
        if end_date < start_date:
            raise ToolError(f"Argument 'end_date': {end_date} is before 'start_date' {start_date}.")

        data = await state_of(ctx).openmeteo.get(
            ARCHIVE,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            timezone="auto",
            daily=open_meteo_names(variables or DEFAULT_BASIC),
        )
        daily, missing = drop_empty_tail(table_from_block(data, "daily"))
        notes: list[str] = []
        if missing:
            notes.append(f"The newest {missing} day(s) have no data yet and are left out.")
        span = (end_date - start_date).days + 1
        if span <= DETAIL_DAYS:
            return WeatherResult(location=location_of(data), kind="daily", table=daily, notes=notes)
        monthly = rollup(daily, by_month, HISTORICAL_HOW)
        notes.append(
            "precipitation_sum is the total per month. Other columns are means of daily "
            "values. A partial first or last month is averaged over the days present."
        )
        if span <= MONTHLY_DAYS:
            return WeatherResult(
                location=location_of(data), kind="monthly", table=monthly, notes=notes
            )
        table, years = climatology(monthly)
        notes.append(
            f"Average of each calendar month over {years} calendar years. "
            "time is the month number, 01 to 12."
        )
        return WeatherResult(
            location=location_of(data), kind="climatology", table=table, notes=notes
        )

    @mcp.tool()
    @upstream_errors
    async def climate(
        ctx: Context[AppState],
        places: Annotated[
            list[Coordinates],
            Field(min_length=1, max_length=5, description="1 to 5 points to compare."),
        ],
        start_year: Annotated[int, Field(ge=1950, le=2049, description="First year.")] = 2025,
        end_year: Annotated[int, Field(ge=1950, le=2049, description="Last year.")] = 2049,
    ) -> ClimateResult:
        """Climate change projection to 2049, one row per year, for up to 5 places.

        Combines 7 climate models. For temperature, precipitation, and wind it returns the mean
        across models plus the lowest and highest model, so you can see how far the models
        disagree. Use it for long-term trends, not for weather on a given day.
        """
        if end_year < start_year:
            raise ToolError(f"Argument 'end_year': {end_year} is before 'start_year' {start_year}.")
        data = await state_of(ctx).openmeteo.get(
            CLIMATE,
            latitude=[place.latitude for place in places],
            longitude=[place.longitude for place in places],
            start_date=f"{start_year}-01-01",
            end_date=f"{end_year}-12-31",
            models=list(CLIMATE_MODELS),
            daily=list(CLIMATE_VARIABLES),
        )
        items = data if isinstance(data, list) else [data]
        return ClimateResult(
            places=[
                WeatherResult(
                    location=location_of(item),
                    kind="yearly",
                    table=climate_yearly(
                        table_from_block(item, "daily"), CLIMATE_VARIABLES, CLIMATE_MODELS
                    ),
                    notes=[CLIMATE_NOTE],
                )
                for item in items
            ]
        )
