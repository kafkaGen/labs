# Design

## Context

See `proposal.md` for why, and the three spec deltas for the behavior. These facts shape how F1 is built.

- `McpClientPool` (PRD-0001, built) opens one session per server from an `mcpServers` file, records servers that fail to open in `failures`, lists every open server's tools as `<server>__<tool>` through `list_all_tools()`, and calls them by that name through `call_namespaced_tool()`. A server-side error comes back as a `CallToolResult` with `is_error=True`. A transport or routing failure raises `McpClientError`. It must be entered and exited in the same asyncio task. It passes no handlers to the SDK client, so no client capabilities are declared.
- The pool takes a `client_factory`, and `tests/client/fakes.py` already has a `FakeClient` for it. Runtime tests can run the real pool with no child process.
- The level-1 server exposes eleven tools. They return structured content. The forecast tool counts days "starting today", and its output carries dates, so the model can resolve "tomorrow" without a date in the prompt.
- The default model is Claude Haiku 5.5 (`claude-haiku-5-5`). It runs adaptive thinking by default, so its responses carry `thinking` blocks that must go back to the API unchanged. Tool names must match `^[a-zA-Z0-9_-]{1,64}$`; `open-meteo__forecast` does.
- Automatic prompt caching is one top-level `cache_control={"type": "ephemeral"}` on `messages.create`. Its default lifetime is 5 minutes. A prefix shorter than the model's minimum silently does not cache, which is fine.
- Neither `anthropic` nor `pydantic-settings` is in the workspace yet. Async tests run under `pytest.mark.anyio` with the `asyncio` backend.
- The root `.env` holds the real `ANTHROPIC_API_KEY`. Tests and Makefile targets run from `packages/weather-agents`, not the repo root.

## Goals / Non-Goals

**Goals:**

- The loop never imports `mcp`. Only `runtimes` knows the tools come from MCP, as the architecture's module table requires.
- Every path in the specs is testable offline with a scripted fake of the Messages API and either a fake tool provider (loop tests) or the real pool over `FakeClient` (runtime tests).
- The seams later features extend stay small: one loop function, one `RunError`, one `Settings`, one tool-provider protocol.

**Non-Goals:**

- No session store. F1 returns a fresh id and keeps no history. F2 adds the store when something reads it.
- No streaming, no deadline, no USD cap, no price table, no retry settings. The SDK's default of 2 retries stands until F10.
- No change to `mcp_client` or `server`.
- No CLI command.

## Decisions

### 1. Module layout follows the architecture's module table

```text
weather_agents/
  settings.py              Settings (pydantic-settings)
  agents/
    __init__.py            WEATHER_SYSTEM_PROMPT
  agent_loop/
    __init__.py
    tools.py               ToolProvider protocol, ToolSpec, ToolOutcome
    messages_api.py        MessagesApi protocol (the slice of AsyncAnthropic.messages the loop uses)
    loop.py                run_loop()
    errors.py              RunError
  runtimes/
    __init__.py
    api.py                 ApiRuntime, AgentResult
    mcp_tools.py           McpToolProvider: McpClientPool -> ToolProvider
```

The MCP adapter lives in `runtimes`, not `agent_loop` or `mcp_client`. `mcp_client` stays model-agnostic, and shaping results for the loop is the runtime's job. The system prompt lives in `agents` because ADR-0004 makes prompts shared by both runtimes, so neither runtime should own it. It is one constant until a second agent exists.

The architecture's `AgentRuntime` protocol is not written yet. It would have one implementation, and its shape (streamed events) is only settled by F9. `ApiRuntime` keeps the method names the architecture gives it, so extracting the protocol later is a rename-free move.

### 2. The tool-provider seam is two methods

```python
class ToolProvider(Protocol):
    async def list_tools(self) -> list[ToolSpec]: ...                     # name, description, input_schema
    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome: ...  # text, is_error
```

