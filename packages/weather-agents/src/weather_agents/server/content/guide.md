# Open-Meteo guide

Open-Meteo serves weather data over HTTP. This server wraps 10 of its endpoints as tools. Read an endpoint guide at `open-meteo://endpoints/{endpoint}` for one endpoint in depth.

## Where the data comes from

- **Forecast:** numerical weather models. With no model chosen, Open-Meteo picks the best match for the location.
- **Ensemble:** several ensemble models, each run many times with slightly different starting conditions. Each run is a member.
- **Seasonal:** ECMWF SEAS5 (7 months) and EC46 (46 days), 51 members each, at 36 km resolution.
- **Historical weather:** reanalysis, which is past weather rebuilt from observations and a model. ERA5 covers 1940 to now, ERA5-Land 1950 to now, and ECMWF IFS 2017 to now.
- **Climate:** seven climate models, run from 1950 to 2050.
- **Marine:** wave models such as ECMWF WAM, GFS Wave, MFWAM, and DWD EWAM and GWAM. History comes from ERA5-Ocean.
- **Air quality:** CAMS Europe and CAMS Global.
- **Flood:** river discharge from a river model, at the largest river within about 5 km of the grid cell.
- **Elevation:** Copernicus DEM GLO-90, at 90 m resolution.
- **Geocoding:** GeoNames.

Source: https://open-meteo.com/en/docs

## Refresh and trust

- Every endpoint answers from a model grid, so a result describes a grid cell and not the exact point. The response gives the grid cell's own latitude and longitude.
- Historical weather from ERA5 lags real time by about 5 days.
- EC46 seasonal data updates daily at about 20:30 UTC. SEAS5 updates monthly, on the 5th.
- Seasonal data is not bias-corrected. It is a tendency against normal and not a forecast for a day.
- An ensemble shows how sure a forecast is. When the members agree, the forecast is firm. When they spread, it is not.
- Refresh cadence and limits differ per endpoint. The endpoint guides list them.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Shared API conventions

- Every weather endpoint takes `latitude` and `longitude`. Most accept several points as comma-separated lists, and then return one result per point.
- `timezone` defaults to GMT. Use `auto` to get times in the place's own timezone. It is required when `daily` variables are asked for. This server always sends `auto`.
- Data comes in blocks: `hourly`, `daily`, or `monthly`. Each block is one `time` array plus one array per variable, all the same length, plus a units object.
- Default units are degrees Celsius, km/h for wind, and mm for precipitation.
- Forecast accepts `past_days` from 0 to 92 and `forecast_days` from 0 to 16. This server's forecast tool does not expose `past_days`.
- An error is HTTP 400 with `{"error": true, "reason": "..."}`.

Source: https://open-meteo.com/en/docs

## Which endpoint answers what

| Question | Endpoint | Horizon |
|---|---|---|
| Weather in the next days | forecast | Today to 16 days |
| How sure is that forecast | ensemble | Within 15 days |
| Tendency beyond two weeks | seasonal | 16 days to 7 months |
| What the weather was | historical | 1940 to about 5 days ago |
| Long-term change | climate | 1950 to 2050 |
| Sea, air, rivers, terrain | marine, air-quality, flood, elevation | See each guide |

A forecast plus the ensemble spread for the same days tells you both the expected weather and how far to trust it. Historical weather over 30 years gives the normal that a forecast or seasonal anomaly is measured against.

Source: https://open-meteo.com/en/docs/ensemble-api

## What Open-Meteo cannot answer

- The flood endpoint returns discharge only. It gives no river name and no distance to the river.
- Marine data exists for the sea and the coast. An inland point returns only empty values.
- Pollen data exists only for Europe and only in season.
- Seasonal data is not a day-by-day forecast.

Source: https://open-meteo.com/en/docs/flood-api

## Attribution and terms

- The free tier is for non-commercial use, under 10,000 calls a day, 5,000 an hour, and 600 a minute. Long date ranges, many points, and many variables count as more than one call.
- Data is licensed CC BY 4.0. Credit Open-Meteo when you show it.
- Geocoding data is based on GeoNames.

Source: https://open-meteo.com/en/terms
