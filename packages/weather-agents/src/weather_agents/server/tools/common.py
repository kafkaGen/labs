"""Helpers every tool module uses."""

import functools
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from weather_agents.server.models import Location
from weather_agents.server.openmeteo.client import OpenMeteoError
from weather_agents.server.state import AppState


def upstream_errors[**P, R](fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Turn an OpenMeteoError into a tool error result that names the cause.

    `functools.wraps` keeps the signature and docstring, which the SDK reads to build the
    tool's input schema and description.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except OpenMeteoError as error:
            raise ToolError(f"Open-Meteo {error.cause}: {error.detail}") from error

    return wrapper


def state_of(ctx: Context[AppState]) -> AppState:
    return ctx.request_context.lifespan_context


def location_of(payload: dict[str, Any]) -> Location:
    return Location(
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        elevation=payload.get("elevation"),
        timezone=payload.get("timezone"),
    )
