# Proposal

## Why

The MCP server and client from PRD-0001 work, but no model drives them yet. PRD-0002 ([`packages/weather-agents/docs/prd/0002-api-agent-loop.md`](../../../packages/weather-agents/docs/prd/0002-api-agent-loop.md)) describes a hand-written agent loop on the Claude Messages API. It is too large for one reviewable PR, so it ships in four blocks. This change is block 1: the smallest loop a caller can use end to end. One question goes in, a structured answer comes out, the run stays under a USD cap and a deadline, and a session id lets the next question continue the conversation.

## Block roadmap for PRD-0002

Each block is one change and one PR, reviewed and merged before the next starts. B2, B3 and B4 depend only on B1, not on each other. Later blocks may rewrite B1 code. That cost was accepted when the split was agreed.

| Block | Change | Scope | PRD-0002 coverage |
| --- | --- | --- | --- |
| **B1** | this change | Settings (only the fields B1 reads), tool-provider interface and MCP pool adapter, MCP tools with their server schemas (not strict), concurrent tool calls, tool errors as error results, stop-reason handling and `RunError`, structured answer with resources, `ApiRuntime` with in-memory sessions, USD cap with a base price table, per-request deadline, step logging with truncation | UC1, UC2, the base of UC5 (cap, deadline) and UC7 (step and run-end logs) |
| **B2** | later | Streamed runs: text, tool-input, tool-call, tool-result and retry events. Mid-stream retries with backoff, rate-limit reset waits, retries that respect the deadline, terminal errors, cancellation within one second | UC3, FR Retries, FR Rate limits, FR Retries respect the deadline, FR Terminal errors, retry logs from UC7 |
| **B3** | later | Compaction and session history after it, automatic prompt caching, full cost model (cache writes and reads, fast mode), effort, adaptive thinking, thinking summaries, fast mode, per-model setting checks | Rest of UC5, UC6, FR Caching, compaction in UC2 |
| **B4** | later | Web search, web fetch, code execution, tool search, programmatic tool calling, server-tool charges in the cost, a structured answer that survives web search citations | UC4, FR Structured answer |

PRD-0002 moves to `Shipped` only after B4 merges.

**Departure from PRD-0002, decided 2026-11-13:** MCP tools are never strict. Argument validation stays on the MCP server, in its pydantic models, which also enforce the ranges and patterns strict mode can't express. This contradicts PRD-0002's "Strict schemas" rule, which makes MCP tools strict by default, and the 20-strict-tool check that goes with it. That PRD line needs an edit by its owner. It also simplifies B4: programmatic tool calling needs non-strict tools, so no "strict or programmatic" setting is needed. The structured answer's schema stays strict, as the PRD asks.

## What Changes

- New `settings` module in `weather-agents`: one pydantic-settings object read from defaults, `.env`, the environment, and per-run overrides. B1 adds only the fields it reads: model, deadline, USD cap, MCP config path, log level, truncation length, and `max_tokens`. Invalid values fail when settings load and name the field.
- New `agent_loop` module: a hand-written loop over the Messages API. It calls the model, runs every tool call of one turn concurrently, returns all results in one message, and repeats until `end_turn`. It depends on a tool-provider interface, not on MCP.
- An MCP adapter that fills the tool-provider interface from PRD-0001's `McpClientPool`. It offers every MCP tool with its server's input schema unchanged, as a non-strict tool. The server's pydantic validation is the only argument check, so a wrong type, a missing field or an out-of-range value comes back as an error result.
- Stop-reason handling: `end_turn` ends the run, and `tool_use` and `pause_turn` continue it. `max_tokens`, `stop_sequence`, `refusal` and `model_context_window_exceeded` raise a `RunError` that names the stop reason and carries usage, cost and partial text. A hit cap or deadline raises the same error family, naming the limit.
- A structured answer: answer text plus a list of resources. Each resource is a URL or an MCP tool call with its name and arguments, plus a short title. Every resource must point at something the run actually touched.
- A per-request USD cap, $0.10 by default. No model call starts once the cap is reached. Cost uses a hand-kept price table with base input and output prices only. A model with no price entry fails before any model call.
- A per-request deadline, 120 seconds by default. On expiry, the in-flight work is cancelled and a `RunError` is raised.
- New `runtimes` module with the `AgentRuntime` interface and `ApiRuntime`: `send(question, session_id=None)`, `clear(session_id)` and `close()`. Sessions hold the message history in memory only. A failed request keeps the user's question and records the run error as the answer, and drops the partial assistant and tool turns. An unknown session id fails before any model call.
- Logging through `labs-logging`: every line carries the session id. Each step logs model input, model output, tool calls and tool results at debug level, cut to the truncation length with a marker. Each step also logs tokens so far and time left. Each run ends with an info line: tokens, cost, elapsed time against the deadline, tool calls and turns.
- New dependencies: `anthropic`, `pydantic-settings`, `labs-logging` (workspace).
- Non-streaming only. The loop calls the API without streaming events reaching the caller. B2 adds streaming.

## Capabilities

### New Capabilities

- `agent-loop`: one agent run on the Claude Messages API: tool calls, stop reasons, run errors, the structured answer, the USD cap, the deadline, and the logs of each run.
- `api-runtime`: the `AgentRuntime` contract on the API runtime: `send`, `clear` and `close`, and the in-memory sessions that carry a conversation across requests.
- `agent-settings`: the settings object the agent reads: its sources, precedence, defaults, and validation.

### Modified Capabilities

None. No specs exist yet in `openspec/specs/`.

## Impact

- **Code:** new `packages/weather-agents/src/weather_agents/settings.py`, `agent_loop/` and `runtimes/`. `mcp_client` is used as built and does not change.
- **Dependencies:** `anthropic` and `pydantic-settings` are added to `weather-agents`, and `labs-logging` as a workspace dependency.
- **Tests:** offline unit tests against a faked Messages API and a fake tool provider. A few `live` tests against the real API and the real MCP server, run by hand, spending against the default cap.
- **Docs:** PRD-0002's `Status` moves from `Draft` to `Building` when work starts. In `packages/weather-agents/docs/architecture.md`, the `agent_loop`, `runtimes` and `settings` rows move to Built for what B1 builds. The data store row becomes one message list per session. The rule that a hit cap or deadline is a visible stop reason becomes a run error, matching the PRD. The "no retries anywhere" row stays until B2.
- **Secrets:** `ANTHROPIC_API_KEY` from `.env`, as the architecture already plans.
