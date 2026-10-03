from datetime import date

import httpx
import pytest

from tests.fakes import constant_daily
from weather_agents.server.openmeteo.client import ARCHIVE, CLIMATE
from weather_agents.server.tools.history import CLIMATE_MODELS

pytestmark = pytest.mark.anyio

POINT = {"latitude": 52.52, "longitude": 13.41}
DAILY_VALUES = {
    "temperature_2m_max": 10.0,
    "temperature_2m_min": 5.0,
    "precipitation_sum": 1.0,
    "wind_speed_10m_max": 20.0,
}


def serve_archive(fake, *, empty_tail: int = 0) -> None:
    """Serve constant days. The last `empty_tail` come back as nulls, like a lagging archive."""

    def archive(request: httpx.Request):
        params = request.url.params
        payload = constant_daily(
            date.fromisoformat(params["start_date"]),
            date.fromisoformat(params["end_date"]),
            DAILY_VALUES,
        )
        if empty_tail:
            for name, values in payload["daily"].items():
                if name != "time":
                    values[-empty_tail:] = [None] * empty_tail
        return payload

    fake.route_with(ARCHIVE, archive)


async def historical(client, start: str, end: str):
    return await client.call_tool("historical", {**POINT, "start_date": start, "end_date": end})


async def test_a_span_up_to_a_month_returns_one_row_per_day(client, fake):
    serve_archive(fake)
    result = await historical(client, "2025-01-01", "2025-01-10")
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "daily"
    assert len(data["table"]["time"]) == 10
    assert fake.params()["start_date"] == "2025-01-01"
    assert fake.params()["daily"] == (
        "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
    )


async def test_a_span_over_a_month_returns_one_row_per_month_with_precipitation_summed(
    client, fake
):
    serve_archive(fake)
    result = await historical(client, "2025-01-01", "2025-03-31")
    data = result.structured_content
    assert data["kind"] == "monthly"
    assert data["table"]["time"] == ["2025-01", "2025-02", "2025-03"]
    assert data["table"]["columns"]["precipitation_sum"] == [31.0, 28.0, 31.0]
    assert data["table"]["columns"]["temperature_2m_max"] == [10.0, 10.0, 10.0]
    assert any("Partial" in note or "partial" in note for note in data["notes"])


async def test_a_span_over_two_years_returns_twelve_calendar_month_normals(client, fake):
    serve_archive(fake)
    result = await historical(client, "2021-01-01", "2023-12-31")
    data = result.structured_content
    assert data["kind"] == "climatology"
    assert data["table"]["time"] == [f"{month:02d}" for month in range(1, 13)]
    assert data["table"]["columns"]["precipitation_sum"][:2] == [31.0, 28.0]
    assert any("3 calendar years" in note for note in data["notes"])


async def test_a_thirty_year_normal_returns_twelve_rows(client, fake):
    serve_archive(fake)
    result = await historical(client, "1991-01-01", "2020-12-31")
    data = result.structured_content
    assert len(data["table"]["time"]) == 12
    assert any("30 calendar years" in note for note in data["notes"])


async def test_days_the_archive_has_no_data_for_yet_are_left_out_with_a_note(client, fake):
    serve_archive(fake, empty_tail=3)
    result = await historical(client, "2026-09-20", "2026-10-01")
    data = result.structured_content
    assert data["table"]["time"][-1] == "2026-09-28"
    assert any("newest 3 day(s)" in note for note in data["notes"])


async def test_a_complete_range_gets_no_missing_data_note(client, fake):
    serve_archive(fake)
    result = await historical(client, "2026-09-20", "2026-10-01")
    assert not any("no data yet" in note for note in result.structured_content["notes"])


@pytest.mark.parametrize(
    ("start", "end", "argument"),
    [
        ("1939-12-31", "1940-01-10", "start_date"),
        ("2026-09-01", "2026-10-04", "end_date"),
        ("2025-02-01", "2025-01-01", "end_date"),
    ],
)
async def test_a_date_outside_the_horizon_names_the_argument_and_skips_open_meteo(
    client, fake, start, end, argument
):
    result = await historical(client, start, end)
    assert result.is_error
    assert argument in result.content[0].text
    assert fake.requests == []


def serve_climate(fake) -> None:
    def climate(request: httpx.Request):
        params = request.url.params
        start = date.fromisoformat(params["start_date"])
        end = date.fromisoformat(params["end_date"])
        values = {}
        for index, model in enumerate(CLIMATE_MODELS):
            values[f"temperature_2m_mean_{model}"] = 10.0 + index
            values[f"precipitation_sum_{model}"] = 1.0
            values[f"wind_speed_10m_max_{model}"] = 5.0
        payload = constant_daily(start, end, values)
        count = len(params["latitude"].split(","))
        return payload if count == 1 else [payload] * count

    fake.route_with(CLIMATE, climate)


async def test_climate_returns_yearly_mean_and_model_range_for_each_place(client, fake):
    serve_climate(fake)
    result = await client.call_tool(
        "climate",
        {
            "places": [
                {"latitude": 52.52, "longitude": 13.41},
                {"latitude": 48.14, "longitude": 11.58},
            ],
            "start_year": 2025,
            "end_year": 2026,
        },
    )
    assert not result.is_error
    places = result.structured_content["places"]
    assert len(places) == 2
    table = places[0]["table"]
    assert places[0]["kind"] == "yearly"
    assert table["time"] == ["2025", "2026"]
    assert table["columns"]["temperature_2m_mean_mean"] == [13.0, 13.0]
    assert table["columns"]["temperature_2m_mean_min"] == [10.0, 10.0]
    assert table["columns"]["temperature_2m_mean_max"] == [16.0, 16.0]
    assert table["columns"]["precipitation_sum_mean"] == [365.0, 365.0]
    params = fake.params()
    assert params["latitude"] == "52.52,48.14"
    assert params["longitude"] == "13.41,11.58"
    assert params["start_date"] == "2025-01-01"
    assert params["end_date"] == "2026-12-31"
    assert params["models"] == ",".join(CLIMATE_MODELS)


async def test_climate_handles_the_single_object_reply_for_one_place(client, fake):
    serve_climate(fake)
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 52.52, "longitude": 13.41}], "start_year": 2030, "end_year": 2030},
    )
    assert not result.is_error
    assert len(result.structured_content["places"]) == 1


async def test_climate_refuses_more_than_five_places_naming_the_argument(client, fake):
    places = [{"latitude": float(i), "longitude": float(i)} for i in range(6)]
    result = await client.call_tool("climate", {"places": places})
    assert result.is_error
    assert "places" in result.content[0].text
    assert fake.requests == []


async def test_climate_refuses_an_end_year_before_the_start_year(client, fake):
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 1.0, "longitude": 1.0}], "start_year": 2040, "end_year": 2030},
    )
    assert result.is_error
    assert "end_year" in result.content[0].text
    assert fake.requests == []


async def test_climate_refuses_a_year_outside_the_data(client, fake):
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 1.0, "longitude": 1.0}], "start_year": 1949},
    )
    assert result.is_error
    assert "start_year" in result.content[0].text
    assert fake.requests == []
