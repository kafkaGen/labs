# Design: Open-Meteo MCP server, level 1

**Date:** 2026-10-03
**Implements:** use cases 1, 2, and 3 of [PRD-0001](../../prd/0001-open-meteo-mcp-server-and-client.md). The MCP client (use case 4) gets its own spec.
**Behaviour source:** [`open-meteo-mcp-scope.md`](../../open-meteo-mcp-scope.md). This spec adds argument names, limits, and result shapes. It adds no behaviour the scope doc does not describe, except the deviations listed at the end.
**Built on:** the official `mcp` 2.x SDK ([ADR-0003](../../adr/0003-official-mcp-sdk-over-fastmcp.md)).

## Goal

A stdio MCP server with 11 endpoint tools, 2 prompts, and 2 resources, that I can drive from MCP Inspector with one command. Level 2 features (local-time tool, dossier, HTTP, auth, sampling, elicitation) are out.

This is a study project, so each choice below is the simplest one that works. Where a choice is arbitrary, it says so and stays arbitrary.

## Package layout

New files under `packages/weather-agents/`:

```
pyproject.toml                  uv workspace member, src layout, Python 3.12
Makefile                        inspect, test, test-live
src/weather_agents/server/
    __main__.py                 mcp.run() over stdio
    app.py                      create_server(); module-level `mcp = create_server()`
    state.py                    AppState: the OpenMeteoClient and the clock
    models.py                   result models and the Latitude, Longitude, Coordinates types
    openmeteo/                  knows HTTP and response shapes, nothing about MCP
        client.py               OpenMeteoClient, OpenMeteoError, endpoint URLs
        tables.py               Table model, rollup(), ensemble stats, climate stats
        variables.py            logical variable names -> Open-Meteo names
    tools/                      thin MCP wrappers over openmeteo/, one register(mcp) per module
        common.py               error-mapping decorator, state and location helpers
        geocoding.py            geocode_search, geocode_get
        forecast.py             forecast, ensemble, seasonal
        history.py              historical, climate
        environment.py          marine, air_quality, flood, elevation
    resources.py                guide, endpoint template, completion handler
    prompts.py                  weekend_check, compare_places
    content/
        guide.md
        endpoints/<name>.md     10 files
tests/
    fakes.py, conftest.py       Open-Meteo response builders and a MockTransport router
    unit/  server/  live/
```

Dependencies: `mcp[cli]>=2,<3` and `httpx`. The SDK now uses `httpx2` internally, so `httpx` is our own dependency. Dev: `pytest`. The SDK's `anyio` plugin runs async tests, so there is no `pytest-asyncio`.

`openmeteo/` imports nothing from `mcp`. `tools/common.py` is the only place that turns an `OpenMeteoError` into a `ToolError`.

## Server assembly

```python
def create_server(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    today: Callable[[], date] = date.today,
) -> MCPServer: ...
```

- A lifespan opens one `httpx.AsyncClient(timeout=30, transport=transport)`, wraps it in an `OpenMeteoClient`, and yields `AppState(openmeteo, today)`. Tools read it from `ctx.request_context.lifespan_context`.
- Tests pass a `MockTransport` and a fixed `today`. Production passes neither.
- The server `instructions` carry the Open-Meteo CC-BY attribution and one line: pick the tool by time horizon.
- Logging goes to stderr through Python `logging`. Nothing writes to stdout, because stdout is the protocol. Log files are out of scope in the PRD.
- Start command: `python -m weather_agents.server`. Level 2 adds the transport argument to this entry point.
- `make inspect` runs `mcp dev` against `app.py`, which needs `npx` on `PATH`. Node stays a dev-only dependency.

## Tools

All tools are `async`, read-only, and return typed models, so the SDK publishes an `outputSchema` and structured content. Every weather tool takes `latitude` (-90 to 90) and `longitude` (-180 to 180) and sends `timezone=auto`. Each description starts with its time horizon.

