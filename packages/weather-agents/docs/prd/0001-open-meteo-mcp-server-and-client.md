# PRD: Open-Meteo MCP server and MCP client

**Status:** Building
**In one line:** An MCP server that gives agents Open-Meteo's data through tools, resources, and prompts, grown in two maturity levels up to the advanced protocol surface, plus a server-agnostic MCP client for the future agent loop.
**Serves:** "an MCP server I wrote" from the goal in [`../vision.md`](../vision.md), and the in-scope lines on the three primitives, both transports, and the advanced protocol surface.

## Why this feature

Nothing in the package runs yet, and every later piece needs this one: neither agent runtime has anything to call until the server exists, and the API runtime's loop has no way to reach it until the client exists. This is also where most of the protocol I came to learn lives (transports, sessions, sampling, elicitation, progress, authorization), so it comes first.

## What we build

An MCP server that answers weather questions from Open-Meteo through the tools, prompts, and resources in [`../open-meteo-mcp-scope.md`](../open-meteo-mcp-scope.md), and an MCP client that connects to any MCP server and uses all three primitives. The work lands in two maturity levels. **Level 1** is the plain server over stdio: one tool per endpoint, both prompts, both resources, and the client to match. **Level 2** adds the advanced surface: the local-time tool with elicitation, the location dossier with progress, log notifications, and sampling, streamable HTTP in stateful and stateless modes, and OAuth authorization on HTTP. I debug the server with MCP Inspector at every level.

## Use cases

### Level 1

#### 1. I query Open-Meteo through the endpoint tools from Inspector

I start Inspector against the server over stdio with one command, pick a tool, fill in its arguments, and read the weather data it returns.

**Acceptance criteria**

- One command starts the server over stdio with Inspector attached to it.
- The server exposes 11 endpoint tools: geocoding search, geocoding lookup by id, forecast, ensemble, seasonal, historical weather, climate, marine, air quality, flood, and elevation.
- Each tool's description states the time horizon it covers, as given in the scope doc.
- Each tool returns structured content.
- Ensemble returns mean and spread only, never raw members. Seasonal results are labelled low-confidence. Historical spans over a month and climate projections come back summarised, and climate refuses more than 5 places.
- When Open-Meteo errors, times out, or is unreachable, the tool returns an error result naming the cause, and the server keeps serving the next call.
- Arguments that fail validation, such as an out-of-range latitude or a date outside the endpoint's horizon, return an error result saying which argument is wrong, without calling Open-Meteo.

#### 2. I read the Open-Meteo guides as resources

From Inspector I read the Open-Meteo guide for the whole service, then the endpoint guide for the one endpoint I care about.

**Acceptance criteria**

- `open-meteo://guide` returns the guide with the sections the scope doc lists.
- `open-meteo://endpoints/{endpoint}` returns the guide for each of the 10 endpoint names in the scope doc.
- Typing a partial endpoint name offers completions from those 10 names.
- An unknown endpoint name returns an error, not an empty resource.
- Guide content matches Open-Meteo's published documentation. A claim with no source in that documentation counts as a defect.

#### 3. I run the trip prompts

From Inspector I get the weekend check or the compare-places prompt, fill in its arguments, and get back messages that a model can run against the tools.

**Acceptance criteria**

- **Weekend check** takes no arguments and returns messages telling the model to ask where I am, resolve "this weekend" to dates in that place's timezone, call forecast and ensemble for those days, and say which day is better, how sure the forecast is, and why.
- **Compare places for a trip** takes `places` and `month`, and returns messages telling the model to split `places` itself, compare 30-year normals for that month, add the seasonal outlook when the month is within 7 months, and label that part low-confidence.
- Compare places refuses more than 5 places, and refuses a `month` that is not a month, with an error naming the argument.
- Assumed: in level 1 the weekend check resolves dates from the geocoded place's timezone, because the local-time tool only arrives in level 2. Once that tool exists, the prompt uses it.

#### 4. A program uses any MCP server through our client

A Python caller, later the API runtime's agent loop, opens a session on an MCP server over stdio and lists and uses its tools, resources, and prompts, with no knowledge of weather.

**Acceptance criteria**

- The client connects to a server described by a stdio entry in Claude Code's `mcpServers` format.
- Through the client, a caller lists tools, resources, resource templates, and prompts, calls a tool, reads a resource, and gets a prompt.
- The client holds its session open across calls until the caller closes it.
- The client contains nothing specific to Open-Meteo or weather. It works unchanged against an MCP server that is not ours.
- The caller supplies the sampling and elicitation handlers. The client declares to the server only the capabilities it was given handlers for, and passes progress and log notifications to its caller.
- When the server cannot be spawned or the session drops, the caller gets an error naming the server, not a hang.

### Level 2

#### 5. An agent finds the local time at a place, and I pick the place when the name is ambiguous

The caller passes a place name and gets the local date and time there, sunrise, sunset, and day length, with relative timeframes like "this weekend" resolved to dates in that timezone.

**Acceptance criteria**

- An unambiguous place returns the local date and time, sunrise, sunset, day length, and the resolved dates for any relative timeframe passed in.
- An ambiguous name, as the scope doc defines it, triggers an elicitation that lists each candidate with its country, region, and population, and the tool continues with the chosen place.
- If I decline or cancel the elicitation, the tool returns an error saying the place was not resolved.
- If the client did not declare elicitation, or the session has no back channel, the tool returns the candidates instead, so the agent can ask me itself.
- A name with no geocoding match returns an error saying no place was found.

