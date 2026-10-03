# Historical weather

## What it answers

What the weather was at a point, for any period since 1940. Time horizon: 1940-01-01 up to today. The newest days can be empty.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Sources and models

Reanalysis datasets: ERA5 (1940 to now), ERA5-Land (1950 to now), and ECMWF IFS (2017 to now). With no model chosen, Open-Meteo blends them.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Trust and limits

- ERA5 is delivered with a 5-day delay. The default blend also uses ECMWF IFS, so the newest days often have data. When they do not, the tool leaves those days out and says how many.
- Different models carry different variables, so a request tied to one model can come back with empty columns.
- This server summarises long spans: up to 31 days one row per day, up to 2 years one row per month, and longer 12 rows with the average of each calendar month.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Variables

The `historical` tool takes `temperature` (`temperature_2m_max`, `temperature_2m_min`, °C), `precipitation` (`precipitation_sum`, mm), and `wind` (`wind_speed_10m_max`, km/h). The API offers more, such as radiation sums, evapotranspiration, and sunshine duration.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Argument tips

- `start_date` and `end_date` are dates like `2024-01-31`.
- For a 30-year normal, ask for 1991-01-01 to 2020-12-31. The result has one row per calendar month. For precipitation, the value is the average monthly total.
- Compare a recent period with a normal by calling the tool twice.

Source: https://open-meteo.com/en/docs/historical-weather-api
