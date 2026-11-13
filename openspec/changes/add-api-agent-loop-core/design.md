# Design

## Context

See `proposal.md` for why, and the three spec deltas for the required behavior. The facts below shape how B1 is built.

- `McpClientPool` (built in PRD-0001) already lists every open server's tools as `<server>__<tool>` through `list_all_tools()` and calls them by that name through `call_namespaced_tool()`. A server-side error comes back as a `CallToolResult` with `is_error=True`, and a transport or routing failure raises `McpClientError`. The pool must be opened and closed in the same asyncio task.
- The level-1 server exposes 11 tools. Their input schemas use `minimum`, `maximum`, `minLength`, `minItems`, `maxItems`, `pattern`, `default`, `$defs`/`$ref` and `anyOf`, and the server enforces all of them with pydantic. Strict mode would reject several of these keywords, which is one reason MCP tools stay non-strict (decision 3).
- The default model is Haiku 5.5 (`claude-haiku-5-5`, $0.10 input and $0.50 output per million tokens for prompts up to 100K tokens). It runs adaptive thinking by default, so responses carry `thinking` blocks that must go back to the API unchanged.
- Structured output (`output_config.format`) can share a request with strict tools. It can't share one with citations, but nothing in B1 produces citations.
- `labs-logging` must be configured once, by the process entrypoint. Library modules only call `get_logger(__name__)` and bind context.
- B1 has no CLI. Its callers are tests and a throwaway script.

## Goals / Non-Goals

**Goals:**

- The loop never imports `mcp`. Only the runtime knows the tools come from MCP, as the architecture requires.
- Every limit and every error path can be tested offline, with a scripted fake of the Messages API and a fake tool provider.
- The shapes B2 to B4 will extend stay small and obvious: one loop function, one `RunError`, one settings class, one price table.

**Non-Goals:**

- No streaming events, no retries beyond what the SDK already does, no prompt caching, no compaction. These belong to B2 and B3.
- No `agents` module. The single system prompt lives next to the runtime until a second runtime needs it.
- No CLI command, and no change to `mcp_client`.

## Decisions

### 1. Module layout follows the architecture's boundaries

```text
weather_agents/
  settings.py            Settings (pydantic-settings)
  agent_loop/
    tools.py             ToolProvider protocol, ToolSpec, ToolOutcome
    loop.py              run_agent(): the loop itself
    answer.py            Answer and Resource models, answer JSON schema, resource resolution
    pricing.py           PRICES table and cost(usage, model)
    errors.py            RunError, RunLimit, ConfigurationError
    trace.py             truncate() and step logging helpers
  runtimes/
    base.py              AgentRuntime protocol, AgentResult
    api.py               ApiRuntime: sessions, wiring, system prompt
    mcp_tools.py         McpToolProvider: adapts McpClientPool to ToolProvider
```

The MCP adapter sits in `runtimes`, not `agent_loop`, so the loop depends only on the `ToolProvider` protocol. Alternative: put the adapter in `mcp_client`. Rejected, because `mcp_client` is meant to stay model-agnostic, and turning results into the loop's shape is the runtime's concern.

### 2. The tool-provider seam is two methods

```python
class ToolProvider(Protocol):
    async def tool_specs(self) -> list[ToolSpec]: ...          # name, description, input_schema
    async def call(self, name: str, arguments: dict) -> ToolOutcome: ...  # text, is_error
```

`ToolOutcome` holds the result as text plus an `is_error` flag. `McpToolProvider` turns a `CallToolResult` into it. It prefers `structured_content` serialized as JSON, and falls back to joining the text content blocks. It also turns a raised `McpClientError` into `ToolOutcome(is_error=True)` with the error's message, so the loop never sees an MCP exception. The loop also catches any other exception from `call` and makes it an error result, which keeps the spec's "a failed tool call goes back as an error result" true for any provider.

