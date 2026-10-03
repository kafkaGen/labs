# Geocoding

## What it answers

A place name to coordinates, elevation, timezone, country, region, and population. `/v1/search` finds places by name. `/v1/get` returns one place by its id. It has no time horizon.

Source: https://open-meteo.com/en/docs/geocoding-api

## Sources and models

Location data is based on GeoNames.

Source: https://open-meteo.com/en/docs/geocoding-api

## Trust and limits

- Search matches names by prefix from 3 characters. With 2 characters it matches the exact name. Shorter searches return nothing.
- `count` runs from 1 to 100.
- When geocoding finds several places with the same name, the name is ambiguous. Check country, region, and population to tell them apart.
- Empty fields are left out of a result.

Source: https://open-meteo.com/en/docs/geocoding-api

## Variables

Each result has `id`, `name`, `latitude`, `longitude`, `elevation`, `timezone`, `feature_code`, `country_code`, `country`, `population`, and `admin1` to `admin4` for the regions above the place. The tools return the fields `id`, `name`, `latitude`, `longitude`, `elevation`, `timezone`, `country`, `country_code`, `admin1`, and `population`.

Source: https://open-meteo.com/en/docs/geocoding-api

## Argument tips

- Add `country_code` (two letters, such as `US`) to narrow an ambiguous name.
- The name can carry a qualifier after a comma, such as `Paris, France`. It must match exactly.
- `geocode_get` takes the `id` from a `geocode_search` result.

Source: https://open-meteo.com/en/docs/geocoding-api
