"""Logical variable names the tools accept, and the Open-Meteo names they stand for."""

from collections.abc import Sequence
from typing import Literal

BasicVariable = Literal["temperature", "precipitation", "wind"]
ForecastVariable = Literal[
    "temperature",
    "precipitation",
    "wind",
    "gusts",
    "precipitation_probability",
    "uv_index",
    "weather_code",
]

DEFAULT_BASIC: tuple[BasicVariable, ...] = ("temperature", "precipitation", "wind")
DEFAULT_FORECAST: tuple[ForecastVariable, ...] = (
    "temperature",
    "precipitation",
    "wind",
    "weather_code",
)

_DAILY: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature_2m_max", "temperature_2m_min"),
    "precipitation": ("precipitation_sum",),
    "wind": ("wind_speed_10m_max",),
    "gusts": ("wind_gusts_10m_max",),
    "precipitation_probability": ("precipitation_probability_max",),
    "uv_index": ("uv_index_max",),
    "weather_code": ("weather_code",),
}

_HOURLY: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature_2m",),
    "precipitation": ("precipitation",),
    "wind": ("wind_speed_10m",),
    "gusts": ("wind_gusts_10m",),
    "precipitation_probability": ("precipitation_probability",),
    "uv_index": ("uv_index",),
    "weather_code": ("weather_code",),
}


def open_meteo_names(variables: Sequence[str], *, hourly: bool = False) -> list[str]:
    """Map logical names to Open-Meteo daily (default) or hourly names, without repeats."""
    mapping = _HOURLY if hourly else _DAILY
    return list(dict.fromkeys(name for variable in variables for name in mapping[variable]))
