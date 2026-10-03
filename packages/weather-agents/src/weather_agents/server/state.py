"""What the server's lifespan hands to every tool call."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from weather_agents.server.openmeteo.client import OpenMeteoClient


@dataclass(frozen=True)
class AppState:
    openmeteo: OpenMeteoClient
    today: Callable[[], date]
