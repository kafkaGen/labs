# Open-Meteo MCP server scope

What the MCP server implements from the Open-Meteo API: its tools, prompts, and resources.

## Endpoints to implement

Each endpoint is its own tool. Every tool description states the time horizon it covers, so the agent picks the right one without a routing tool.

| Family | Endpoint | What it answers |
|---|---|---|
| Geocoding | `geocoding-api.open-meteo.com/v1/search`, `/v1/get` | Place name to coordinates and timezone. An ambiguous name returns the candidates. |
| Forecast | `api.open-meteo.com/v1/forecast` | Today out to 16 days |
| Ensemble (mean and spread only) | `ensemble-api.open-meteo.com/v1/ensemble` | How sure a forecast within 16 days is. No raw members. |
| Seasonal | `seasonal-api.open-meteo.com/v1/seasonal` | 16 days to 7 months, as a tendency against normal, labelled low-confidence |
| Historical weather | `archive-api.open-meteo.com/v1/archive` | Any period since 1940. Up to a month in detail, longer spans summarised. |
| Climate | `climate-api.open-meteo.com/v1/climate` | Projection to 2050, summarised, showing how far the models disagree. Up to 5 places per question. |
| Marine | `marine-api.open-meteo.com/v1/marine` | Waves, swell, currents, sea surface temperature, tide and surge sea level |
| Air quality | `air-quality-api.open-meteo.com/v1/air-quality` | Pollutants, European and US AQI, pollen |
| Flood | `flood-api.open-meteo.com/v1/flood` | River discharge |
| Elevation | `api.open-meteo.com/v1/elevation` | Terrain height for one or more points |

## Tools beyond the endpoints

### Local time at a place

The caller passes a location and gets the local date and time there, plus sunrise, sunset, and day length. Relative timeframes such as "this weekend" resolve to dates in that place's timezone.

**Ambiguous place names.** A name is ambiguous when geocoding returns more than one place with that name and the caller gave no country or region to narrow it, as with "Springfield" or "Paris". The tool then uses MCP elicitation to ask the user to pick one. Each candidate is shown with its country, region, and population. The tool continues with the chosen place. If the user declines or cancels, the tool returns an error saying the place was not resolved. If the client does not support elicitation, the tool returns the candidates so the agent can ask the user itself.

### Location dossier

The caller passes a place and gets a short summary and a full report on its weather and climate. This is the tool that exercises progress notifications, log notifications, and sampling.

**Data it gathers.** It geocodes once, then fetches these in parallel:

| Section | Source |
|---|---|
| Next 16 days | Forecast, with ensemble mean and spread for confidence |
| Up to 7 months | Seasonal, labelled low-confidence |
| Last 14 days against normal | Forecast `past_days` for the recent days (the archive lags a few days), compared with the 1991 to 2020 normal for the same calendar days |
| Seasons | Monthly normals from the same archive call. The server decides whether the place has distinct seasons. |
| Observed climate change | Archive, recent decades against 1961 to 1990 |
| Projected climate change | Climate, to 2050, with model disagreement |
| Marine | Marine. Skipped when the place is inland, which the server detects from empty marine data. |
| Air quality | Air quality |
| River | Flood, river discharge at the nearest river grid cell. Open-Meteo cannot name the river or give its distance. |
| Terrain | Elevation at the point and at a ring of nearby points, giving local relief |

One long archive call covers the normal, the seasons, and the observed change.

**Notifications.** A progress notification fires each time a source returns, then once when the report starts and once when it finishes. The total is the number of sources plus two. If a source fails or is skipped, the rest still come back and a log notification names the missing part. If the client cancels, outstanding fetches stop.

**Sampling.** One sampling call at the end turns the gathered data into the summary and the report. The tool returns only those, not the raw data. The prompt itself is left for the prompts discussion.

**Without sampling.** If the client does not support sampling, the tool returns the gathered data as structured sections and sends a log notification saying no report was written.

## Prompts

1. **Weekend check** (no arguments). The model asks the user where they are, uses the local-time tool to turn "this weekend" into dates in that place's timezone, and calls forecast and ensemble for those days. It answers which day is better, how sure the forecast is, and why.
2. **Compare places for a trip** (arguments: `places`, `month`). `places` is up to 5 place names in one comma-separated string. MCP prompt arguments are plain strings, so the model splits the list itself. For each place the model compares the 30-year normals for that month from historical weather, plus the seasonal outlook when the month is within 7 months. It answers which place suits the trip best and labels the seasonal part low-confidence.

## Resources

Resources hold depth, not what a call needs. The client decides when a resource is read, so anything the agent needs to call a tool correctly also goes in that tool's description. Resource content is written from Open-Meteo's published documentation. Nothing invented.

1. **Open-Meteo guide** (static, `open-meteo://guide`). The whole service in one read:
   - Where the data comes from: weather models for forecasts, reanalysis for history, and separate model families for air quality, marine, flood, and climate.
   - How often data refreshes in general, and how far each kind of data can be trusted.
   - API conventions shared by every endpoint: coordinates, timezone, units, `past_days`, hourly against daily data.
   - Which endpoint answers which time horizon, and how endpoints combine. Example: a forecast plus the ensemble spread tells you how sure the forecast is.
   - What Open-Meteo cannot answer, such as river names, routes, or live observations.
2. **Endpoint guide** (template, `open-meteo://endpoints/{endpoint}`). One endpoint in depth:
   - What it answers and its time horizon.
   - Its sources and models, resolution, and update cadence.
   - How far it can be trusted, and its known limits.
   - The variables it offers, with units.
   - Argument tips that get better results.

   The endpoint names are `geocoding`, `forecast`, `ensemble`, `seasonal`, `historical`, `climate`, `marine`, `air-quality`, `flood`, and `elevation`. The server offers argument completion for `{endpoint}`. An unknown name returns an error.
