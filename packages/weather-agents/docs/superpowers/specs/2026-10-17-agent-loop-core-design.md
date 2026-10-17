# Design: agent loop, core

**Date:** 2026-10-17
**Implements:** slice 1 of 4 of [PRD-0002](../../prd/0002-api-agent-loop.md): use cases 1, 2, 6, and 7, minus the parts listed under Later slices.
**Built on:** `anthropic` 1.15 (the Messages API, hand-written loop, no `tool_runner`), the level 1 MCP client from [PRD-0001](../../prd/0001-open-meteo-mcp-server-and-client.md), and `labs-logging` from the workspace.
**Fits:** the `agent_loop`, `runtimes`, `agents`, and `settings` modules in [`architecture.md`](../../architecture.md). Server tools are API-runtime-only by [ADR-0004](../../adr/0004-anthropic-server-tools-only-on-the-api-runtime.md), but none arrive in this slice.

## Goal

A caller opens the API runtime, sends a weather question, and gets back a structured answer with its sources and a session id. Sending the id with the next question continues the conversation. The agent calls the MCP tools from the config file, several at once when asked, and every step is logged.

## PRD-0002 split

| Slice | Covers |
|---|---|
| 1, this spec | Settings, the runtime and its sessions, the loop with MCP tools, strict schemas, the structured answer, stop reasons, step logging |
| 2 | USD cap and price table, deadline and cancellation, retries alongside the SDK's, rate-limit waits, compaction, caching |
| 3 | The stream to the caller: text and tool-input deltas, thinking summaries, the retry event |
| 4 | Web search, web fetch, code execution, tool search, programmatic tool calling, and the structured answer when web search ran |

## Package layout

New files under `packages/weather-agents/`:

```
src/weather_agents/
    settings.py                 Settings (pydantic-settings), Effort
    agents/
        __init__.py             exports AgentDefinition, WEATHER_AGENT
        definitions.py
    agent_loop/
        __init__.py             exports run_agent, the events, the errors, Answer, the interfaces
        answer.py               Answer, UrlResource, ToolCallResource
        events.py               ModelTurn, ToolCallStarted, ToolCallFinished, RunFinished
        errors.py               RunError, StopReasonError, InvalidAnswerError, ApiCallError
        interfaces.py           ModelCaller, ModelRequest, ToolProvider, ToolSpec, ToolOutcome
        model.py                AnthropicModelCaller
        ledger.py               SourceLedger: tool calls (and later URLs) a session touched
        result.py               RunResult, TokenUsage
        truncate.py             truncate(value, limit)
        loop.py                 run_agent
    runtimes/
        __init__.py             exports AgentRuntime, ApiRuntime, SessionNotFoundError
        base.py                 AgentRuntime protocol
        api.py                  ApiRuntime, Session
        mcp_tools.py            McpToolProvider
scripts/try_agent.py            throwaway driver, deleted once the live tests pass
tests/agent_loop/  tests/runtimes/  tests/test_settings.py
```

New dependencies: `anthropic>=1.15,<2`, `pydantic-settings>=2`, and `labs-logging` as a workspace source. `agent_loop` imports nothing from `mcp_client` or `mcp`. `runtimes` is the only package that knows both.

## Settings

`Settings(BaseSettings)` with `env_prefix="WEATHER_AGENTS_"` and `env_file` set to `packages/weather-agents/.env`, resolved from the module's path, not the working directory.

| Field | Type | Default |
|---|---|---|
| `model` | `str` | `"claude-haiku-5-5"` |
| `effort` | `Effort`, a `Literal` of `low`, `medium`, `high`, `xhigh`, `max`. A `Literal` rather than an `Enum`, so the value passes to the SDK's typed parameter unchanged | `low` |
| `thinking` | `bool`, adaptive when true, disabled when false | `True` |
| `max_tokens` | `int`, greater than 0 | `32_000` |
| `fast_mode` | `bool` | `False` |
| `mcp_config` | `Path` | `mcp.stdio.json`, resolved from the package root |
| `log_level` | `str` | `"INFO"` |
| `log_truncate` | `int`, greater than 0 | `200` |
| `anthropic_api_key` | `SecretStr`, read from `ANTHROPIC_API_KEY` with no prefix | required |

- An invalid value fails when `Settings()` is built, and pydantic's error names the field.
- There is no table of what each model supports. An unsupported combination, such as `fast_mode` on Haiku, goes to the API, which returns a 400. The loop raises that as `ApiCallError` on the first model call. See Deviations.
- `fast_mode=True` sends `speed="fast"` with the `fast-mode-2026-02-01` beta header. `thinking=False` sends `{"type": "disabled"}`.
- `log_level` is read by the entry point, which configures `labs-logging`. The runtime never configures logging.

