import pytest

from tests.fakes import iso_days, iso_hours, om_response
from weather_agents.server.openmeteo.client import ENSEMBLE, FORECAST, SEASONAL

pytestmark = pytest.mark.anyio

POINT = {"latitude": 52.52, "longitude": 13.41}


async def test_forecast_returns_daily_rows_with_weekdays_for_the_default_variables(client, fake):
    columns = {
        "temperature_2m_max": [19.5, 19.6, 18.0],
        "temperature_2m_min": [13.4, 12.3, 11.0],
        "precipitation_sum": [0.0, 0.0, 2.1],
        "wind_speed_10m_max": [6.3, 7.0, 9.9],
        "weather_code": [3, 3, 61],
    }
    fake.route(FORECAST, om_response("daily", iso_days("2026-10-03", 3), columns))
    result = await client.call_tool("forecast", {**POINT, "days": 3})
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "daily"
    assert data["table"]["time"] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert data["table"]["weekday"] == ["Saturday", "Sunday", "Monday"]
    assert data["table"]["columns"]["precipitation_sum"] == [0.0, 0.0, 2.1]
    assert data["location"]["timezone"] == "Europe/Berlin"
    assert fake.params() == {
        "latitude": "52.52",
        "longitude": "13.41",
        "forecast_days": "3",
        "timezone": "auto",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "wind_speed_10m_max,weather_code",
    }


async def test_forecast_hourly_returns_hourly_rows_without_weekdays(client, fake):
    times = iso_hours("2026-10-03", 48)
    fake.route(FORECAST, om_response("hourly", times, {"temperature_2m": [1.0] * 48}))
    result = await client.call_tool("forecast", {**POINT, "days": 2, "hourly": True})
    assert not result.is_error
    assert result.structured_content["kind"] == "hourly"
    assert result.structured_content["table"]["weekday"] is None
    assert "daily" not in fake.params()
    assert fake.params()["hourly"] == ("temperature_2m,precipitation,wind_speed_10m,weather_code")


async def test_forecast_hourly_over_three_days_is_refused_before_calling_open_meteo(client, fake):
    result = await client.call_tool("forecast", {**POINT, "days": 4, "hourly": True})
    assert result.is_error
    assert "days" in result.content[0].text
    assert fake.requests == []


async def test_forecast_maps_chosen_variables(client, fake):
    fake.route(
        FORECAST,
        om_response("daily", iso_days("2026-10-03", 1), {"wind_gusts_10m_max": [30.0]}),
    )
    await client.call_tool("forecast", {**POINT, "days": 1, "variables": ["gusts"]})
    assert fake.params()["daily"] == "wind_gusts_10m_max"


async def test_forecast_rejects_an_unknown_variable_naming_the_argument(client, fake):
    result = await client.call_tool("forecast", {**POINT, "variables": ["snow"]})
    assert result.is_error
    assert "variables" in result.content[0].text
    assert fake.requests == []


async def test_forecast_rejects_more_than_sixteen_days(client, fake):
    result = await client.call_tool("forecast", {**POINT, "days": 17})
    assert result.is_error
    assert "days" in result.content[0].text
    assert fake.requests == []


async def test_ensemble_returns_mean_and_spread_and_never_members(client, fake):
    columns = {
        "precipitation_sum": [1.0, 0.0],
        "precipitation_sum_member01": [2.0, 0.0],
        "precipitation_sum_member02": [3.0, 0.0],
    }
    fake.route(ENSEMBLE, om_response("daily", iso_days("2026-10-03", 2), columns))
    result = await client.call_tool(
        "ensemble", {**POINT, "days": 2, "variables": ["precipitation"]}
    )
    assert not result.is_error
    table = result.structured_content["table"]
    assert table["columns"] == {
        "precipitation_sum_mean": [2.0, 0.0],
        "precipitation_sum_std": [0.82, 0.0],
    }
    assert table["weekday"] == ["Saturday", "Sunday"]
    assert fake.params()["models"] == "ecmwf_ifs025"
    assert fake.params()["forecast_days"] == "2"


async def test_ensemble_rejects_sixteen_days(client, fake):
    result = await client.call_tool("ensemble", {**POINT, "days": 16})
    assert result.is_error
    assert fake.requests == []


def seasonal_payload() -> dict:
    return om_response(
        "monthly",
        [f"2026-{month:02d}-01" for month in range(10, 13)] + ["2027-01-01", "2027-02-01"],
        {
            "temperature_2m_anomaly": [0.2, 0.6, 1.2, 1.2, 0.3],
            "precipitation_anomaly": [-5.1, 2.8, 6.4, 4.3, 2.6],
        },
        {"temperature_2m_anomaly": "K", "precipitation_anomaly": "mm"},
    )


async def test_seasonal_returns_the_requested_months_labelled_low_confidence(client, fake):
    fake.route(SEASONAL, seasonal_payload())
    result = await client.call_tool("seasonal", {**POINT, "months": 3})
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "monthly"
    assert data["table"]["time"] == ["2026-10-01", "2026-11-01", "2026-12-01"]
    assert data["table"]["columns"]["temperature_2m_anomaly"] == [0.2, 0.6, 1.2]
    assert any("Low confidence" in note for note in data["notes"])
    assert fake.params()["monthly"] == "temperature_2m_anomaly,precipitation_anomaly"
    assert fake.params()["forecast_days"] == "93"


async def test_seasonal_leaves_out_a_last_month_the_api_has_no_data_for(client, fake):
    payload = seasonal_payload()
    for name, values in payload["monthly"].items():
        if name != "time":
            values[-1] = None
    fake.route(SEASONAL, payload)
    result = await client.call_tool("seasonal", {**POINT, "months": 5})
    data = result.structured_content
    assert data["table"]["time"] == [
        "2026-10-01",
        "2026-11-01",
        "2026-12-01",
        "2027-01-01",
    ]
    assert any("last 1 month(s)" in note for note in data["notes"])


async def test_seasonal_caps_forecast_days_at_the_api_limit(client, fake):
    fake.route(SEASONAL, seasonal_payload())
    await client.call_tool("seasonal", {**POINT, "months": 7})
    assert fake.params()["forecast_days"] == "216"


async def test_seasonal_rejects_eight_months(client, fake):
    result = await client.call_tool("seasonal", {**POINT, "months": 8})
    assert result.is_error
    assert fake.requests == []