`McpToolProvider` maps `list_all_tools()` to `ToolSpec`s and `call_namespaced_tool()` to `ToolOutcome`. It turns a `CallToolResult` into text: `structured_content` serialized as JSON when present, otherwise the text content blocks joined with newlines. `is_error` passes through. It does not catch `McpClientError`; the loop wraps any exception from `call` in a `RunError` (decision 4). F4 changes that to an error result.

The loop calls `list_tools()` once at the start of each run. Alternative: list once when the runtime opens. Rejected for F1 because the order and content are the same either way over stdio, and per-run listing keeps the runtime free of tool state. Tool order is the pool's order (file order, then server order), so the cached prefix stays stable.

### 3. The loop is one async function over `messages.create`

```text
run_loop(messages_api, tools, settings, system, question) -> str
  specs = await tools.list_tools()
  messages = [user question]
  loop:
    response = await messages_api.create(model, max_tokens, system, tools=specs,
                                         messages, cache_control={"type": "ephemeral"})
      API error -> RunError(cause=error)
    messages.append(assistant: response.content, unchanged)
    match response.stop_reason:
      end_turn -> return the text blocks of response.content, joined
      tool_use -> run every tool_use block concurrently,
                  append one user turn with every tool_result, in block order
      other    -> RunError(stop_reason)
```

- **Non-streaming `create`.** F9 brings streaming and rewrites this call site. `create` keeps the fake API to "return this `Message` next". `max_tokens` defaults to 16,000, which keeps a non-streaming call under the SDK's timeout.
- **The assistant turn is appended as `response.content`**, the SDK's block objects, so thinking blocks go back as they came.
- **Only `end_turn` returns and only `tool_use` continues.** `pause_turn` and `compaction` only arise with server tools and compaction, which F1 does not turn on. F6 adds them. Treating them as errors now is safe: they cannot happen.
- **A turn that is not `tool_use` runs no tools**, so a call cut off by `max_tokens` is never made.
- **MCP tools go without `strict`.** Strictness is F5's decision.

Alternative: the SDK's beta tool runner. Rejected because the architecture and the vision make the hand-written loop the point of the area.

### 4. Concurrent tool calls use one `TaskGroup`

Each `tool_use` block becomes a task in an `asyncio.TaskGroup`. Each task returns a `tool_result` param with the block's `tool_use_id`, the outcome's text, and `is_error` when set. The results are gathered in block order, not completion order, and go back as one user message.

A task whose `call` raises re-raises as `RunError(tool=name, cause=error)`. The `TaskGroup` cancels the siblings and raises an `ExceptionGroup`; the loop catches it with `except*` and re-raises the first `RunError` alone, so the caller catches one type.

Calls run from child tasks while the pool was entered in the caller's task. That is allowed: the pool's same-task rule is about entering and exiting, and the SDK client multiplexes concurrent requests on one session.

Alternative: `asyncio.gather`. Rejected because it leaves siblings running when one fails.

### 5. `RunError` is one exception, logged once where it is raised

```python
class RunError(Exception):
    stop_reason: str | None   # set when the model stopped for a reason other than end_turn
    tool: str | None          # set when a tool call raised
    # __cause__ holds the API or tool exception
```

The loop has one helper, `_fail(error) -> RunError`, that logs the error at `error` level with its cause and returns it for `raise`. Every raise site goes through it, and nothing above the loop logs a `RunError` again. F1 uses `logging.getLogger(__name__)`. F3 decides how `labs-logging` fits.

API errors are caught as `anthropic.APIError` (the base of status and connection errors) after the SDK's own retries. F10 splits retryable from terminal errors.

### 6. The runtime is an async context manager around the pool

```python
async with ApiRuntime(settings) as runtime:
    result = await runtime.send("what's the weather in Lviv tomorrow?")
    result.answer, result.session_id
```

