import pytest
from mcp import MCPError
from mcp.types import ResourceTemplateReference

from weather_agents.server.resources import ENDPOINT_TEMPLATE, ENDPOINTS

pytestmark = pytest.mark.anyio


async def test_the_guide_is_markdown_about_the_whole_service(client):
    result = await client.read_resource("open-meteo://guide")
    content = result.contents[0]
    assert content.mime_type == "text/markdown"
    assert content.text.startswith("# Open-Meteo guide")


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_every_endpoint_has_a_guide(client, endpoint):
    result = await client.read_resource(f"open-meteo://endpoints/{endpoint}")
    assert result.contents[0].text.startswith("# ")


async def test_an_unknown_endpoint_is_an_error_that_lists_the_valid_names(client):
    with pytest.raises(MCPError) as caught:
        await client.read_resource("open-meteo://endpoints/radar")
    assert "radar" in caught.value.message
    assert "air-quality" in caught.value.message


async def complete(client, prefix: str) -> list[str]:
    result = await client.complete(
        ref=ResourceTemplateReference(uri=ENDPOINT_TEMPLATE),
        argument={"name": "endpoint", "value": prefix},
    )
    return result.completion.values


async def test_a_partial_endpoint_name_completes_from_the_ten_names(client):
    assert await complete(client, "a") == ["air-quality"]
    assert await complete(client, "") == list(ENDPOINTS)
    assert await complete(client, "zzz") == []
