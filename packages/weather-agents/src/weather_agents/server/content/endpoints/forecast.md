# Forecast

## What it answers

Weather from today out to 16 days, hourly or daily, for one point. Time horizon: `forecast_days` runs from 0 to 16, default 7.

Source: https://open-meteo.com/en/docs

## Sources and models

With no model chosen, Open-Meteo combines the best available models for the location. The default output starts at 00:00 local time today.

Source: https://open-meteo.com/en/docs

## Trust and limits

- For how sure a forecast is, use the ensemble endpoint.
- The `weather_code` is a WMO code number. The API returns the number only.
- Beyond 16 days, use the seasonal endpoint.

Source: https://open-meteo.com/en/docs

## Variables

The `forecast` tool takes logical names and maps them. Daily rows use the first name, hourly rows the second.

| `variables` name | Daily | Hourly | Unit |
|---|---|---|---|
| `temperature` | `temperature_2m_max`, `temperature_2m_min` | `temperature_2m` | °C |
| `precipitation` | `precipitation_sum` | `precipitation` | mm |
| `wind` | `wind_speed_10m_max` | `wind_speed_10m` | km/h |
| `gusts` | `wind_gusts_10m_max` | `wind_gusts_10m` | km/h |
| `precipitation_probability` | `precipitation_probability_max` | `precipitation_probability` | % |
| `uv_index` | `uv_index_max` | `uv_index` | none |
| `weather_code` | `weather_code` | `weather_code` | WMO code |

The API offers many more variables, such as humidity, pressure, cloud cover, visibility, and soil values.

Source: https://open-meteo.com/en/docs

## Argument tips

- `days` runs from 1 to 16. Hourly rows are limited to 3 days to keep the result small.
- Daily rows carry a `weekday` for each date in the place's timezone. Use it to find a weekend.
- Default variables are temperature, precipitation, wind, and weather_code.

Source: https://open-meteo.com/en/docs