#### 6. An agent gets a location dossier and watches it being built

The caller passes a place and gets a short summary and a full report on its weather and climate, with progress visible while the sources come in.

**Acceptance criteria**

- The dossier gathers every section listed in the scope doc, from one geocoding call.
- A progress notification fires as each source returns, once when the report starts, and once when it finishes, against a total of the number of sources plus two.
- When a source fails, or marine is skipped for an inland place, the other sections still come back and a log notification names the missing one.
- One sampling request at the end turns the gathered data into the summary and the report, and the tool returns only those two.
- When sampling is unavailable or refused, the tool returns the gathered data as structured sections and sends a log notification saying no report was written.
- When the client cancels the call, outstanding fetches stop and nothing further is sent for that call.

#### 7. I run the server over streamable HTTP, stateful or stateless, and connect to it

I start the server on HTTP in the mode I want, connect Inspector or our client to it, and every tool, resource, and prompt works as it does over stdio.

**Acceptance criteria**

- The server's start command takes the transport as an argument: stdio, HTTP stateful, or HTTP stateless. With no argument it runs stdio.
- The HTTP server listens on `127.0.0.1` only.
- In stateful mode, the initialize handshake opens a session. The client reuses that session across calls, and after a dropped stream it reconnects to the same session and receives the events sent while it was away.
- In stateless mode, every tool, resource, and prompt still works. A level 2 tool that needs the client sees there is no back channel before asking, takes its fallback path at once, and sends a log notification saying which request it skipped. There are no retries, and the server never crashes or hangs on it.
- Our client connects over both HTTP modes from an HTTP entry in the `mcpServers` format, with the same calls as over stdio.
- When the HTTP server is not running, the client's connect attempt fails with an error naming the URL.

#### 8. An authorized client connects over HTTP, and anyone else is refused

Before a client can use the HTTP server, it obtains authorization through the MCP authorization flow (OAuth 2.1). A request without valid authorization gets nothing.

**Acceptance criteria**

- A request to the HTTP server with no token, an expired token, or an invalid token is refused with 401 and touches no tool, resource, or prompt.
- Our client obtains authorization through the MCP authorization flow and then works over HTTP as in use case 7, in both stateful and stateless mode.
- Inspector can complete the same flow and connect.
- stdio has no authorization: whoever can spawn the process owns it.
- Open: which OAuth grant I use, where the authorization server runs, and whether tokens outlive a client run. I am studying OAuth before I decide, and the spec settles these. Assumed: tokens live in memory only, in line with the vision's in-memory rule.

## Functional requirements

- Every server-to-client request (sampling, elicitation) has a fallback path, and the server checks the client's declared capabilities and the session's back channel before sending one. A missing back channel is never an error the caller sees.
- No retries against Open-Meteo or against the client. A failure becomes an error result or a fallback, once.
- Every level 2 fallback sends an MCP log notification to the client saying what was skipped and why.
- Unit tests cover the client and the server. An integration test connects to the real server and checks every tool, resource, and prompt, and the sampling and elicitation handlers, over every transport the current level supports: stdio in level 1, and stdio plus stateful and stateless HTTP in level 2.

## In scope

- The scope doc, [`../open-meteo-mcp-scope.md`](../open-meteo-mcp-scope.md), as the source of truth for what each tool, prompt, and resource does. This PRD adds no new behaviour to it.
- MCP Inspector over stdio as the debugging path, with Node as a dev-only dependency. The server and the client themselves stay free of Node.
- MCP log notifications from the server to the client, as a protocol feature.
- Replaying missed events after a dropped stateful HTTP stream.

## Out of scope

- The agent loop, both runtimes, and the Textual CLI. They come with their own PRD, and that is when the client gets a real sampling handler that uses the conversation's model and a real elicitation UI.
- Connecting the Claude Code binary, and so the SDK runtime, to the server. Comes back with the SDK runtime.
- Server and client log files, their rotation, and client-side logging. Both sides need it, kept separate from each other, and it will be integrated as its own task. Comes back once the server has enough moving parts that MCP log notifications alone stop explaining a failure.
- One-command startups beyond Inspector over stdio. Comes back if starting HTTP by hand gets tedious.
- A terminal driver for the client. Tests drive it until the agent loop exists.

## Success criteria

- From Inspector I can exercise every tool, resource, and prompt, and both level 2 capabilities, without editing code.
- On every transport, any tool runs from any prompt. On stateless HTTP, the level 2 tools have never crashed the server or hung a call. They always took the best fallback available.
- The client's and the server's unit tests, and the integration test across every transport, pass.
- I can explain each protocol feature here from memory: both transports, stateful and stateless sessions, sampling, elicitation, progress and log notifications, resumability, and OAuth.

## Non-functional requirements

None. This PRD sets no timeout, latency, or retention numbers. Log retention moves to the deferred logging task, and the rest of the system's qualities are covered by the vision and the architecture.

## Approach note

- Both sides are built on the official `mcp` SDK ([ADR-0003](../adr/0003-official-mcp-sdk-over-fastmcp.md)). The client pins the legacy protocol mode, because that is the only way the server can push sampling and elicitation.
- The server's Open-Meteo layer knows HTTP and response shapes and nothing about MCP, as [`../architecture.md`](../architecture.md) lays out.
- The one-command Inspector startup looks like a `make` target in the package that wraps the SDK's Inspector launcher.
- [`../architecture.md`](../architecture.md) plans a static bearer token on HTTP. This PRD asks for the MCP OAuth flow instead, so that line changes once the auth spec settles the open questions.
