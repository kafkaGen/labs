# Flood

## What it answers

River discharge, the volume of water flowing past a point, in m³/s. Time horizon: up to 210 days ahead in the API, and data back to 1984. This server asks for up to 92 days.

Source: https://open-meteo.com/en/docs/flood-api

## Sources and models

Discharge is computed for a grid of river cells. For a point, it uses the largest river within about 5 km.

Source: https://open-meteo.com/en/docs/flood-api

## Trust and limits

- The result gives no river name and no distance to the river.

Source: https://open-meteo.com/en/docs/flood-api

## Variables

`river_discharge` (m³/s), one value per day. The API also offers mean, median, maximum, minimum, and quartile values across ensemble members for forecasts.

Source: https://open-meteo.com/en/docs/flood-api

## Argument tips

- `days` runs from 1 to 92. The default is 30.
- Choose a point on or near the river you care about, because the result follows the largest river within about 5 km.

Source: https://open-meteo.com/en/docs/flood-api
