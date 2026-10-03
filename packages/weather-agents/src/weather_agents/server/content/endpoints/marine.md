# Marine

## What it answers

Sea conditions: waves, swell, ocean currents, sea surface temperature, and sea level height. Time horizon: this server asks for up to 7 days ahead. History from ERA5-Ocean runs from 1940.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Sources and models

Wave models: ECMWF WAM, GFS Wave, MFWAM, and DWD EWAM and GWAM. ERA5-Ocean covers history, with a 5-day delay.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Trust and limits

- Only the sea and the coast have data. An inland point returns a valid response whose values are all null. This server returns an empty table with a note for it.
- Sea level height may be unreliable further inland.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Variables

`wave_height` (m), `wave_period` (s), `swell_wave_height` (m), `ocean_current_velocity` (km/h), `sea_surface_temperature` (°C), and `sea_level_height_msl` (m). The API offers more, such as wave and swell directions, wind waves, and secondary swells. This server returns one row per day: the daily maximum, except sea surface temperature, which is the daily mean.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Argument tips

- `days` runs from 1 to 7.
- Use a point on the coast or in open water. If the result is empty, the point is inland.

Source: https://open-meteo.com/en/docs/marine-weather-api
