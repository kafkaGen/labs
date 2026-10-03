import httpx
import pytest

from weather_agents.server.openmeteo.client import OpenMeteoClient, OpenMeteoError

pytestmark = pytest.mark.anyio

URL = "https://example.test/v1/thing"


def client_for(handler) -> OpenMeteoClient:
    return OpenMeteoClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_get_returns_json_joins_lists_and_drops_none():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"ok": True})

    data = await client_for(handler).get(URL, daily=["a", "b"], timezone="auto", skip=None)
    assert data == {"ok": True}
    assert seen == {"daily": "a,b", "timezone": "auto"}


async def test_a_400_becomes_rejected_with_the_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": True, "reason": "Latitude must be in range"})

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "rejected"
    assert caught.value.detail == "Latitude must be in range"


async def test_a_400_without_a_reason_falls_back_to_the_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="nope")

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "rejected"
    assert caught.value.detail == "HTTP 400"


@pytest.mark.parametrize(
    ("status", "cause"), [(429, "rate_limited"), (500, "server_error"), (503, "server_error")]
)
async def test_other_statuses_map_to_a_cause(status: int, cause: str):
    with pytest.raises(OpenMeteoError) as caught:
        await client_for(lambda request: httpx.Response(status)).get(URL)
    assert caught.value.cause == cause


async def test_a_timeout_becomes_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "timeout"


async def test_a_network_failure_becomes_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "unreachable"