### 3. MCP tools are non-strict, and the server's pydantic models validate

Each `ToolSpec` carries the server's `input_schema` unchanged and goes to the API without `strict`. The model sees the full schema, ranges and patterns included, as guidance. The MCP server validates every call against its pydantic models and returns a violation as an error result, which the model reads and corrects on its next turn.

Alternative: strict tools, with the schema rewritten to remove the keywords strict mode rejects. Rejected by the user on 2026-11-13. The tools are read-only and the server already validates, so strict mode would only save a retry turn. It would cost a schema rewrite and an open risk around optional fields with defaults. Strict mode also guarantees types, not ranges, so the server would still be needed for limits like latitude ±90. This departs from PRD-0002's "Strict schemas" rule (see `proposal.md`).

The debug log shows every tool call's arguments and every error result. That makes the rate of invalid calls visible, should the decision ever need revisiting.

### 4. The loop is one async function over `AsyncAnthropic.messages.create`

```text
run_agent(client, tools, history, question, settings, system) -> LoopOutcome
  check the model has a price           -> ConfigurationError
  messages = history + [user question]
  async with asyncio.timeout(deadline):
    loop:
      if cost >= cap: raise RunError(limit=USD_CAP)
      response = await client.messages.create(model, max_tokens, system,
                                              tools=tool specs, output_config=answer schema,
                                              messages)
      add usage and cost; log step
      append response.content as the assistant turn, unchanged
      match stop_reason:
        end_turn   -> parse the answer, resolve resources, return
        tool_use   -> run all tool_use blocks in a TaskGroup,
                      append one user turn with every tool_result
        pause_turn -> continue with no new user turn
        other      -> raise RunError(stop_reason=..., partial text)
  except TimeoutError -> raise RunError(limit=DEADLINE)
```

- **Non-streaming `create`, not `stream`.** Alternative: stream internally from B1 so B2 doesn't rewrite the call site. Rejected: the rewrite was accepted, and `create` keeps B1's fake API to "return this `Message` next". The default `max_tokens` of 16,000 keeps a non-streaming call well under the SDK's timeout.
- **The assistant turn is appended unchanged**, `thinking` blocks included, because adaptive thinking is on by default on Haiku 5.5 and the API needs those blocks back as they came.
- **A refused or truncated turn runs no tools.** A stop reason other than `tool_use` never reaches tool execution, so a `tool_use` block cut short by `max_tokens` or `refusal` is never called.
- **The cap is checked before each call**, so the overshoot is at most the one call already made. Tools of the last turn still run before the check. Their cost is zero, and their results are dropped with the failed request anyway.
- **The deadline is one `asyncio.timeout` around the whole loop.** Cancelling it cancels the in-flight HTTP call and the tool `TaskGroup` together. The SDK's own retries (2 by default) run inside that timeout, so they can't outlive the deadline either. B2 makes the retry count a setting.
- **`LoopOutcome`** carries the final message list, the answer, usage, cost, turns and tool calls. `RunError` carries usage, cost and partial text. The runtime uses `LoopOutcome.messages` to update the session.

### 5. The structured answer cites tool calls by id, and the loop fills in the call

The answer schema sent as `output_config.format` is:

```json
{
  "answer": "string",
  "resources": [
    {"title": "string", "source": {"anyOf": [
      {"type": "tool_call", "tool_use_id": "string"},
      {"type": "url", "url": "string"}
    ]}}
  ]
}
```

The model names a tool call by its `tool_use_id`, not by its name and arguments. Each tool result the loop sends starts with `[source id: <tool_use_id>]`, because the first live run showed Haiku 5.5 invents ids like `forecast_lviv_3day` when the id is only block metadata. Strict mode needs `additionalProperties: false` on every object, so it can't express a free-form arguments object. An id is also easy to check. The loop keeps a ledger of every `tool_use` block it ran (id, name, arguments) and every URL it found in tool results (a regex over the result text). Then it resolves the answer:

