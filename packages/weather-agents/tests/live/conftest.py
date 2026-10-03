import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from mcp import Client, StdioServerParameters


@asynccontextmanager
async def stdio_client() -> AsyncIterator[Client]:
    """The server as a child process, spoken to over stdin and stdout."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        yield client


# One entry per transport. Every live test runs once for each, with the name in its test id.
# To add HTTP, write `http_client()` like `stdio_client()` and register it here. No test changes.
TRANSPORTS: dict[str, Callable[[], AbstractAsyncContextManager[Client]]] = {
    "stdio": stdio_client,
}


@pytest.fixture(params=TRANSPORTS)
async def live_client(request: pytest.FixtureRequest) -> AsyncIterator[Client]:
    async with TRANSPORTS[request.param]() as client:
        yield client
