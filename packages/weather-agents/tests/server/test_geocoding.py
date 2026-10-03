import pytest

from tests.fakes import PLACES
from weather_agents.server.openmeteo.client import GEOCODING_GET, GEOCODING_SEARCH

pytestmark = pytest.mark.anyio


async def test_search_returns_every_candidate_with_country_region_and_population(client, fake):
    fake.route(GEOCODING_SEARCH, {"results": [PLACES["springfield_mo"], PLACES["springfield_il"]]})
    result = await client.call_tool("geocode_search", {"name": "Springfield"})
    assert not result.is_error
    places = result.structured_content["results"]
    assert [(p["admin1"], p["population"]) for p in places] == [
        ("Missouri", 170188),
        ("Illinois", 114394),
    ]
    assert places[0]["country"] == "United States"
    assert fake.params() == {"name": "Springfield", "count": "5", "language": "en"}


async def test_search_with_no_match_returns_an_empty_list(client, fake):
    fake.route(GEOCODING_SEARCH, {"generationtime_ms": 0.1})
    result = await client.call_tool("geocode_search", {"name": "Zzyzzyxx"})
    assert not result.is_error
    assert result.structured_content["results"] == []


async def test_search_sends_the_country_code_in_upper_case(client, fake):
    fake.route(GEOCODING_SEARCH, {"results": [PLACES["berlin"]]})
    await client.call_tool("geocode_search", {"name": "Berlin", "country_code": "de"})
    assert fake.params()["countryCode"] == "DE"


async def test_search_rejects_a_one_letter_name_without_calling_open_meteo(client, fake):
    result = await client.call_tool("geocode_search", {"name": "B"})
    assert result.is_error
    assert "name" in result.content[0].text
    assert fake.requests == []


async def test_get_returns_one_place_by_id(client, fake):
    fake.route(GEOCODING_GET, PLACES["berlin"])
    result = await client.call_tool("geocode_get", {"id": 2950159})
    assert not result.is_error
    assert result.structured_content["name"] == "Berlin"
    assert fake.params()["id"] == "2950159"