| Tool | Arguments (default) | Horizon sentence in the description |
|---|---|---|
| `geocode_search` | `name` (2+ chars), `country_code=None`, `count=5` (1 to 100) | Place name to coordinates and timezone. Several results means the name is ambiguous. |
| `geocode_get` | `id` | Look up one place by its geocoding id. |
| `forecast` | `days=7` (1 to 16), `hourly=False`, `variables` | Today out to 16 days. |
| `ensemble` | `days=7` (1 to 15), `variables` | How sure a forecast is, within 15 days. Mean and spread only. |
| `seasonal` | `months=3` (1 to 7) | 16 days to 7 months, a tendency against normal. Low confidence. |
| `historical` | `start_date`, `end_date`, `variables` | Any period since 1940. Up to 31 days in detail, longer spans summarised. |
| `climate` | `places` (1 to 5 coordinate pairs), `start_year=2025`, `end_year=2049` | Projection to 2049, summarised per year, with the spread between models. |
| `marine` | `days=5` (1 to 7) | Waves, swell, currents, sea surface temperature, sea level. Coastal and open water only. |
| `air_quality` | `days=3` (1 to 7) | Pollutants, European and US AQI, pollen. Pollen is Europe only. |
| `flood` | `days=30` (1 to 92) | River discharge at the nearest river cell. |
| `elevation` | `points` (1 to 100 coordinate pairs) | Terrain height. |

**Variables.** Only `forecast`, `ensemble`, and `historical` take `variables`, a list of logical names. `variables.py` maps each name to Open-Meteo's daily or hourly name. The tool description lists the allowed names. Everything else is a fixed bundle, so there is no variable argument.

| Logical name | Daily (Open-Meteo) | Hourly (Open-Meteo) | Tools |
|---|---|---|---|
| `temperature` | `temperature_2m_max`, `temperature_2m_min` | `temperature_2m` | forecast, ensemble, historical |
| `precipitation` | `precipitation_sum` | `precipitation` | forecast, ensemble, historical |
| `wind` | `wind_speed_10m_max` | `wind_speed_10m` | forecast, ensemble, historical |
| `gusts` | `wind_gusts_10m_max` | `wind_gusts_10m` | forecast |
| `precipitation_probability` | `precipitation_probability_max` | `precipitation_probability` | forecast |
| `uv_index` | `uv_index_max` | `uv_index` | forecast |
| `weather_code` | `weather_code` | `weather_code` | forecast |

Defaults: forecast uses `temperature`, `precipitation`, `wind`, `weather_code`. Ensemble and historical use `temperature`, `precipitation`, `wind`. Hourly forecasts are limited to `days <= 3` to keep the result small.

**Result shape.** One columnar model serves every tool:

```python
class Table(BaseModel):
    time: list[str]  # ISO dates, months ("2024-03"), or years
    units: dict[str, str]
    columns: dict[str, list[float | int | None]]
    weekday: list[str] | None = None  # "Saturday", ... on raw daily tables only


class WeatherResult(BaseModel):
    location: Location  # grid latitude, longitude, elevation, timezone
    kind: Literal["hourly", "daily", "monthly", "climatology", "yearly"]
    table: Table
    notes: list[str] = []  # caveats the model should repeat
```

Other result types: `PlaceList` and `Place` for geocoding, `ClimateResult(places: list[WeatherResult])`, and `ElevationResult(points: list[ElevationPoint])`. Each result type is a class with annotated fields, so the SDK builds its output schema.

**Per-tool behaviour**

