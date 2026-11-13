# Tasks

## 1. Setup

- [x] 1.1 Move PRD-0002's `Status` from `Draft` to `Building` in `packages/weather-agents/docs/prd/0002-api-agent-loop.md`, and change nothing else in the file. Verify that `git diff` on the PRD shows only the status line.
- [x] 1.2 Add `anthropic`, `pydantic-settings` and `labs-logging` (with `[tool.uv.sources] labs-logging = { workspace = true }`) to `packages/weather-agents/pyproject.toml`. Update the `live` marker's description to cover the Anthropic API too. Verify that `uv sync` succeeds and `uv run --package weather-agents python -c "import anthropic, pydantic_settings, labs_logging"` exits 0.
- [x] 1.3 Create the empty `agent_loop/` and `runtimes/` packages, and `tests/agent_loop/` and `tests/runtimes/`, as laid out in design.md decision 1. Verify that `make test` still passes.

## 2. Settings

- [x] 2.1 Implement `weather_agents/settings.py` (design decision 9): fields, defaults, `WEATHER_AGENTS_` prefix, `.env` support, `ANTHROPIC_API_KEY` as `SecretStr`, and validation for values that must be positive. Verify with unit tests for the defaults, environment-over-default precedence, and the negative-cap and zero-deadline errors naming their fields.
- [x] 2.2 Add `Settings.with_overrides(**changes)`. It revalidates the changed settings and rejects an API-key override. Verify with unit tests: an override beats the environment, an invalid override fails naming the field, and an API-key override is refused.

## 3. Tool seam and MCP adapter

- [x] 3.1 Implement `agent_loop/tools.py` with the `ToolProvider` protocol, `ToolSpec` and `ToolOutcome` (design decision 2). Verify that `ty` and `ruff` pass on the module.
- [x] 3.2 Implement `runtimes/mcp_tools.py` `McpToolProvider` over `McpClientPool` (design decisions 2 and 3). It passes each tool's `input_schema` through unchanged, turns `CallToolResult` into `ToolOutcome` (structured content first, then text), turns `McpClientError` into an error outcome, and logs each failed server from `pool.failures`. Verify with unit tests on the PRD-0001 fake client from `tests/client/fakes.py`: a schema with `minimum` and `maximum` comes out unchanged, a normal result, an `is_error` result, a raised `McpClientError`, and a failed server named in the log.

## 4. Errors, pricing and trace helpers

- [x] 4.1 Implement `agent_loop/errors.py`: `RunError` (stop reason or limit, usage, cost, partial text), `RunLimit`, `ConfigurationError` and `UnknownSessionError`. Verify with a unit test that the `RunError` message names its stop reason or limit.
- [x] 4.2 Implement `agent_loop/pricing.py` with `PRICES` (Haiku 5.5, Sonnet 5.5 and Opus 5.5 base rates, with the source and the date checked in a comment) and `cost(usage, model)`. Verify with unit tests: a known usage gives the expected USD, and an unknown model raises `ConfigurationError` naming it.
- [x] 4.3 Implement `agent_loop/trace.py` `truncate()`. Verify with unit tests: a short value is unchanged, and a 5,000-character value is cut to the limit and reports `truncated=True` and its original length.

## 5. Structured answer

- [x] 5.1 Implement `agent_loop/answer.py`: the `Answer`, `Resource`, `ToolCallSource` and `UrlSource` models, the strict answer JSON schema for `output_config.format`, and the ledger-based resolution (design decision 5). Verify with unit tests: a known `tool_use_id` resolves to a tool name and arguments, a URL found in a tool result resolves, an unknown id or URL is dropped and logged, and text that doesn't match the schema raises `RunError`. Also check that the schema has `additionalProperties: false` on every object.

## 6. The loop

