# Seasonal

## What it answers

The tendency of the coming months against normal. Time horizon: beyond the 16-day forecast, up to 7 months ahead. It is a tendency, not a forecast for a day.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Sources and models

ECMWF SEAS5 reaches 7 months. ECMWF EC46 reaches 46 days. Both have 51 members at 36 km resolution. EC46 updates daily at about 20:30 UTC and SEAS5 monthly on the 5th.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Trust and limits

- Low confidence. The data is not bias-corrected.
- An anomaly is the forecast minus the model's own climate for that period.
- Individual member data is kept for one month. Means and spread are kept longer.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Variables

This server returns monthly anomalies: `temperature_2m_anomaly` in K (degrees above or below normal) and `precipitation_anomaly` in mm. The API also offers daily, weekly, and 6-hourly variables.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Argument tips

- `months` runs from 1 to 7 and counts the current month.
- Present the result as a tendency against normal, and label it low-confidence.
- To compare with the normal itself, call `historical` for 1991-01-01 to 2020-12-31.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api