- **ensemble.** Requests daily variables for `ecmwf_ifs025` (51 members). Open-Meteo returns each member as its own key (`temperature_2m_max`, `temperature_2m_max_member01`, and so on). The server computes the mean and the population standard deviation across all keys with that prefix, per day. The result has columns `<name>_mean` and `<name>_std` and never the members.
- **seasonal.** Requests `monthly=temperature_2m_anomaly,precipitation_anomaly` (checked live on 2026-10-03: anomalies in K and mm, one row per month) with `forecast_days = min(months * 31, 216)`, then keeps the first `months` rows. A fixed low-confidence sentence goes in `notes`.
- **historical.** `start_date >= 1940-01-01`, `end_date <= today`, `start_date <= end_date`. The span decides the shape: up to 31 days returns daily rows; up to 730 days returns monthly rows; longer returns a 12-row climatology (mean per calendar month across the years, with the year count in `notes`). Precipitation sums within a month. Every other variable averages. The newest days can be null, since ERA5 lags about 5 days and the default blend only sometimes fills them. Trailing all-null rows are left out and `notes` gives the count. Partial months at either end are averaged as they are, and `notes` says that.
- **climate.** Requests all 7 models for `temperature_2m_mean`, `precipitation_sum`, and `wind_speed_10m_max`. Per model it computes yearly values (mean, sum, mean). Across models it returns `<name>_mean`, `<name>_min`, and `<name>_max`, skipping models that lack the variable. Requires `1950 <= start_year <= end_year <= 2049`. Always sends coordinates as lists and normalises the single-object reply to a list.
- **marine.** Requests hourly waves, swell, ocean current, sea surface temperature, and sea level height, rolled up to daily rows (max for waves, swell, current, and sea level; mean for temperature). If every value is null, the point is inland: the result has an empty table and a note saying so. It is not an error.
- **air_quality.** Requests hourly `pm10`, `pm2_5`, `ozone`, `nitrogen_dioxide`, `european_aqi`, `us_aqi`, and four pollen types, rolled up to daily maximums. All-null columns are dropped, with a note naming them.
- **flood.** Requests daily `river_discharge`. The note says Open-Meteo gives no river name or distance.
- **elevation.** Sends the points as comma-separated lists and zips the reply back to coordinates.
- **geocode_search.** Sends `language=en`. A reply with no `results` key becomes an empty `PlaceList`.

`rollup(table, key, how)` is one function: it groups rows by a key function over `time` and applies `max`, `mean`, or `sum` per column. Daily, monthly, and yearly rollups all use it.

## Errors

All errors are error results, and the server keeps serving the next call.

| Cause | Where caught | Result |
|---|---|---|
| Wrong type or range (`latitude` 95, `count` 0, `days` 20) | The SDK's argument validation, before the function runs | Automatic error result naming the argument. No HTTP call. |
| Rule the type cannot express (date outside 1940 to today, `end_date` before `start_date`, hourly with `days > 3`, `end_year` before `start_year`). Unknown variable names are caught by the SDK, because `variables` is a list of literals. | Explicit checks at the top of the tool, using `state.today()` | `ToolError("Argument 'end_date': ...")`. No HTTP call. |
| Open-Meteo 400 | `OpenMeteoClient` | `OpenMeteoError(cause="rejected", reason=<their reason>)` |
| HTTP 429 | `OpenMeteoClient` | `OpenMeteoError(cause="rate_limited")` |
| HTTP 5xx | `OpenMeteoClient` | `OpenMeteoError(cause="server_error", status=<code>)` |
| Timeout (30 s) | `OpenMeteoClient` | `OpenMeteoError(cause="timeout")` |
| Network failure | `OpenMeteoClient` | `OpenMeteoError(cause="unreachable")` |

A decorator on each tool turns `OpenMeteoError` into `ToolError("Open-Meteo <cause>: <reason>")`. There are no retries. Open-Meteo sometimes answers 400 with only `{"reason": "Bad Request"}`, and the message passes that through as it is.

## Resources

- `open-meteo://guide`: static, `text/markdown`, read from `content/guide.md`. Sections follow the scope doc's list: data sources, refresh and trust, shared API conventions, which endpoint covers which horizon, what Open-Meteo cannot answer. A final section carries the CC-BY attribution.
- `open-meteo://endpoints/{endpoint}`: a template over the 10 names `geocoding`, `forecast`, `ensemble`, `seasonal`, `historical`, `climate`, `marine`, `air-quality`, `flood`, `elevation`. Each file has the five parts the scope doc lists. The tool's own `variables` names and limits appear in the file too.
- An unknown name raises `ResourceNotFoundError` listing the valid names.
- One `@mcp.completion()` handler returns the endpoint names that start with the typed text, and `None` for any other reference.
- Static resources cannot take `Context`, so the markdown is read by a module-level function with a cache.

**Sourcing rule.** Every `##` section of every content file ends with a line `Source: <Open-Meteo docs URL>`. A claim with no page behind it is deleted, not softened. Content is written from the Open-Meteo pages listed in the research for this spec, and each endpoint file also links its page. A test fails on a section with no `Source:` line.

## Prompts

Both are `@mcp.prompt()` functions that return messages. The wording is written during implementation with the `writing-llm-prompts` skill. This spec fixes what each must tell the model.

