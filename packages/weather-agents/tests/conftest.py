import os
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from mcp import Client

from tests.fakes import FakeOpenMeteo
from weather_agents.server.app import create_server

TODAY = date(2026, 10, 3)  # a Saturday


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake() -> FakeOpenMeteo:
    return FakeOpenMeteo()


@pytest.fixture
async def client(fake: FakeOpenMeteo) -> AsyncIterator[Client]:
    server = create_server(transport=httpx.MockTransport(fake), today=lambda: TODAY)
    async with Client(server) as connected:
        yield connected


@pytest.fixture(autouse=True)
def _no_agent_settings_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("WEATHER_AGENTS_"):
            monkeypatch.delenv(name)
