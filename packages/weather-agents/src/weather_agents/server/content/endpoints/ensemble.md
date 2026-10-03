# Ensemble

## What it answers

How sure a forecast is. An ensemble runs a weather model many times from slightly different starting points. Each run is a member. When members agree the forecast is firm, and when they spread it is not. Time horizon: this server uses a model that runs 15 days.

Source: https://open-meteo.com/en/docs/ensemble-api

## Sources and models

Open-Meteo offers many ensemble models, for example ECMWF IFS 0.25° (51 members, 15 days), GFS 0.25° (31 members, 10 days), ICON-EPS (40 members, 7.5 days), and GEM (21 members, 16 days). This server uses ECMWF IFS 0.25°. Data is interpolated to hourly, and some models are 6-hourly later in their range.

Source: https://open-meteo.com/en/docs/ensemble-api

## Trust and limits

- The API returns every member as its own variable, such as `temperature_2m_max_member01`. This server never returns members. It returns the mean and the standard deviation across members for each day.
- On the last day of a model's range, values can be null.
- A larger standard deviation means a less certain forecast.

Source: https://open-meteo.com/en/docs/ensemble-api

## Variables

Daily variables offered by this server: `temperature` (`temperature_2m_max`, `temperature_2m_min`, °C), `precipitation` (`precipitation_sum`, mm), and `wind` (`wind_speed_10m_max`, km/h). Each comes back as `<name>_mean` and `<name>_std`. The API offers more variables, such as cloud cover, snow, and soil values.

Source: https://open-meteo.com/en/docs/ensemble-api

## Argument tips

- `days` runs from 1 to 15.
- Call it with the same `days` as `forecast`, and compare the `_std` of the days you care about.
- Daily rows carry a `weekday` for each date.

Source: https://open-meteo.com/en/docs/ensemble-api
