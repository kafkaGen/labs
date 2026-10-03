import pytest

from tests.fakes import iso_days, iso_hours, om_response
from weather_agents.server.openmeteo.client import AIR_QUALITY, ELEVATION, FLOOD, MARINE

pytestmark = pytest.mark.anyio

POINT = {"latitude": 54.5, "longitude": 8.3}
MARINE_COLUMNS = (
    "wave_height",
    "wave_period",
    "swell_wave_height",
    "ocean_current_velocity",
    "sea_surface_temperature",
    "sea_level_height_msl",
)


async def test_marine_returns_daily_maximums_and_the_mean_sea_temperature(client, fake):
    times = iso_hours("2026-10-03", 48)
    columns = {name: [1.0] * 48 for name in MARINE_COLUMNS}
    columns["wave_height"] = [float(i % 24) for i in range(48)]
    columns["sea_surface_temperature"] = [float(i % 24) for i in range(48)]
    fake.route(MARINE, om_response("hourly", times, columns))
    result = await client.call_tool("marine", {**POINT, "days": 2})
    assert not result.is_error
    table = result.structured_content["table"]
    assert table["time"] == ["2026-10-03", "2026-10-04"]
    assert table["columns"]["wave_height"] == [23.0, 23.0]
    assert table["columns"]["sea_surface_temperature"] == [11.5, 11.5]
    assert fake.params()["forecast_days"] == "2"
    assert fake.params()["hourly"] == ",".join(MARINE_COLUMNS)


async def test_marine_for_an_inland_point_returns_an_empty_table_with_a_note(client, fake):
    times = iso_hours("2026-10-03", 24)
    columns = {name: [None] * 24 for name in MARINE_COLUMNS}
    fake.route(MARINE, om_response("hourly", times, columns))
    result = await client.call_tool("marine", {"latitude": 48.14, "longitude": 11.58, "days": 1})
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["time"] == []
    assert any("inland" in note for note in data["notes"])


async def test_air_quality_returns_daily_maximums_and_drops_empty_pollen(client, fake):
    times = iso_hours("2026-10-03", 24)
    columns = {
        "pm10": [float(i) for i in range(24)],
        "european_aqi": [20] * 24,
        "alder_pollen": [None] * 24,
    }
    fake.route(AIR_QUALITY, om_response("hourly", times, columns))
    result = await client.call_tool(
        "air_quality", {"latitude": 40.7, "longitude": -74.0, "days": 1}
    )
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["time"] == ["2026-10-03"]
    assert data["table"]["columns"] == {"pm10": [23.0], "european_aqi": [20]}
    assert any("alder_pollen" in note for note in data["notes"])
    assert fake.params()["forecast_days"] == "1"


async def test_flood_returns_daily_discharge_with_a_note_about_the_river(client, fake):
    fake.route(
        FLOOD,
        om_response(
            "daily",
            iso_days("2026-10-03", 3),
            {"river_discharge": [0.46, 0.45, 0.45]},
            {"river_discharge": "m³/s"},
        ),
    )
    result = await client.call_tool("flood", {"latitude": 52.52, "longitude": 13.41})
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["columns"]["river_discharge"] == [0.46, 0.45, 0.45]
    assert any("no river name" in note for note in data["notes"])
    assert fake.params()["daily"] == "river_discharge"
    assert fake.params()["forecast_days"] == "30"


async def test_flood_rejects_more_than_92_days(client, fake):
    result = await client.call_tool("flood", {"latitude": 1.0, "longitude": 1.0, "days": 93})
    assert result.is_error
    assert fake.requests == []


async def test_elevation_pairs_each_height_with_its_point(client, fake):
    fake.route(ELEVATION, {"elevation": [38.0, 524.0]})
    result = await client.call_tool(
        "elevation",
        {
            "points": [
                {"latitude": 52.52, "longitude": 13.41},
                {"latitude": 48.14, "longitude": 11.58},
            ]
        },
    )
    assert not result.is_error
    assert result.structured_content["points"] == [
        {"latitude": 52.52, "longitude": 13.41, "elevation": 38.0},
        {"latitude": 48.14, "longitude": 11.58, "elevation": 524.0},
    ]
    assert fake.params()["latitude"] == "52.52,48.14"


async def test_elevation_refuses_more_than_100_points(client, fake):
    points = [{"latitude": 1.0, "longitude": 1.0}] * 101
    result = await client.call_tool("elevation", {"points": points})
    assert result.is_error
    assert "points" in result.content[0].text
    assert fake.requests == []
