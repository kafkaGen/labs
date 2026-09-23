# Design: the MCP server and the MCP client

**Date:** 2026-09-23
**Status:** Draft, awaiting review
**Package:** `packages/weather-agents`

## What this builds

An MCP server over Open-Meteo, and an MCP client that talks to it. Nothing else.

No agent loop, no chat CLI, no Claude API calls except the one place the protocol
demands them. Both agent runtimes from [ADR-0001](../../adr/0001-two-agent-runtimes-over-one-tool-layer.md)
are consumers of what this produces, and both are out of scope here. The Agent SDK
brings its own MCP client; the Claude API runtime will use the client built here.
Those are later specs.

The work splits into three tracks. Tracks 1 and 2 are the deliverable. Track 3
starts only once they are both done.

| Track | Builds | Transport |
|---|---|---|
| 1 | Server: tools, resources, prompts | stdio |
| 2 | Client: calls tools, reads resources, gets prompts | stdio |
| 3 | Sampling, logging, progress, streamable HTTP, bearer auth | stdio + HTTP |

## Architecture

One uv workspace package, two modules that never import each other.

```
packages/weather-agents/
  pyproject.toml
  src/weather_agents/
    mcp_server/
      __main__.py          entry point, picks transport
      app.py               FastMCP instance, instructions, registration
      openmeteo/
        http.py            httpx wrapper, error mapping, the quirks below
        endpoints.py       one request builder per Open-Meteo endpoint
        variables.py       curated variable enums
        results.py         Pydantic result models
      tools/               one module per tool
      resources/
        content/           the how-to markdown files
      prompts/
    mcp_client/
      config.py            reads the servers config file
      session.py           connect, list, call, read, get
      sampling.py          track 3 only
  tests/
```

The split that matters is inside the server. `openmeteo/` knows about HTTP,
query parameters, and Open-Meteo's response shapes, and knows nothing about MCP.
`tools/` knows about MCP and calls into `openmeteo/`. A tool module that builds a
query string, or an `openmeteo/` module that imports `Context`, is the boundary
breaking.

The client never imports `mcp_server` and never knows the word "weather". It is
handed a server by config and speaks protocol. That is the point: the client is
where the protocol gets learned, and hardcoding the server hides half of it.

**SDK:** FastMCP, from the official `mcp` package. Its `Context` object still
exposes sampling, progress, and log notifications, so track 3 loses nothing.

**HTTP:** plain `httpx.AsyncClient`, not `openmeteo-requests`. The official client
speaks FlatBuffers for zero-copy into numpy, which an MCP server would decode only
to re-encode as JSON. It also accesses variables positionally, by request order,
which does not survive a model choosing variables at call time, and it does not
cover geocoding or elevation at all.

## Track 1: the server

### Tools

Seven endpoint tools, one per Open-Meteo endpoint, mirroring the API so the
mapping back to the docs stays obvious. Two tools that add something the API
does not.

| Tool | Endpoint |
|---|---|
| `search_locations` | `geocoding-api.open-meteo.com/v1/search` |
| `get_forecast` | `api.open-meteo.com/v1/forecast` |
| `get_historical_weather` | `archive-api.open-meteo.com/v1/archive` |
| `get_air_quality` | `air-quality-api.open-meteo.com/v1/air-quality` |
| `get_marine_forecast` | `marine-api.open-meteo.com/v1/marine` |
| `get_elevation` | `api.open-meteo.com/v1/elevation` |
| `get_river_discharge` | `flood-api.open-meteo.com/v1/flood` |
| `get_local_time` | none, reads the machine |
| `decode_weather_code` | none, a lookup table |

`get_local_time` returns the machine's IANA timezone and current local time, so a
model can resolve "tomorrow" without asking. It does not geolocate. Nothing in
this package calls a third-party location service, which would break
[ADR-0002](../../adr/0002-open-meteo-as-the-single-data-domain.md).

### What tools return

A condensed Pydantic model, emitted as MCP structured content with an output
schema alongside a short text rendering.

