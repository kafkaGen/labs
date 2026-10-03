import sys
from collections.abc import AsyncIterator

import pytest
from mcp import Client, StdioServerParameters


@pytest.fixture
async def live_client() -> AsyncIterator[Client]:
    """A client on a real server child process. Every live test takes this and nothing else.

    The HTTP transport will add a second way to build this client, and the tests stay as they are.
    """
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        yield client