## Agents

`AgentDefinition` is a frozen pydantic model with `name: str` and `system_prompt: str`. `WEATHER_AGENT` is the one definition. Its prompt tells the model it answers weather questions with the tools provided, cites each tool call or URL it relied on as a resource, and writes `arguments` as the exact JSON it sent. The SDK runtime will read the same definition later.

## The loop's interfaces

`interfaces.py` holds the two seams the loop depends on. Both are `Protocol`s.

- `ModelCaller.call(request: ModelRequest) -> anthropic.types.Message`. `ModelRequest` is a frozen dataclass holding `system`, `messages` (a list of SDK `MessageParam`), and `tools` (a list of `ToolSpec`). It is a dataclass rather than pydantic so the SDK's TypedDicts pass through unvalidated. The settings a call needs live in the caller, which gets them when it is built.
- `ToolProvider.list_tools() -> list[ToolSpec]` and `ToolProvider.call(name: str, arguments: dict[str, object]) -> ToolOutcome`. `ToolSpec` has `name`, `description`, and `input_schema`, the strict one. `ToolOutcome` has `content: str` and `is_error: bool`.

The SDK's message types cross the seam unchanged. The project uses one provider ([vision](../../vision.md) non-goals), so wrapping them would only hide the API being learned.

`AnthropicModelCaller(client: AsyncAnthropic, settings: Settings)` sends each request with `client.messages.stream(...)`, passing `output_config={"effort": ..., "format": {"type": "json_schema", "schema": transform_schema(Answer)}}` and every tool with `strict: True`, and returns `await stream.get_final_message()`. It does not pass `output_format=Answer`. With that set, the SDK parses every text block as the stream ends (checked in `anthropic` 1.15's `lib/streaming/_messages.py`), so a non-JSON preamble in a `tool_use` turn, or a reply cut off at `max_tokens`, would raise a pydantic error before the loop could see the stop reason. The loop parses the answer itself, on `end_turn` only. It always streams, so a long request never trips the SDK's limit on non-streamed calls, and slice 3 only has to pass the events on. It wraps `anthropic.APIError` in `ApiCallError`, keeping the original as `__cause__`. In this slice the SDK keeps its default retries. Slice 2 sets them.

## The structured answer

```python
class UrlResource(BaseModel):
    kind: Literal["url"]
    url: str
    title: str

class ToolCallResource(BaseModel):
    kind: Literal["tool_call"]
    tool: str        # the prefixed name, as the model called it
    arguments: str   # JSON text: strict mode forbids a free-form object
    title: str

class Answer(BaseModel):
    answer: str
    resources: list[Annotated[UrlResource | ToolCallResource, Field(discriminator="kind")]]
```

Structured output is sent on every call in a run, because it only constrains the final text, never a `tool_use` turn. Slice 4 has to revisit this, because web search citations and structured output cannot share a request.

## The loop

`run_agent(*, caller: ModelCaller, tools: ToolProvider, tool_specs: list[ToolSpec], agent: AgentDefinition, settings: Settings, history: list[MessageParam], question: str, ledger: SourceLedger) -> AsyncIterator[Event]` is an async generator. `tool_specs` is the list the runtime fetched once, and `tools` is the provider that runs them. `history` is the session's messages, which it copies and never mutates.

1. The working list is `history` plus `{"role": "user", "content": question}`.
2. Each step builds a `ModelRequest` and awaits `caller.call`. It appends the assistant's `content` blocks to the working list exactly as returned. Thinking blocks and their signatures must go back unchanged for tool use to keep working. It adds the message's `usage` to the running `TokenUsage` and yields `ModelTurn(step, stop_reason, usage, tool_uses)`.
3. It acts on `stop_reason`:
   - `tool_use`: it yields `ToolCallStarted(id, name, arguments)` for each `tool_use` block, then runs every call at once in an `asyncio.TaskGroup`. Each call is recorded in the ledger as it starts. When all are done, it yields `ToolCallFinished(id, name, is_error, content)` for each, in the model's order, appends one user message holding every `tool_result` (`is_error` set from the outcome), and goes to the next step.
   - `pause_turn`: it goes to the next step with nothing appended.
   - `end_turn`: it validates the reply's text with `Answer.model_validate_json`. Text that is empty or does not validate raises `InvalidAnswerError`. Otherwise it checks each resource against the ledger and drops any that fail, with a warning. It yields `RunFinished(result, messages)`, where `messages` is the working list.
   - Anything else (`max_tokens`, `stop_sequence`, `refusal`, `model_context_window_exceeded`, and any value the SDK adds later) raises `StopReasonError(stop_reason)`.
4. A tool call never raises into the loop. `ToolProvider.call` returns an error outcome for an MCP failure. An unexpected exception inside one call becomes an error outcome naming its type, so one bad call cannot cancel its siblings in the task group.

`RunResult` holds `answer: Answer`, `session_id: str`, `usage: TokenUsage` (`input`, `output`, `cache_read`, `cache_write`), `turns: int` (one per model call), and `tool_calls: int`.

## Resource check

`SourceLedger` belongs to the session and lives as long as it does. `record_tool_call(name, arguments)` stores the prefixed tool name and the arguments dict. `has_tool_call(name, arguments_json)` parses the JSON and compares it to each recorded call with `==`. Invalid JSON counts as not found. `record_url(url)` and `has_url(url)` hold URLs. Nothing records one in this slice, so every `UrlResource` is dropped until slice 4's web tools record the URLs they touch. Calls from a failed request stay in the ledger, because their data was fetched.

## Errors

| Error | Raised when | Carries |
|---|---|---|
| `RunError` | Base class. Never raised itself | `session_id`, `usage`, `partial_text` (the text blocks of the last assistant message, or `""`) |
| `StopReasonError(RunError)` | A stop reason the loop does not continue on | `stop_reason` |
| `InvalidAnswerError(RunError)` | `end_turn` whose text is not a valid `Answer` | |
| `ApiCallError(RunError)` | The SDK raised, after its own retries | `status_code` or `None` for a connection error |
| `SessionNotFoundError` | `send` or `clear` named an id the runtime does not hold. Not a `RunError`: no run started | `session_id` |

The loop raises a `RunError` with `session_id=""`. The runtime fills it in before the error reaches the caller. Each `RunError` is logged once at error level by the runtime, where it is caught.

## Runtime and sessions

`AgentRuntime` is a `Protocol` and an async context manager with `send(question: str, session_id: str | None = None) -> RunResult`, `clear(session_id: str) -> None`, and `close() -> None`.

`ApiRuntime(settings, *, model_caller: ModelCaller | None = None, pool: McpClientPool | None = None)`. Tests inject both. Left as `None`, it builds `AnthropicModelCaller` over `AsyncAnthropic(api_key=...)` and `McpClientPool.from_file(settings.mcp_config)`.

- **On enter**, it opens the pool and logs a warning for each server in `pool.failures`. It lists the tools once, through `McpToolProvider`, and keeps the list for every request. A stable tool list keeps the cache prefix stable for slice 2. No server opening is not an error: the agent runs with no MCP tools. The runtime has to be opened and closed in one task, because the pool does.
- **`Session`** has `id` (`uuid4().hex`), `messages: list[MessageParam]`, and `ledger: SourceLedger`. The runtime keeps them in a `dict` in memory and nowhere else.
- **`send`** finds or creates the session, raising `SessionNotFoundError` for an unknown id. Under `bound_context(session_id=...)` it runs `run_agent` to its `RunFinished` and returns the result.
  - On success, the session's messages become the run's working list.
  - On a `RunError`, the session gets `{"role": "user", "content": question}` plus `{"role": "assistant", "content": f"The previous request failed: {error}"}`, and the partial turns are dropped. The error is re-raised with the session id set.
  - On any other exception, including cancellation, the session is left as it was.
- **`clear(id)`** deletes the session, or raises `SessionNotFoundError`. **`close()`** drops every session and closes the pool. `__aexit__` calls it.

`McpToolProvider(pool)`:

- `list_tools()` takes `pool.list_all_tools()` and passes each `input_schema` through `anthropic.transform_schema`. Strict mode rejects `minimum`, `maximum`, `minLength`, `maxItems`, and `pattern`, all of which the Open-Meteo server uses. The transform moves them, and `default`, into the property's description as text such as `{minimum: -90, maximum: 90}`, adds `additionalProperties: false`, and leaves `required` as the server wrote it. The server still enforces the limits.
- `call(name, arguments)` calls `pool.call_namespaced_tool`. The content is the result's text blocks joined with newlines, or `json.dumps(structured_content)` when there are none. `is_error` is copied. A `McpClientError` becomes `ToolOutcome(content=str(error), is_error=True)`.

## Logging

Every module uses `labs_logging.get_logger(__name__)`. The session id reaches every line through `bound_context`. Every logged value of unbounded size goes through `truncate(value, settings.log_truncate)`, which renders the value with `str` (or `json.dumps` for a dict or list), cuts it, and appends `… [cut N chars]`.

| Level | When | Fields |
|---|---|---|
| debug | Each step, before the call | `step`, `input`: the messages added since the previous step |
| debug | Each step, after the call | `step`, `stop_reason`, `output`: the text blocks, `tool_uses`: names, `tokens`: running totals, `elapsed_s` |
| debug | Each tool call | `tool`, `arguments`, then `result`, `is_error` |
| info | End of a successful run | `tokens`, `elapsed_s`, `turns`, `tool_calls` |
| warning | A dropped resource, and a server that failed to open | `resource` or `server`, `reason` |
| error | A `RunError`, once, in the runtime | `error`, `stop_reason` when there is one, `tokens` |

Slice 2 adds `time_left_s`, `cost_usd`, and the retry lines.

## Driver

`scripts/try_agent.py` configures `labs-logging` (`app="weather-agents"`, `family="weather_agents"`, the level from settings), opens `ApiRuntime`, asks a weather question, prints the answer and its resources, then asks a follow-up on the same session. It is deleted in the same plan, once the live tests pass.

## Tests

`pyproject.toml` gains `-p no:logging` in `addopts`, as `labs-logging` requires. Fakes live in `tests/agent_loop/fakes.py`. `FakeModelCaller` returns scripted `ParsedMessage` objects in order and records each request. `FakeToolProvider` returns scripted outcomes and can hold calls at a barrier.

| File | Covers |
|---|---|
| `tests/test_settings.py` | Defaults, a `WEATHER_AGENTS_` override, `ANTHROPIC_API_KEY` without the prefix, and an unknown effort and a zero `max_tokens` failing with the field named |
| `tests/agent_loop/test_truncate.py` | Short values unchanged, long ones cut with the count, dicts rendered as JSON |
| `tests/agent_loop/test_ledger.py` | A match, a mismatch on arguments, key order not mattering, invalid JSON |
| `tests/agent_loop/test_model.py` | The request `AnthropicModelCaller` builds (strict tools, output format, thinking, effort, speed and beta header), and an SDK error wrapped as `ApiCallError`, against a fake SDK client |
| `tests/agent_loop/test_loop.py` | An answer on `end_turn`; three tool calls in flight at once (the barrier only opens when all three have started) with their results in one message, in order; `pause_turn`; each terminal stop reason; thinking blocks sent back unchanged; no parsed answer; a dropped resource; a tool exception becoming an error result; the event order |
| `tests/runtimes/test_mcp_tools.py` | The real server's schemas come out strict (no `minimum`, `maximum`, `minLength`, `maxItems`, or `pattern` left, `additionalProperties: false` on every object, `required` unchanged); text and structured results; `McpClientError` becoming an error result |
| `tests/runtimes/test_api_runtime.py` | A new session id; a follow-up sending the earlier history; an unknown id; a failed request leaving the question and the error message in the session; `clear`; `close`; a pool with every server failed |
| `tests/runtimes/test_logging.py` | `labs-logging` configured synchronously into `tmp_path`, with the JSON lines read back: the session id on every line, the debug fields with truncation, the info summary, and the error line |
| `tests/runtimes/test_live.py` (`live`) | One question through the real API and the real stdio server, then a follow-up that only makes sense with the history |

The `live` marker now covers both the real Open-Meteo and the real Anthropic API. Its description in `pyproject.toml` changes to say so.

## Docs and files

- `.env.example` at the package root, listing `ANTHROPIC_API_KEY` and every `WEATHER_AGENTS_` setting with its default.
- `architecture.md`: checked against what got built with `writing-architecture` in update mode. The `agent_loop`, `runtimes`, `agents`, and `settings` rows, the API runtime's message list store (now one per session), and the `.env` row are the likely changes.
- PRD-0002's status goes from `Draft` to `Building` when work starts.

## Deviations from the PRD

- **Use case 6, unsupported settings.** The PRD says a setting the model does not support fails before any model call. By the user's decision, there is no table of model capabilities, so the API rejects the first call with a 400, which costs no tokens, and the loop raises `ApiCallError`. Slice 2 adds a price table. If it grows capability fields, this deviation can close then.

## Later slices

Not in this spec: the deadline, the USD cap, retry settings, rate-limit waits, compaction, caching, and their log fields (slice 2); the stream to the caller, thinking summaries, and the retry event (slice 3); every Anthropic tool, the programmatic mode for MCP tools, and URL resources in the ledger (slice 4).