- `__aenter__` builds the pool with `McpClientPool.from_file(settings.mcp_config, client_factory=...)` and enters it. `close()` and `__aexit__` exit it.
- `send` runs the loop and returns `AgentResult(answer, session_id)`. The id is `uuid4().hex`.
- The constructor takes two optional injection points for tests: `messages_api` (default `AsyncAnthropic(api_key=...).messages`) and `mcp_client_factory` (default the SDK's `Client`). Nothing else is injectable.
- A `RunError` propagates out of `send` unchanged. The pool and the client hold no per-run state, so the next `send` works.

### 7. Settings: pydantic-settings, prefixed, with the nearest `.env`

```python
class Settings(BaseSettings):
    anthropic_api_key: SecretStr        # env: ANTHROPIC_API_KEY (no prefix)
    model: str = "claude-haiku-5-5"     # env: WEATHER_AGENTS_MODEL
    max_tokens: PositiveInt = 16_000    # env: WEATHER_AGENTS_MAX_TOKENS
    mcp_config: FilePath = <package root>/mcp.stdio.json   # env: WEATHER_AGENTS_MCP_CONFIG
```

- **Priority** is pydantic-settings' own: init kwargs (the per-run overrides) beat the environment, which beats `.env`, which beats defaults. The spec groups `.env` and the environment as one level, and this order fits it.
- **`.env` is the nearest one walking up from the current directory.** Tests run from the package directory and the key lives in the repo root's `.env`. Alternative: a fixed `.env` in the current directory. Rejected: `make test-live` would not find the key. Alternative: a path computed from `__file__`. Rejected: it ties a library to the repo layout more than the walk does.
- **The API key goes to `AsyncAnthropic(api_key=...)` explicitly.** The SDK reads `os.environ`, which does not see values loaded only from `.env`.
- **Errors name the field and hide the input.** `Settings` re-raises `ValidationError` as `SettingsError` with each failing field's name and message, and without `input`, so a bad key value never reaches a log. `SecretStr` covers printing.
- **The default MCP config** is the package's `mcp.stdio.json`, found relative to the package source. It works because the package is only ever installed editable in this workspace.

Only the four fields F1 uses exist. Later features add theirs.

### 8. Tests

- `tests/agent/fakes.py`: `ScriptedMessages`, a `MessagesApi` that returns queued `anthropic.types.Message` objects (built with `Message.model_validate`) and records every request's kwargs; `FakeTools`, a `ToolProvider` with canned outcomes, optional delays, and optional exceptions.
- `tests/agent/test_loop.py`: one test per loop scenario in the spec.
- `tests/agent/test_runtime.py`: the runtime over the real `McpClientPool` with `tests/client/fakes.FakeClient`, plus `ScriptedMessages`.
- `tests/agent/test_settings.py`: priority, defaults, and every failure, using `monkeypatch` for the environment and `tmp_path` for `.env` files.
- `tests/live/test_api_runtime.py`, marked `live`: the real runtime, real API, real stdio server. A recording wrapper around the real `messages` checks that a request after the first carried a `tool_result` for an `open-meteo__` tool, which is how "built from MCP tool results" is checked.

## Risks / Trade-offs

- [The SDK's MCP client might serialize concurrent calls on one stdio session] → The concurrency test runs against `FakeTools`, not MCP. The live test logs nothing about timing. If calls serialize, the spec still holds at the loop level, and the gap is noted for F3's logs to reveal.
- [Haiku 5.5 may answer "tomorrow" without calling a tool] → The live test asserts a tool result was sent. If Haiku skips tools, the system prompt says to use the weather tools for any weather fact.
- [A live run costs money] → One Haiku question is a fraction of a cent, and the test runs only by hand.
- [Raising on a tool exception is harsher than the final behavior] → F4 replaces it with an error result. Until then the caller sees a `RunError` naming the tool, which is honest.
- [Treating `pause_turn` as an error] → It needs server tools, which F1 never enables. F6 adds it before F13 to F16 enable them.

## Open Questions

- Whether `list_tools()` per run should move to runtime open once tool search (F15) lands. It does not change F1's specs or tasks.