Raw passthrough is not viable. A 16-day hourly forecast with ten variables is
several thousand numbers, which is expensive to send and which models read badly.
It is also expensive in the literal sense: Open-Meteo's free tier bills a request
asking for more than 10 variables or more than 2 weeks of data as several calls,
fractionally, so a naive request burns quota faster than the request count
suggests.

So every result model:

- inlines units next to values rather than shipping a parallel `hourly_units` object
- carries only the variables that were asked for
- caps returned rows at a documented limit and says in the payload when it truncated

### Variable selection

A curated enum of around fifteen useful variables per dataset, with a default set
when the caller passes none. The complete Open-Meteo variable list lives in the
`weather://howto/variable-selection` resource, not in the tool schema. A 50-value
enum in a tool schema is tokens paid on every single call for a list the model
needs once.

### Errors

A tool result marked `isError`, with a message written for the model to act on.
Protocol-level errors stay for unknown tools and malformed arguments. An ambiguous
place name returns the candidate list so the model can ask which one.

Open-Meteo's real behaviour, all verified against the live API, is what this has
to absorb:

- **A missing required parameter returns HTTP 200 with a zero-byte body.** The
  status check passes and the JSON parser throws. Validate before sending, and
  treat an empty body as an error.
- **Errors are HTTP 400 with `{"error": true, "reason": "..."}`.** The `reason`
  string leaks Swift generic type names: a typo in a variable name produces
  `Cannot initialize SurfacePressureAndHeightVariable<VariableAndPreviousDay, ...>
  from invalid String value tempeture_2m`. Map these to something a model can use.
  Never pass them through.
- **Error messages misreport the value you sent.** `forecast_days=20` is rejected
  with "Allowed range 0 to 16. Given 16", echoing the clamped value.
- **Geocoding omits the `results` key entirely on no match.** It returns 200 and
  `{"generationtime_ms": 0.51}`. Use `.get("results", [])`.
- **Marine returns 200 with all-null arrays for inland coordinates.** No error,
  no signal but the nulls. Detect and say so.
- **`timezone` is documented as required with `daily` and is not enforced.**
  Omitting it silently gives GMT-boundary days, so "daily max" spans the wrong 24
  hours anywhere outside UTC. Default `timezone=auto` on every daily request.
- **The archive's 5-day reanalysis lag is hidden by the default model.** Explicit
  `models=era5` for last week returns nulls; the default `best_match` fills the gap
  with ECMWF IFS. Do not expose a model selector.
- **Documented ranges are wrong in places.** Verified live: forecast 0–16, marine
  0–16 despite docs saying 0–8, air quality 0–7, flood 0–210, `past_days` 0–92.
- **Elevation has no metadata wrapper.** It returns `{"elevation": [38.0]}`,
  always an array, capped at 100 coordinates.

No caching and no retry. One person at a terminal will not approach 10,000 calls a
day, and a cache is speculative work that teaches nothing about MCP. A 429 is a
normal tool error.

### Resources

Two, one of them templated.

- `weather://guide/open-meteo` — static. What Open-Meteo is, what each of the seven
  wrapped datasets covers, what it cannot answer, and which tool to reach for. This
  is the orientation brief that gives a model enough context to pick correctly.
- `weather://howto/{topic}` — templated, the one with arguments. Topics:
  `location-search`, `date-ranges`, `variable-selection`, `reading-a-response`.
  Each is a short markdown file under `resources/content/`.

Open-Meteo's CC-BY attribution, required by ADR-0002, appears in the guide resource
and in the server's `instructions` string, so any connected client sees it once.

### Prompts

Two, both with arguments.

- `plan_outdoor_activity(activity, location, date_range)` — the compound question
  from the vision, as a reusable prompt.
- `daily_briefing(location)` — structured what-to-expect-today.

### Running it

```make
mcp-inspector:   npx @modelcontextprotocol/inspector uv run weather-mcp
mcp-server:      uv run weather-mcp
```

Node 25 and npx are already on this machine, so the Inspector needs no setup.

Track 1 is done when every tool, both resources, and both prompts are visible and
callable in the Inspector's web UI.

## Track 2: the client

A protocol client, weather-agnostic, that:

