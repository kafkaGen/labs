# Climate

## What it answers

How the climate is projected to change. Time horizon: 1950-01-01 to 2050-01-01. This server returns one row per year, up to 2049, for up to 5 places.

Source: https://open-meteo.com/en/docs/climate-api

## Sources and models

Seven climate models: `CMCC_CM2_VHR4`, `FGOALS_f3_H`, `HiRAM_SIT_HR`, `MRI_AGCM3_2_S`, `EC_Earth3P_HR`, `MPI_ESM1_2_XR`, and `NICAM16_8S`. Values are bias-corrected onto ERA5-Land by default.

Source: https://open-meteo.com/en/docs/climate-api

## Trust and limits

- Models disagree. This server returns the mean across models plus the lowest and highest, so the gap shows the disagreement.
- Not every model carries every variable. For example, soil moisture exists for only two models. Models without a variable are skipped.
- Only daily data exists. A call over many years, places, and models counts as many calls against the free-tier limit.

Source: https://open-meteo.com/en/docs/climate-api

## Variables

The `climate` tool returns `temperature_2m_mean` (°C), `precipitation_sum` (mm per year), and `wind_speed_10m_max` (km/h, the yearly mean of the daily maximum). Each comes back as `_mean`, `_min`, and `_max` across models. The API offers more, such as humidity, cloud cover, and radiation.

Source: https://open-meteo.com/en/docs/climate-api

## Argument tips

- `places` takes 1 to 5 latitude and longitude pairs.
- `start_year` and `end_year` run from 1950 to 2049. The defaults are 2025 and 2049.
- Use it for long-term trends. For weather on a given day, use `forecast` or `historical`.

Source: https://open-meteo.com/en/docs/climate-api
