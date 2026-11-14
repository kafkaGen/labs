# Tasks

Write each test before the code that makes it pass.

## 1. Dependencies

- [x] 1.1 Add `anthropic` and `pydantic-settings` to `packages/weather-agents/pyproject.toml`, run `uv sync`, and verify `uv run --package weather-agents python -c "import anthropic, pydantic_settings"` succeeds
- [x] 1.2 Widen the `live` marker's description in `pyproject.toml` to "calls the real Open-Meteo or Anthropic API", and verify `make test` still deselects live tests

## 2. Settings

- [x] 2.1 Add `weather_agents/settings.py` with `Settings` (`anthropic_api_key`, `model`, `max_tokens`, `mcp_config`), the `WEATHER_AGENTS_` prefix, `ANTHROPIC_API_KEY` unprefixed, and the default MCP config path, per design decision 7; verify with `tests/agent/test_settings.py` covering the default model, environment over default, override over environment, and `.env` loading
- [x] 2.2 Add the nearest-`.env` lookup walking up from the current directory, and verify a test that runs from a nested `tmp_path` directory picks up a `.env` two levels up
- [x] 2.3 Add `SettingsError` raised on load with each failing field's name and no input value, and verify tests for a negative `max_tokens`, a missing API key, and a missing MCP config file each name their field, and that a bad API key value never appears in the error text or in `repr(settings)`

## 3. Agent loop

- [x] 3.1 Add `agent_loop/tools.py` (`ToolProvider`, `ToolSpec`, `ToolOutcome`), `agent_loop/messages_api.py` (`MessagesApi`), and `agent_loop/errors.py` (`RunError`), and add `tests/agent/fakes.py` with `ScriptedMessages` and `FakeTools`; verify a smoke test that `ScriptedMessages` returns its queued `Message` and records the request
- [x] 3.2 Implement `run_loop` for the no-tool and sequential-tool paths, sending `response.content` back unchanged and `cache_control={"type": "ephemeral"}` on every request; verify tests "two tool rounds, then an answer", "no tool needed", "thinking blocks survive a tool round", and "caching on every request"
- [x] 3.3 Run every `tool_use` block of one turn in a `TaskGroup` and return the results in block order in one user message, with `is_error` passed through; verify the "two slow tools overlap" test (two 200 ms tools finish in under 350 ms, results in requested order) and the "server rejects an argument" test
- [x] 3.4 Raise `RunError` through one `_fail` helper for a non-`end_turn`, non-`tool_use` stop, for a tool call that raises, and for an `anthropic.APIError`; verify tests for `max_tokens` with a cut-off tool call (tool not called), a raising tool (error names the tool, siblings cancelled), an authentication error (cause preserved), and exactly one error log record per failure via `caplog`
- [x] 3.5 Verify the loop does not depend on MCP: `grep -rn "mcp" src/weather_agents/agent_loop` finds no import

## 4. API runtime

- [x] 4.1 Add `agents/__init__.py` with `WEATHER_SYSTEM_PROMPT`, a short prompt telling the agent to answer weather questions from the weather tools rather than from memory; verify the loop test fixtures pass it as `system`
- [x] 4.2 Add `runtimes/mcp_tools.py` with `McpToolProvider`, mapping `list_all_tools()` to `ToolSpec`s and `CallToolResult` to `ToolOutcome` (structured content as JSON, else joined text, `is_error` passed through); verify unit tests over `McpClientPool` with `tests/client/fakes.FakeClient`
- [x] 4.3 Add `runtimes/api.py` with `ApiRuntime` (async context manager, `send`, `close`) and `AgentResult(answer, session_id)`, with `messages_api` and `mcp_client_factory` injection; verify `tests/agent/test_runtime.py` covers tools named `<server>__<tool>` in the first request, a server that fails to open, two sends getting different ids, the pool closed on exit, and a `RunError` followed by a successful `send`
- [x] 4.4 Verify `make test` passes and `uv run ruff check packages/weather-agents` and `uv run ty check packages/weather-agents` report nothing new

## 5. Live check and docs

- [x] 5.1 Add `tests/live/test_api_runtime.py` (marked `live`) that opens the real runtime with default settings, sends "what's the weather in Lviv tomorrow?", and asserts a non-empty answer, a session id, and a recorded request carrying a `tool_result` for an `open-meteo__` tool; verify by running `make test-live` by hand and recording the outcome in the PR
- [x] 5.2 Update `packages/weather-agents/docs/architecture.md`: mark `agent_loop`, `runtimes` (API runtime only), and `settings` as Built for what F1 built, and correct the "No retries anywhere" and "tool calls from one model turn in order" lines to match the code; verify every Built claim names code that exists

## Workflow follow-up

- After the PR merges, archive this change and set F1 to `done` in `packages/weather-agents/docs/backlog/api-runtime.md`.