- **`weekend_check`** (no arguments). Ask the user where they are. Call `geocode_search`, and if several places come back, ask which one. Call `forecast` with `days=10` for the chosen place. Take the Saturday and Sunday dates from the returned `time` column, which is already in the place's timezone, then call `ensemble` for the same place. Answer which day is better, how sure the forecast is, and why. Level 2 swaps the date step for the local-time tool.
- **`compare_places`** (`places`, `month`; both strings).
  - Validation, raising `MCPError(INVALID_PARAMS, "Invalid argument 'places': ...")`: more than 5 comma-separated names, or an empty list; `month` that is not 1 to 12 or an English month name, in full or in three letters.
  - Messages: split `places` on commas; for each, call `geocode_search`, then `historical` for 1991-01-01 to 2020-12-31 and read the row for the month (the tool returns a 12-row climatology for that span); if the month starts within 7 months of the date given in the message, also call `seasonal` and label that part low-confidence; answer which place suits the trip best.
  - The prompt embeds a `seasonal_months` value computed from the server clock, which says whether and how far `seasonal` reaches for the chosen month. The model does no date math. `seasonal` leaves out trailing months the API has no data for, and `notes` says so.

## Tests

| Layer | What it covers | Upstream |
|---|---|---|
| `tests/unit/` | `rollup`, ensemble stats, climate stats, variable mapping, `OpenMeteoClient` error mapping | None. Plain data or `MockTransport`. |
| `tests/server/` | Every tool, resource, and prompt through the in-memory `Client(mcp)`. Covers all acceptance criteria of use cases 1 to 3. | `MockTransport` routed by URL, answering with builders in `tests/fakes.py` shaped after real responses probed on 2026-10-03. An unmatched request fails the test. |
| `tests/server/` guides | Every `##` section has a `Source:` line. The guide has the sections the scope doc lists. All 10 endpoint files exist. | None. |
| `tests/server/` stdio | Spawns `python -m weather_agents.server` over stdio, lists tools, resources, and prompts, reads the guide, and gets a prompt. | None. No tool is called. |
| `tests/live/` | One `@pytest.mark.live` test spawns the stdio server and calls `geocode_search` and `forecast` for real. | Real Open-Meteo. |

- `make test` runs everything except `live`. `make test-live` runs the live tests: every tool, resource, and prompt, through a real stdio server.
- Builders are used instead of recorded files because the historical and climate cases need tens of thousands of rows. The live test catches drift between the builders and the real API.
- Criteria worth naming: every tool has an `outputSchema` and returns structured content; the ensemble result has no `_member` column; climate with 6 places returns an error naming `places` and records no HTTP request; a 500 fixture on one call does not stop the next call.

## Deviations from the scope doc

These come from the research for this spec. The scope doc itself is not edited here.

- **Ensemble horizon is 15 days, not 16.** The chosen model, ECMWF IFS 0.25, runs 15 days.
- **Climate ends at 2049, not 2050.** Open-Meteo's data ends on 2050-01-01, so 2049 is the last full year.
- **Ensemble spread is the standard deviation.** The scope doc says only "spread".
- **Daily tables carry a `weekday` list.** Models get date math wrong, and the weekend check needs the Saturday and Sunday rows. Added to raw daily tables only.
- **`forecast` has no `past_days`.** The scope doc routes "the last 14 days against normal" to `forecast` with `past_days`. The tool leaves it out (YAGNI), and `historical` covers past days. The guide says so.
- **Guide content drops two claims.** "Routes" and "live observations" are not backed by any Open-Meteo page, so the guide's "cannot answer" section lists only what the docs and the API responses show.

## Checked before the plan

Verified live on 2026-10-03, so the plan relies on them:

- `ecmwf_ifs025` works for the ensemble: 51 members, and day 16 comes back null, so 15 days is the real limit.
- `/v1/seasonal` accepts `monthly=temperature_2m_anomaly,precipitation_anomaly`.
- `/v1/get?id=` returns one place object with no `results` key.
- A single-place climate call returns an object, and a multi-place call returns a list.
- The error-mapping decorator keeps the tool signature visible to the SDK (checked on `mcp` 2.3.0).

Not verifiable headlessly: `make inspect` was started and began installing Inspector, but the browser UI was not exercised. That is a manual check at the end.

## Out of scope

The MCP client, the local-time tool, the dossier, HTTP transports, authorization, sampling, elicitation, progress and log notifications, the Click CLI, log files, and a console script.
