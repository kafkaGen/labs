# Air quality

## What it answers

Pollutant levels, the European and US air quality indexes, and pollen. Time horizon: a forecast of about 4 days for Europe and 5 days for the world. This server asks for up to 7.

Source: https://open-meteo.com/en/docs/air-quality-api

## Sources and models

CAMS Europe (forecast from October 2023, reanalysis from 2013) and CAMS Global (from August 2022). With the default `domains=auto`, Open-Meteo picks the one that fits the location.

Source: https://open-meteo.com/en/docs/air-quality-api

## Trust and limits

- Pollen exists only for Europe and only in season. Elsewhere those values are null, and this server leaves those columns out with a note.
- The API has hourly data only. This server returns the daily maximum.

Source: https://open-meteo.com/en/docs/air-quality-api

## Variables

`pm10`, `pm2_5`, `ozone`, `nitrogen_dioxide` (µg/m³), `european_aqi`, `us_aqi`, and the pollen types `alder_pollen`, `birch_pollen`, `grass_pollen`, and `ragweed_pollen` (grains/m³). The API offers more, such as carbon monoxide, dust, and UV index.

Source: https://open-meteo.com/en/docs/air-quality-api

## Argument tips

- `days` runs from 1 to 7.
- For hay fever questions, read the pollen columns, and expect them to be missing outside Europe.

Source: https://open-meteo.com/en/docs/air-quality-api