- reads a config file to find a server
- opens a session over stdio and completes initialization
- lists and calls tools, reading structured content and `isError` results
- lists resources and resource templates, and reads both, including expanding the
  `{topic}` template
- lists prompts and gets them with arguments, returning the rendered messages

**Config format:** JSON with an `mcpServers` map, the same shape Cursor and Claude
Desktop use. `command` plus `args` for stdio, `url` plus `headers` for HTTP in
track 3. Familiar, and it transfers.

Nothing interactive drives it. pytest is the proof, running against the real
server over stdio.

Track 2 is done when a test connects to the server, calls every tool, reads both
resources, gets both prompts with arguments, and asserts on what comes back.

## Track 3: the advanced surface

Only after 1 and 2 both pass. Five pieces.

### Sampling

One new tool, `conditions_briefing(location, activity)`. It geocodes the place,
then fetches forecast, air quality, and marine in sequence, then asks the client's
LLM via `sampling/createMessage` to merge the three into one narrative. Several
upstream calls and then a sampling call, which is what makes it the right home for
progress reporting as well.

The client's sampling handler calls the Anthropic Messages API for real and returns
the completion. Single-shot, no loop, no agent. Tests inject a fake handler so they
cost nothing.

### Structured logging

MCP log notifications are the primary channel, so the client receives and renders
them: what a tool is doing, what it got back, warnings for degraded results such as
marine nulls inland. The client asserts on received notifications in tests.
Standard Python logging to stderr runs alongside for server-process diagnostics
that no client should see.

### Progress

Only tools doing genuinely multi-step work: `conditions_briefing`, and any tool
that makes more than one upstream call. A single-call tool reporting progress is
noise.

### Transports

Streamable HTTP added beside stdio, in both stateless and stateful modes, with
stdio still working. Selected by a flag on the server entry point, and by whether
the client's config entry carries `command` or `url`.

Stateless HTTP cannot send a request back to the client, so sampling is impossible
there. `conditions_briefing` detects this up front, emits a warning log
notification, and returns the merged forecast, air quality, and marine data without
the narrative, saying in the result that the summary was skipped because the
transport cannot support sampling. Degraded but useful beats an error.

### Authorization

A static bearer token on the HTTP transport. The server rejects requests without
it; the client sends it from the `headers` block in its config. Small, and it makes
the 401 path real. Not the spec's OAuth 2.1 flow, which is a project of its own.

Dropped from track 3 after discussion: list-changed notifications, for want of
anything that genuinely changes at runtime.

## Testing

pytest is stood up as part of track 1. The Makefile already has a commented-out
`test` target waiting; this uncomments it and adds `test` to the `pre-commit`
target.

Three layers.

1. **Unit tests over recorded fixtures.** Real captured Open-Meteo responses,
   including the pathological ones: the empty body, the missing `results` key, the
   inland marine nulls, the Swift-leaking 400. No network.
2. **Integration tests against the real server**, launched in-process, covering
   every tool, resource, and prompt.
3. **A live smoke suite** behind a pytest marker, excluded from the default run,
   that hits Open-Meteo for real so drift in the API surfaces eventually.

For track 3's transports, the integration suite is parameterised over stdio,
stateful HTTP, and stateless HTTP, driving the server's ASGI app through an
in-memory transport rather than binding ports. Every assertion holds in all three
modes except the sampling one, which expects a narrative under stdio and stateful
HTTP and expects the degraded result plus a warning notification under stateless.
That parameterisation is the test that the transports actually behave.

## Decisions taken here, deliberately

- **stdio first, HTTP in track 3.** stdio is MCP's simplest transport and the one
  the Inspector drives with no setup. The vision requires both eventually.
- **One tool per endpoint** rather than narrow purpose-built tools. Fewer tools,
  and the mapping to Open-Meteo's docs stays legible.
- **No geolocation of any kind.** Local time only.
- **No agent, no CLI.** Reversed mid-session from an earlier decision to include
  the Claude API loop. Keeping them out is what keeps this spec one spec.

## What is not settled

Nothing blocking. Two things to decide while building rather than now:

- The exact variable list in each curated enum, which wants a pass over the real
  response once the first tool works.
- Row caps per tool, which want a look at actual payload sizes.
