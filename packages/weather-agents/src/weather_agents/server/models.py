"""Argument types and result models shared by the tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from weather_agents.server.openmeteo.tables import Table

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude in degrees.")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Longitude in degrees.")]


class Coordinates(BaseModel):
    latitude: Latitude
    longitude: Longitude


class Location(BaseModel):
    """The grid cell Open-Meteo answered for. It can differ slightly from the request."""

    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None


class WeatherResult(BaseModel):
    location: Location
    kind: Literal["hourly", "daily", "monthly", "climatology", "yearly"]
    table: Table
    notes: list[str] = []


class ClimateResult(BaseModel):
    places: list[WeatherResult]


class Place(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    population: int | None = None


class PlaceList(BaseModel):
    results: list[Place]


class ElevationPoint(BaseModel):
    latitude: float
    longitude: float
    elevation: float | None


class ElevationResult(BaseModel):
    points: list[ElevationPoint]
