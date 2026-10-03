# Elevation

## What it answers

Terrain height in metres for one or more points. It has no time horizon, because terrain does not change.

Source: https://open-meteo.com/en/docs/elevation-api

## Sources and models

Copernicus DEM GLO-90, a digital elevation model at 90 m resolution.

Source: https://open-meteo.com/en/docs/elevation-api

## Trust and limits

- At most 100 points per call.

Source: https://open-meteo.com/en/docs/elevation-api

## Variables

`elevation` in metres, one value per point, in the order the points were given.

Source: https://open-meteo.com/en/docs/elevation-api

## Argument tips

- Pass several points in one call. A ring of nearby points around a place shows how hilly it is: compare the highest and lowest value.

Source: https://open-meteo.com/en/docs/elevation-api