- A `tool_call` source whose id is in the ledger becomes `Resource(title, ToolCallSource(tool, arguments))`.
- A `url` source whose URL is in the ledger becomes `Resource(title, UrlSource(url))`.
- Anything else is dropped and logged at warning level.

The caller's `Resource` therefore carries the tool name and arguments the PRD asks for. The model only has to point at the call.

If the final text doesn't parse against the schema, which structured output should prevent, the loop raises `RunError(stop_reason="end_turn")` with a message saying the answer did not match its schema, and the raw text as partial text. That is a failure the caller can see, not a crash.

Alternatives considered:

- A strict "submit answer" tool. Rejected, because the run would then end on a tool call, not on `end_turn`, and forced `tool_choice` is unavailable on some models.
- Building resources only from the ledger, with no model input. Rejected, because the model couldn't title them or leave out calls that didn't support the answer.

B4 revisits this when web search citations rule out `output_config.format`.

### 6. One error type with a reason, plus two configuration errors

- `RunError(Exception)` has `stop_reason: str | None`, `limit: RunLimit | None` (`USD_CAP`, `DEADLINE`), `usage`, `cost_usd` and `partial_text`. Its message names whichever is set.
- `ConfigurationError` covers an unpriced model, before any model call.
- `UnknownSessionError` covers an unknown session id.

Alternative: a subclass per stop reason. Rejected under KISS. Callers branch on one field, and B2's retry errors fit the same type.

### 7. Cost: a hand-kept price table of base rates

`PRICES: dict[str, ModelPrice]` holds the input and output USD per million tokens, today for `claude-haiku-5-5`, `claude-sonnet-5-5` and `claude-opus-5-5`. `cost(usage, model) = input_tokens * in + output_tokens * out`. B1 sends no `cache_control`, so cache tokens are zero, and Haiku 5.5's higher rate above 100K-token prompts is not modelled. B3 adds cache rates, long-context tiers, fast mode and server-tool charges, and the table's shape grows with them.

### 8. Sessions are a dict of message lists owned by `ApiRuntime`

```text
ApiRuntime (async context manager; opens McpClientPool in __aenter__, closes in close/__aexit__)
  _sessions: dict[str, list[MessageParam]]
  send(question, session_id=None, **overrides) -> AgentResult(answer, resources, session_id, usage, cost)
    id unknown -> UnknownSessionError, before anything else
    new id     -> uuid4 hex, empty history
    with bound_context(session_id=id): outcome = await run_agent(...)
    success -> session = outcome.messages
    RunError -> session += [user question, assistant "The request failed: <error>"]; re-raise
  clear(session_id) -> drop it
  close() -> drop all, close the pool
```

The loop works on a copy of the history, so a failure never leaves partial turns in the session. A history that ends with an assistant error text is a valid next prefix, because the next `send` adds a user turn after it. Two concurrent `send` calls to the same session are not supported. One user and one chat make this safe today, and the docstring says so.

`ApiRuntime` is used as `async with ApiRuntime(settings) as runtime:`, because the pool must open and close in the same task. `close()` is still public to meet the `AgentRuntime` interface.

The system prompt is a module constant in `runtimes/api.py`. It tells the model it answers weather questions with the tools, and that it lists only resources it used. It moves to the `agents` module once the SDK runtime needs the same prompt (YAGNI until then).

### 9. Settings: pydantic-settings, with overrides validated, not copied

`Settings(BaseSettings)` reads `.env` (in the working directory) and environment variables with the prefix `WEATHER_AGENTS_`. Fields: `model`, `deadline_seconds` (> 0), `usd_cap` (> 0), `max_tokens` (> 0, default 16,000), `mcp_config` (path, default `mcp.stdio.json`), `log_level`, `log_truncate_chars` (> 0, default 200). The API key is a `SecretStr` read from `ANTHROPIC_API_KEY` and passed to `AsyncAnthropic(api_key=...)`.