- [x] 6.1 Add the scripted fake `AsyncAnthropic` (`FakeMessages` returning real `anthropic.types.Message` objects, recording requests) and `FakeToolProvider` (scripted outcomes, optional raise, start and end timestamps) under `tests/agent_loop/fakes.py`. Verify that one smoke test drives one scripted `end_turn` through the fake.
- [x] 6.2 Implement `agent_loop/loop.py` `run_agent()` up to `end_turn` and `tool_use`. The tool specs, without `strict`, and the answer schema go on every request, the assistant content is appended unchanged, all tool calls of a turn run in a `TaskGroup`, and all results go back in one user message. Verify with unit tests: a two-turn run returns the resolved answer, two tool calls overlap in time and come back in one message, an `is_error` outcome and a raising provider both reach the model as `is_error` results, and thinking blocks are passed back unchanged.
- [x] 6.3 Add the stop-reason handling: `pause_turn` continues with no new user turn, and `max_tokens`, `stop_sequence`, `refusal` and `model_context_window_exceeded` raise `RunError` with usage, cost and partial text, without running that turn's tools. Verify with one parameterized unit test per stop reason.
- [x] 6.4 Add the limits: the price check before the first call, the USD cap checked before every call, and the deadline as one `asyncio.timeout` that becomes `RunError(limit=DEADLINE)`. Verify with unit tests: an unpriced model fails with zero recorded requests, a cap hit after the first call stops with exactly one request, and a fake tool that sleeps past a 0.2-second deadline is cancelled and raises within the deadline plus one second.
- [x] 6.5 Add step and end-of-run logging (design decision 10): debug lines for model request and response, tool call and result, each truncated and carrying tokens so far and seconds left, an info `run.end` line in `finally`, and the cause of a run error logged once. Verify with unit tests that capture log records: a one-round run has each debug line, every line carries the bound session id, a long result is marked truncated, and a failed run still writes `run.end` with turns and tool calls.

## 7. The API runtime and sessions

- [x] 7.1 Implement `runtimes/base.py` with the `AgentRuntime` protocol and `AgentResult` (answer, resources, session id, usage, cost). Verify that `ty` passes with `ApiRuntime` assigned to an `AgentRuntime`-typed variable in a test.
- [x] 7.2 Implement `runtimes/api.py` `ApiRuntime` (design decision 8): an async context manager that opens the pool, builds the `AsyncAnthropic` client from settings, holds the system prompt constant, and implements `send` with new and existing sessions, `bound_context(session_id=...)`, and per-run overrides. Verify with unit tests on the fake API and fake provider: a send without an id returns a new id, and a follow-up sends the earlier exchange, tool turns included.
- [x] 7.3 Add the failure and lifetime paths: an unknown id raises `UnknownSessionError` before any request, a `RunError` leaves exactly the question plus an assistant error text in the session, `clear` forgets one session, and `close` forgets all and closes the pool. Verify with unit tests for each, including that a follow-up after a deadline failure carries no tool turns from the failed request.

## 8. Live checks and docs

- [x] 8.1 Add `live` tests under `tests/live/` that configure `labs-logging` (family `weather_agents`) and open a real `ApiRuntime` over `mcp.stdio.json`. Ask "What is the weather in Lviv tomorrow?" and assert a non-empty answer and at least one tool-call resource. Then ask "and the day after?" in the same session and assert the same session id and an answer that mentions Lviv. Verify by running `make test-live` by hand with `ANTHROPIC_API_KEY` set, and record the cost the run logged in the PR description.
- [x] 8.2 Correct `packages/weather-agents/docs/architecture.md` for what B1 built. The `agent_loop`, `runtimes` and `settings` rows become Built with B1's scope. The API runtime data store becomes one message list per session. The API-runtime sequence diagram and the error-handling row say a hit cap or deadline raises a run error. The "no retries anywhere" row and the Planned streaming parts stay as they are. Verify that every line marked Built matches the code.
- [x] 8.3 Run the full offline suite plus lint and types. Verify that `make test`, `uv run ruff check packages/weather-agents` and `uv run ty check packages/weather-agents` all pass.

## Workflow follow-up

- Open one PR for B1, get it reviewed and merge it.
- Archive this change after merge so its specs move to `openspec/specs/`.
- B2, B3 and B4 each start as their own change from the roadmap in `proposal.md`.
