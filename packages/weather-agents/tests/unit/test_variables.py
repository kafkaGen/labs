from weather_agents.server.openmeteo.variables import (
    DEFAULT_BASIC,
    DEFAULT_FORECAST,
    open_meteo_names,
)


def test_daily_names_expand_temperature_to_max_and_min():
    assert open_meteo_names(["temperature", "wind"]) == [
        "temperature_2m_max",
        "temperature_2m_min",
        "wind_speed_10m_max",
    ]


def test_hourly_names_use_the_hourly_variables():
    assert open_meteo_names(["temperature", "gusts"], hourly=True) == [
        "temperature_2m",
        "wind_gusts_10m",
    ]


def test_repeated_variables_are_sent_once():
    assert open_meteo_names(["wind", "wind"]) == ["wind_speed_10m_max"]


def test_default_forecast_bundle_names():
    assert open_meteo_names(DEFAULT_FORECAST) == [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "wind_speed_10m_max",
        "weather_code",
    ]
    assert open_meteo_names(DEFAULT_BASIC)[-1] == "wind_speed_10m_max"