Per-run overrides go through `settings.with_overrides(**changes)`. It rebuilds the settings through validation, so `deadline_seconds=0` fails like it would from the environment. It rejects the API key as an override. pydantic-settings already ranks init arguments over the environment over `.env` over defaults, so no custom source ordering is needed.

### 10. Logging: context binding at the boundary, truncation in one helper

- `ApiRuntime.send` wraps the run in `bound_context(session_id=...)`, so every line from the loop, the adapter and the tool calls carries it. `TaskGroup` children copy the context.
- `trace.truncate(value, limit)` serializes a value to compact JSON or a string. If it is longer than the limit, it returns the first `limit` characters plus `truncated=True` and the original length as log fields.
- Step lines are at debug level: `model.request`, `model.response`, `tool.call`, `tool.result`, each with `tokens_so_far` and `seconds_left`. `run.end` is at info level with tokens, cost, elapsed time, deadline, tool calls and turns, and is logged in a `finally` so failed runs report too.
- The `RunError` cause is logged once, at the raise site in the loop. The runtime does not log it again.
- No module calls `configure`. The live tests and the throwaway script configure `labs-logging` with family `weather_agents`.

### 11. Tests: a scripted fake API and a fake tool provider

- `FakeMessages.create(**kwargs)` records each request and returns the next scripted `anthropic.types.Message`. Tests build messages with real SDK types, so stop reasons and content blocks match the real shapes. A fake that sleeps covers the deadline. A large `usage` covers the cap.
- `FakeToolProvider` returns scripted outcomes, can raise, and can record start and end times to prove concurrency.
- Unit tests cover each stop reason, the cap, the deadline, the unpriced model, tool specs that carry the server schema unchanged and without `strict`, resource resolution, session success and failure paths, unknown ids, settings precedence and validation, and truncation.
- `live` tests (marked, run by hand, needing `ANTHROPIC_API_KEY`) cover one question to a structured answer over the real stdio server, and one follow-up in the same session. The `live` marker's description changes to cover both Open-Meteo and the Anthropic API.

## Risks / Trade-offs

- [Without strict mode, the model sometimes sends invalid arguments, and each costs one extra turn] → The server rejects them with a readable error, and the debug log counts them. The USD cap bounds the cost of a model that keeps getting a call wrong.
- [The API may reject a JSON Schema keyword in a server schema even without strict mode] → The first live test sends all 11 schemas, and a 400 would name the keyword. No such rejection is expected for non-strict tools.
- [Cancelling an MCP call mid-flight may leave the pool's session unusable] → The deadline test runs against the fake provider, and one live run checks that a session still answers after a cancelled call. If it breaks, the failure is recorded as an architecture limit for B2's cancellation work, not hidden.
- [The model may cite no resources, or only URLs it saw in a tool's text] → The URL ledger scans tool result text, so URLs the server returns count as touched. An empty resource list is allowed, and a live test checks that the first answer cites at least one tool call.
- [`output_config.format` with tools on Haiku 5.5 may answer in JSON before calling any tool] → The system prompt says to use the tools before answering. The live test asserts a tool call happened.
- [The price table drifts from Anthropic's pricing] → It is hand-kept by design (PRD UC5). It names its source and the date it was last checked.
- [Non-streaming calls block until the whole response arrives] → `max_tokens` defaults to 16,000, and B2 moves the loop to streaming.

## Migration Plan

No migration is needed: nothing uses these modules yet. Rollback is reverting the PR. When work starts, PRD-0002's `Status` moves from `Draft` to `Building`. When the PR is ready, `docs/architecture.md` is corrected for what B1 builds (decision list in `proposal.md` → Impact).

## Open Questions

- Which models the price table lists beyond Haiku 5.5 does not change the design. Adding Sonnet 5.5 and Opus 5.5 now costs two lines.
