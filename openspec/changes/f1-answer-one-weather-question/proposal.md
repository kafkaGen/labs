# Proposal

Implements: F1 of `packages/weather-agents/docs/backlog/api-runtime.md`

## Why

The MCP server and client from PRD-0001 work, but no model drives them yet. F1 is the walking skeleton of the API runtime: the thinnest path from a weather question, through a hand-written loop on the Messages API and our MCP tools, to an answer. Every later feature in the backlog (F2 to F16) adds depth to this path.

## What Changes

- New `ApiRuntime` in `weather_agents.runtimes`. A caller opens it as an async context manager, sends one question, and gets back the answer text and a new session id. `close` shuts down the MCP sessions.
- On open, the runtime opens every server in the MCP config file through the existing `McpClientPool`, and offers the model all their tools.
- New hand-written agent loop in `weather_agents.agent_loop`. It calls the Messages API, runs every tool the model asks for, sends the results back, and repeats until the model ends its turn. Tools asked for in one turn run concurrently, and all their results go back in one message.
- The loop reaches tools through a tool-provider interface. An adapter in `runtimes` fills it from `McpClientPool`. The loop never imports `mcp`.
- Every request uses automatic prompt caching with the 5-minute lifetime.
- A run that stops for any reason other than `end_turn` raises one `RunError` naming the stop reason. F6 widens this into the full stop-reason handling.
- New `Settings` object (pydantic-settings) holding the model, `max_tokens`, the MCP config path, and the API key. It reads defaults, then `.env` and the environment, then overrides passed for one run. An invalid value fails when settings load and names the field. The default model is Claude Haiku 5.5.
- New offline tests against a scripted fake of the Messages API and a fake tool provider, plus one `live` test that asks "what's the weather in Lviv tomorrow?" against the real API and MCP server.
- New dependencies: `anthropic` and `pydantic-settings`.

Left to later features, on purpose:

- Continuing a session, `clear`, and unknown session ids: F2. In F1 each `send` starts a new session with a new id, and no history is kept, because nothing would read it.
- Step logs and run summaries: F3. F1 logs only a run error's cause, once, where it is raised.
- A tool call that raises (as opposed to a server error result), and naming servers that failed to open: F4. In F1 a raised tool failure ends the run with a `RunError`. A result the server marks `is_error` already goes back to the model as an error result, because that is the result's own shape.
- Structured answer, sources, and strict tools: F5. F1 returns the final turn's text. MCP tools go to the API with their server schema and no `strict` flag.
- USD cap, deadline, streaming, retries beyond the SDK default, compaction, model behaviour settings, and every Anthropic server tool: F7 to F16.

## Capabilities

### New Capabilities

- `weather-agents/api-runtime`: the API runtime a caller uses. Opening it with the MCP config, sending a question, the result's answer text and session id, and closing it.
- `weather-agents/agent-loop`: the hand-written loop on the Messages API. Model calls, tool calls through the tool-provider interface, concurrent tool calls in one turn, prompt caching, and how a run ends.
- `weather-agents/agent-settings`: the one settings object every knob of the agent layer lives in, and how its values load and fail.

### Modified Capabilities

None. The project has no specs yet.

## Impact

- **Code:** new packages `weather_agents.agent_loop`, `weather_agents.runtimes`, and `weather_agents.agents` (the one system prompt), and a new module `weather_agents.settings`. `mcp_client` and `server` are unchanged.
- **Dependencies:** `anthropic` and `pydantic-settings` added to `packages/weather-agents/pyproject.toml`.
- **Tests:** new `tests/agent/` for offline loop and runtime tests, and a new live test. The `live` marker's description widens to cover the Anthropic API.
- **Spend:** the live test makes real Haiku 5.5 calls, a fraction of a cent per run. It runs only by hand.
- **Docs:** `docs/architecture.md` moves the `agent_loop`, `runtimes`, and `settings` rows from Planned to Built for what F1 builds, once it is built. The backlog's F1 row moves to `building` with this change's name.
