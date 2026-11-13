# Agent Loop Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A caller opens the API runtime, asks a weather question, and gets back a structured answer with its sources and a session id it can send again to continue the conversation, with the agent calling the MCP tools and every step logged.

**Architecture:** `agent_loop` is an async generator that yields events while it calls the model through a `ModelCaller` interface and runs tools through a `ToolProvider` interface. It knows nothing about MCP. `runtimes.ApiRuntime` wires the real pieces together (the SDK-backed caller, the MCP pool behind `McpToolProvider`), holds in-memory sessions, and logs through `labs-logging`. Spec: [`../specs/2026-10-17-agent-loop-core-design.md`](../specs/2026-10-17-agent-loop-core-design.md). PRD: [PRD-0002](../../prd/0002-api-agent-loop.md), slice 1 of 4.

**Tech Stack:** Python 3.12, `anthropic>=1.15,<2`, `pydantic-settings>=2`, `labs-logging` (workspace), `mcp>=2,<3` (already a dependency), pytest with the anyio plugin, Ruff, ty.

## Global Constraints

- Python 3.12 in the `labs` uv workspace. New dependencies: `anthropic>=1.15,<2`, `pydantic-settings>=2`, and `labs-logging` as a workspace source. Add them with `uv add`, never by hand.
- `weather_agents.agent_loop` imports nothing from `weather_agents.mcp_client` or `mcp`. `weather_agents.runtimes` is the only package that knows both.
- The loop is hand-written on `client.messages.stream(...)`. Never use the SDK's `tool_runner`, and never pass `output_format=` (the SDK would parse every text block as the stream ends). The answer schema goes in `output_config.format`.
- Every tool is sent with `strict: True`. MCP schemas pass through `anthropic.transform_schema` first.
- Settings: prefix `WEATHER_AGENTS_`, file `packages/weather-agents/.env`. The API key is `ANTHROPIC_API_KEY`, with no prefix. Defaults: model `claude-haiku-5-5`, effort `low`, thinking on (adaptive), `max_tokens` 32,000, fast mode off, `mcp_config` `mcp.stdio.json`, `log_level` `INFO`, `log_truncate` 200.
- Fast mode sends `speed="fast"` with the beta header `fast-mode-2026-02-01`. There is no table of model capabilities: an unsupported setting is the API's 400, raised as `ApiCallError`.
- No retries, deadline, cost, compaction, or caching in this plan. The SDK keeps its default retries. Those arrive in slice 2.
- Sessions live in memory only. Nothing writes a session's history to a file or store.
- Logging uses `labs_logging.get_logger(__name__)` with keyword fields. Only an entry point calls `configure`. The runtime never does.
- Repo conventions (`.cursor/rules/python-conventions.mdc`): `uv run` for every command, type hints everywhere, no `Any`, Google-style docstrings on public names, `__all__` in every public module, absolute imports, f-strings for human-facing text and lazy fields for logs, Ruff line length 100.
- Commit messages follow the log: `[feature] (weather-agents) <what>` or `[docs] (weather-agents) <what>`. Pre-commit hooks run Ruff, ty, and pytest. Fix what they report. Never use `--no-verify`. If ty flags an SDK TypedDict or a pydantic-settings constructor in the code below, fix it with a scoped `# ty: ignore[<rule>]` on that line, not by loosening types.
- Work in the worktree `/Users/oboryse/Projects/labs/.worktrees/weather-agents-agent-loop-core` on branch `weather-agents/agent-loop-core`. Run package commands from `packages/weather-agents/` inside it. `uv` must read the root `uv.lock`; if the sandbox blocks it, run outside the sandbox.
- The test command is `uv run --package weather-agents --group dev pytest <path> -v`. `make test` runs everything offline.

## File Structure

```
pyproject.toml                                     Task 1: dependencies, pytest addopts and marker
.env.example                                       Task 1
src/weather_agents/settings.py                     Task 1: PACKAGE_ROOT, Effort, LogLevel, Settings
tests/conftest.py                                  Task 1: clear WEATHER_AGENTS_* from the shell
tests/test_settings.py                             Task 1
tests/agent_loop/__init__.py                       Task 1
tests/agent_loop/fakes.py                          Task 1 (make_settings), Task 3 (builders), Task 4 (fakes)
src/weather_agents/agents/__init__.py              Task 2
src/weather_agents/agents/definitions.py           Task 2: AgentDefinition, WEATHER_AGENT
src/weather_agents/agent_loop/__init__.py          Task 2, Task 3, Task 4 (exports)
src/weather_agents/agent_loop/answer.py            Task 2: Answer, UrlResource, ToolCallResource, Resource
src/weather_agents/agent_loop/result.py            Task 2: TokenUsage, RunResult
src/weather_agents/agent_loop/errors.py            Task 2: RunError, StopReasonError, InvalidAnswerError, ApiCallError
src/weather_agents/agent_loop/interfaces.py        Task 2: ModelRequest, ModelCaller, ToolSpec, ToolOutcome, ToolProvider
src/weather_agents/agent_loop/events.py            Task 2: ModelTurn, ToolCallStarted, ToolCallFinished, RunFinished, Event
src/weather_agents/agent_loop/ledger.py            Task 2: SourceLedger
src/weather_agents/agent_loop/truncate.py          Task 2: truncate
tests/agent_loop/test_answer.py, test_ledger.py, test_truncate.py   Task 2
src/weather_agents/agent_loop/model.py             Task 3: ANSWER_SCHEMA, FAST_MODE_BETA, AnthropicModelCaller
tests/agent_loop/test_model.py                     Task 3
src/weather_agents/agent_loop/loop.py              Task 4: run_agent
tests/agent_loop/test_loop.py                      Task 4
src/weather_agents/runtimes/__init__.py            Task 5, Task 6 (exports)
src/weather_agents/runtimes/mcp_tools.py           Task 5: ToolPool, McpToolProvider
tests/runtimes/__init__.py, fakes.py               Task 5: FakePool, FORECAST_TOOL
tests/runtimes/test_mcp_tools.py                   Task 5
src/weather_agents/runtimes/base.py                Task 6: AgentRuntime, SessionNotFoundError
src/weather_agents/runtimes/api.py                 Task 6: Session, ApiRuntime
tests/runtimes/test_api_runtime.py                 Task 6
tests/runtimes/test_logging.py                     Task 7
tests/live/test_agent_live.py                      Task 8
Makefile                                           Task 8: test-live help text
scripts/try_agent.py                               Task 8: throwaway, never committed
docs/architecture.md                               Task 9
docs/prd/0002-api-agent-loop.md                    Task 1: Status line only
```

All paths below are relative to `packages/weather-agents/` unless they start with `/`.

## Docs Check

- `docs/architecture.md` could drift: the `agent_loop`, `runtimes`, `agents`, and `settings` rows say Planned, the "API runtime's message list" store becomes one list per session, and the `.env` row gains the `WEATHER_AGENTS_` settings. Task 9 checks it with `writing-architecture` in update mode.
- `docs/prd/0002-api-agent-loop.md`: only its `Status` line changes, `Draft` to `Building`, in Task 1. It stays `Building` after this plan, because slices 2 to 4 are unbuilt.
- `Makefile`: the `test-live` help text says it calls only Open-Meteo. Task 8 updates it.
- `docs/vision.md` and `docs/adr/` are not touched. No ADR came out of the design session. The package has no README.

---

### Task 1: Dependencies, settings, and the PRD status

**Files:**
- Modify: `pyproject.toml` (dependencies via `uv add`, `[tool.pytest.ini_options]`)
- Modify: `docs/prd/0002-api-agent-loop.md:3` (Status line)
- Modify: `tests/conftest.py`
- Create: `src/weather_agents/settings.py`, `.env.example`, `tests/test_settings.py`, `tests/agent_loop/__init__.py`, `tests/agent_loop/fakes.py`

**Interfaces:**
- Produces:
  - `PACKAGE_ROOT: Path`, the `packages/weather-agents` directory.
  - `Effort = Literal["low", "medium", "high", "xhigh", "max"]`, `LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]`.
  - `Settings(BaseSettings)` with fields `model: str`, `effort: Effort`, `thinking: bool`, `max_tokens: int`, `fast_mode: bool`, `mcp_config: Path`, `log_level: LogLevel`, `log_truncate: int`, `anthropic_api_key: SecretStr`.
  - `tests.agent_loop.fakes.make_settings(**overrides) -> Settings`, which ignores `.env` and uses the key `"test-key"`.

- [ ] **Step 1: Mark the PRD as being built**

In `docs/prd/0002-api-agent-loop.md`, change line 3 from `**Status:** Draft` to `**Status:** Building`. Nothing else in the file changes.

- [ ] **Step 2: Add the dependencies**

From the worktree root:

```bash
uv add --package weather-agents "anthropic>=1.15,<2" "pydantic-settings>=2" labs-logging
```

Expected: `packages/weather-agents/pyproject.toml` lists the three, `[tool.uv.sources]` gains `labs-logging = { workspace = true }`, and `uv.lock` updates. If uv does not add the source line, add it with `uv add --package weather-agents labs-logging --workspace`.

- [ ] **Step 3: Update the pytest settings**

In `pyproject.toml`, replace the `[tool.pytest.ini_options]` table with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
# labs-logging refuses to configure while pytest's logging plugin holds root handlers.
addopts = "-m 'not live' -p no:logging"
markers = [
    "live: calls the real Open-Meteo API or the real Anthropic API",
]
```

- [ ] **Step 4: Keep shell settings out of the tests**

Append to `tests/conftest.py` (add `import os` to its imports):

```python
@pytest.fixture(autouse=True)
def _no_agent_settings_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("WEATHER_AGENTS_"):
            monkeypatch.delenv(name)
```

- [ ] **Step 5: Write the failing settings tests**

Create `tests/agent_loop/__init__.py` as an empty file. Create `tests/agent_loop/fakes.py`:

```python
"""Fakes and builders for the agent loop and runtime tests."""

from weather_agents.settings import Settings


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore `.env` and carry a dummy API key."""
    return Settings(_env_file=None, anthropic_api_key="test-key", **overrides)
```

Create `tests/test_settings.py`:

```python
import pytest
from pydantic import ValidationError

from weather_agents.settings import PACKAGE_ROOT, Settings


def test_the_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    settings = Settings(_env_file=None)
    assert settings.model == "claude-haiku-5-5"
    assert settings.effort == "low"
    assert settings.thinking is True
    assert settings.max_tokens == 32_000
    assert settings.fast_mode is False
    assert settings.mcp_config == PACKAGE_ROOT / "mcp.stdio.json"
    assert settings.log_level == "INFO"
    assert settings.log_truncate == 200
    assert settings.anthropic_api_key.get_secret_value() == "key"


def test_prefixed_environment_variables_override_the_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("WEATHER_AGENTS_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("WEATHER_AGENTS_EFFORT", "high")
    monkeypatch.setenv("WEATHER_AGENTS_THINKING", "false")
    monkeypatch.setenv("WEATHER_AGENTS_MCP_CONFIG", "mcp.http.json")
    settings = Settings(_env_file=None)
    assert settings.model == "claude-sonnet-5-5"
    assert settings.effort == "high"
    assert settings.thinking is False
    assert settings.mcp_config == PACKAGE_ROOT / "mcp.http.json"


def test_an_absolute_mcp_config_is_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    settings = Settings(_env_file=None, mcp_config=tmp_path / "mcp.json")
    assert settings.mcp_config == tmp_path / "mcp.json"


def test_the_api_key_is_read_without_the_prefix(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("WEATHER_AGENTS_ANTHROPIC_API_KEY", "wrong")
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None)


def test_an_unknown_effort_fails_naming_the_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("WEATHER_AGENTS_EFFORT", "extreme")
    with pytest.raises(ValidationError, match="effort"):
        Settings(_env_file=None)


def test_a_zero_max_tokens_fails_naming_the_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    with pytest.raises(ValidationError, match="max_tokens"):
        Settings(_env_file=None, max_tokens=0)


def test_the_key_never_shows_in_the_repr(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "very-secret")
    assert "very-secret" not in repr(Settings(_env_file=None))
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'weather_agents.settings'`.

- [ ] **Step 7: Write the settings**

Create `src/weather_agents/settings.py`:

```python
"""Agent runtime settings: defaults here, then `packages/weather-agents/.env`, then the environment."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["PACKAGE_ROOT", "Effort", "LogLevel", "Settings"]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

# Literals, not Enums, so the values pass to the SDK's typed parameters unchanged.
Effort = Literal["low", "medium", "high", "xhigh", "max"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Everything the API runtime reads.

    Each field is read from `WEATHER_AGENTS_<FIELD>` in the environment or in
    `packages/weather-agents/.env`, except the API key, which is plain `ANTHROPIC_API_KEY`.
    An invalid value fails when the object is built, and the error names the field.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEATHER_AGENTS_",
        env_file=PACKAGE_ROOT / ".env",
        extra="ignore",
        populate_by_name=True,
    )

    model: str = "claude-haiku-5-5"
    effort: Effort = "low"
    thinking: bool = True
    max_tokens: Annotated[int, Field(gt=0)] = 32_000
    fast_mode: bool = False
    mcp_config: Path = PACKAGE_ROOT / "mcp.stdio.json"
    log_level: LogLevel = "INFO"
    log_truncate: Annotated[int, Field(gt=0)] = 200
    anthropic_api_key: Annotated[SecretStr, Field(validation_alias="ANTHROPIC_API_KEY")]

    @field_validator("mcp_config")
    @classmethod
    def _resolve_from_package_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PACKAGE_ROOT / value
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/test_settings.py -v`
Expected: 7 passed. If `populate_by_name` does not let `anthropic_api_key=` through in `make_settings`, replace the alias with `Field(validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"))` and import `AliasChoices` from pydantic, then re-run.

- [ ] **Step 9: Write `.env.example`**

Create `.env.example`:

```sh
# Copy to .env. Only ANTHROPIC_API_KEY is required; every other line shows its default.
ANTHROPIC_API_KEY=
# WEATHER_AGENTS_MODEL=claude-haiku-5-5
# WEATHER_AGENTS_EFFORT=low            # low, medium, high, xhigh, max
# WEATHER_AGENTS_THINKING=true         # adaptive thinking on or off
# WEATHER_AGENTS_MAX_TOKENS=32000
# WEATHER_AGENTS_FAST_MODE=false       # Opus 5.5 only; other models reject it
# WEATHER_AGENTS_MCP_CONFIG=mcp.stdio.json
# WEATHER_AGENTS_LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR
# WEATHER_AGENTS_LOG_TRUNCATE=200      # characters per logged value at debug level
```

- [ ] **Step 10: Run the whole suite**

Run: `uv run --package weather-agents --group dev pytest`
Expected: every existing test still passes with `-p no:logging`.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml ../../uv.lock .env.example src/weather_agents/settings.py tests/conftest.py \
        tests/test_settings.py tests/agent_loop docs/prd/0002-api-agent-loop.md
git commit -m "[feature] (weather-agents) Add the agent runtime settings and its dependencies"
```

---

### Task 2: The loop's data types and the weather agent

**Files:**
- Create: `src/weather_agents/agents/__init__.py`, `src/weather_agents/agents/definitions.py`
- Create: `src/weather_agents/agent_loop/__init__.py`, `answer.py`, `result.py`, `errors.py`, `interfaces.py`, `events.py`, `ledger.py`, `truncate.py`
- Test: `tests/agent_loop/test_answer.py`, `tests/agent_loop/test_ledger.py`, `tests/agent_loop/test_truncate.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except `anthropic.types`.
- Produces:
  - `AgentDefinition(name: str, system_prompt: str)`, frozen. `WEATHER_AGENT: AgentDefinition`.
  - `UrlResource(kind: Literal["url"], url: str, title: str)`, `ToolCallResource(kind: Literal["tool_call"], tool: str, arguments: str, title: str)`, `Resource` (the discriminated union), `Answer(answer: str, resources: list[Resource])`. All frozen.
  - `TokenUsage(input: int = 0, output: int = 0, cache_read: int = 0, cache_write: int = 0)`, frozen, with `add(usage: anthropic.types.Usage) -> TokenUsage`.
  - `RunResult(answer: Answer, session_id: str, usage: TokenUsage, turns: int, tool_calls: int)`, frozen.
  - `RunError(message: str, *, usage: TokenUsage | None = None, partial_text: str = "")` with mutable attributes `usage`, `partial_text`, `session_id` (starts as `""`).
  - `StopReasonError(stop_reason: str, *, usage=None, partial_text="")` with `.stop_reason`, message `the model stopped with '<stop_reason>'`.
  - `InvalidAnswerError(RunError)`, same constructor as `RunError`.
  - `ApiCallError(message: str, *, status_code: int | None, usage=None)` with `.status_code`.
  - `ModelRequest(system: str, messages: list[MessageParam], tools: list[ToolSpec])`, a frozen dataclass.
  - `ModelCaller` protocol: `async call(request: ModelRequest) -> anthropic.types.Message`.
  - `ToolSpec(name: str, description: str, input_schema: dict[str, object])`, `ToolOutcome(content: str, is_error: bool = False)`, both frozen.
  - `ToolProvider` protocol: `async list_tools() -> list[ToolSpec]`, `async call(name: str, arguments: dict[str, object]) -> ToolOutcome`.
  - Events, frozen dataclasses: `ModelTurn(step: int, stop_reason: str | None, usage: TokenUsage, tool_uses: list[str])`, `ToolCallStarted(id: str, name: str, arguments: dict[str, object])`, `ToolCallFinished(id: str, name: str, is_error: bool, content: str)`, `RunFinished(result: RunResult, messages: list[MessageParam])`, and `Event` as their union.
  - `SourceLedger()` with `record_tool_call(name: str, arguments: dict[str, object]) -> None`, `has_tool_call(name: str, arguments_json: str) -> bool`, `record_url(url: str) -> None`, `has_url(url: str) -> bool`.
  - `truncate(value: object, limit: int) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/agent_loop/test_truncate.py`:

```python
from weather_agents.agent_loop.truncate import truncate


def test_a_short_value_is_unchanged():
    assert truncate("sunny", 10) == "sunny"


def test_a_long_value_is_cut_and_says_how_much():
    assert truncate("x" * 25, 10) == "xxxxxxxxxx… [cut 15 chars]"


def test_dicts_and_lists_are_rendered_as_json():
    assert truncate({"latitude": 52.5}, 100) == '{"latitude": 52.5}'
    assert truncate([1, 2], 100) == "[1, 2]"


def test_other_values_use_str():
    assert truncate(42, 100) == "42"
```

Create `tests/agent_loop/test_ledger.py`:

```python
from weather_agents.agent_loop.ledger import SourceLedger


def test_a_recorded_call_matches_with_the_same_name_and_arguments():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert ledger.has_tool_call("open-meteo__forecast", '{"latitude": 52.52, "longitude": 13.41}')


def test_key_order_does_not_matter():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert ledger.has_tool_call("open-meteo__forecast", '{"longitude": 13.41, "latitude": 52.52}')


def test_other_arguments_or_another_tool_do_not_match():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert not ledger.has_tool_call("open-meteo__forecast", '{"latitude": 0, "longitude": 0}')
    assert not ledger.has_tool_call("open-meteo__marine", '{"latitude": 52.52, "longitude": 13.41}')


def test_invalid_json_does_not_match():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {})
    assert not ledger.has_tool_call("open-meteo__forecast", "{not json")


def test_a_url_matches_only_once_recorded():
    ledger = SourceLedger()
    assert not ledger.has_url("https://open-meteo.com")
    ledger.record_url("https://open-meteo.com")
    assert ledger.has_url("https://open-meteo.com")
```

Create `tests/agent_loop/test_answer.py`:

```python
import json

import anthropic

from weather_agents.agent_loop.answer import Answer, ToolCallResource, UrlResource
from weather_agents.agent_loop.result import TokenUsage
from anthropic.types import Usage


def test_an_answer_with_both_kinds_of_resource_parses_from_json():
    text = json.dumps(
        {
            "answer": "Sunny, 21 °C.",
            "resources": [
                {"kind": "url", "url": "https://open-meteo.com", "title": "Open-Meteo"},
                {
                    "kind": "tool_call",
                    "tool": "open-meteo__forecast",
                    "arguments": '{"latitude": 52.52}',
                    "title": "Forecast",
                },
            ],
        }
    )
    answer = Answer.model_validate_json(text)
    assert isinstance(answer.resources[0], UrlResource)
    assert isinstance(answer.resources[1], ToolCallResource)


def test_the_strict_schema_closes_every_object():
    schema = anthropic.transform_schema(Answer)
    objects = [schema, *schema["$defs"].values()]
    assert all(item["additionalProperties"] is False for item in objects)


def test_token_usage_adds_a_reply_including_cache_counts():
    usage = TokenUsage().add(
        Usage(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=3,
            cache_creation_input_tokens=2,
        )
    )
    assert usage == TokenUsage(input=10, output=5, cache_read=3, cache_write=2)
    assert usage.add(Usage(input_tokens=1, output_tokens=1)).input == 11
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'weather_agents.agent_loop'`.

- [ ] **Step 3: Write the agent definition**

Create `src/weather_agents/agents/definitions.py`:

```python
"""Agent definitions: system prompts that both runtimes read, so neither owns a prompt."""

from pydantic import BaseModel, ConfigDict

__all__ = ["WEATHER_AGENT", "AgentDefinition"]


class AgentDefinition(BaseModel):
    """One agent's name and system prompt."""

    model_config = ConfigDict(frozen=True)

    name: str
    system_prompt: str


_WEATHER_PROMPT = """\
You answer questions about weather with the tools you are given. Take every number you report \
from a tool result, and say plainly when the tools cannot answer.

Reply with an answer and its resources. List each tool call you relied on as a resource of kind \
"tool_call": `tool` is the tool's name exactly as you called it, `arguments` is the exact JSON \
object you sent, written as a string, and `title` says in a few words what it gave you. Never \
list a source you did not use."""

WEATHER_AGENT = AgentDefinition(name="weather", system_prompt=_WEATHER_PROMPT)
```

Create `src/weather_agents/agents/__init__.py`:

```python
"""Agent definitions shared by both runtimes."""

from weather_agents.agents.definitions import WEATHER_AGENT, AgentDefinition

__all__ = ["WEATHER_AGENT", "AgentDefinition"]
```

- [ ] **Step 4: Write the answer and the result**

Create `src/weather_agents/agent_loop/answer.py`:

```python
"""The structured answer a run returns: the text and the sources that back it."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Answer", "Resource", "ToolCallResource", "UrlResource"]


class UrlResource(BaseModel):
    """A web page the answer relied on."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["url"]
    url: str
    title: str


class ToolCallResource(BaseModel):
    """A tool call whose result the answer relied on.

    `arguments` is JSON text rather than an object, because strict structured output forbids an
    object with free-form keys.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_call"]
    tool: str
    arguments: str
    title: str


Resource = Annotated[UrlResource | ToolCallResource, Field(discriminator="kind")]


class Answer(BaseModel):
    """What the model must return when it finishes."""

    model_config = ConfigDict(frozen=True)

    answer: str
    resources: list[Resource]
```

Create `src/weather_agents/agent_loop/result.py`:

```python
"""What a finished run reports: the answer, the session, and the tokens it took."""

from typing import Self

from anthropic.types import Usage
from pydantic import BaseModel, ConfigDict

from weather_agents.agent_loop.answer import Answer

__all__ = ["RunResult", "TokenUsage"]


class TokenUsage(BaseModel):
    """Token counts summed over every model call in a run."""

    model_config = ConfigDict(frozen=True)

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add(self, usage: Usage) -> Self:
        """Return these totals plus one reply's usage."""
        return self.model_copy(
            update={
                "input": self.input + usage.input_tokens,
                "output": self.output + usage.output_tokens,
                "cache_read": self.cache_read + (usage.cache_read_input_tokens or 0),
                "cache_write": self.cache_write + (usage.cache_creation_input_tokens or 0),
            }
        )


class RunResult(BaseModel):
    """A successful run. `turns` counts model calls."""

    model_config = ConfigDict(frozen=True)

    answer: Answer
    session_id: str
    usage: TokenUsage
    turns: int
    tool_calls: int
```

- [ ] **Step 5: Write the errors**

Create `src/weather_agents/agent_loop/errors.py`:

```python
"""Errors a run raises. Each carries what the run had spent and said before it stopped."""

from weather_agents.agent_loop.result import TokenUsage

__all__ = ["ApiCallError", "InvalidAnswerError", "RunError", "StopReasonError"]


class RunError(Exception):
    """A run stopped without an answer.

    The loop fills in `usage` with the run's totals so far. The runtime fills in `session_id`
    before the caller sees the error.

    Args:
        message: What went wrong, in one sentence.
        usage: Tokens spent before the failure.
        partial_text: The text of the last assistant reply, if any.
    """

    def __init__(
        self, message: str, *, usage: TokenUsage | None = None, partial_text: str = ""
    ) -> None:
        super().__init__(message)
        self.usage = usage if usage is not None else TokenUsage()
        self.partial_text = partial_text
        self.session_id = ""


class StopReasonError(RunError):
    """The model stopped for a reason the loop does not continue on, such as `max_tokens`."""

    def __init__(
        self, stop_reason: str, *, usage: TokenUsage | None = None, partial_text: str = ""
    ) -> None:
        super().__init__(
            f"the model stopped with '{stop_reason}'", usage=usage, partial_text=partial_text
        )
        self.stop_reason = stop_reason


class InvalidAnswerError(RunError):
    """The model ended its turn with text that is not a valid answer."""


class ApiCallError(RunError):
    """The SDK raised, after its own retries. `status_code` is `None` for a connection error."""

    def __init__(
        self, message: str, *, status_code: int | None, usage: TokenUsage | None = None
    ) -> None:
        super().__init__(message, usage=usage)
        self.status_code = status_code
```

- [ ] **Step 6: Write the interfaces and the events**

Create `src/weather_agents/agent_loop/interfaces.py`:

```python
"""The two seams the loop depends on: one model call, and the tools it may use."""

from dataclasses import dataclass
from typing import Protocol

from anthropic.types import Message, MessageParam
from pydantic import BaseModel, ConfigDict

__all__ = ["ModelCaller", "ModelRequest", "ToolOutcome", "ToolProvider", "ToolSpec"]


class ToolSpec(BaseModel):
    """A tool as the model sees it. `input_schema` is already strict-compatible."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, object]


class ToolOutcome(BaseModel):
    """A tool's result as text, and whether it is an error the model should read."""

    model_config = ConfigDict(frozen=True)

    content: str
    is_error: bool = False


# A dataclass, not pydantic: the SDK's TypedDicts must pass through unvalidated.
@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Everything one model call sends that changes between calls."""

    system: str
    messages: list[MessageParam]
    tools: list[ToolSpec]


class ModelCaller(Protocol):
    """Sends one request and returns the model's final message."""

    async def call(self, request: ModelRequest) -> Message:
        """Raises:
        ApiCallError: The call failed.
        """
        ...


class ToolProvider(Protocol):
    """Lists the tools the model may call and runs them by name."""

    async def list_tools(self) -> list[ToolSpec]:
        """Return every tool, with strict schemas."""
        ...

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Run one tool. A failure is an error outcome, not an exception."""
        ...
```

Create `src/weather_agents/agent_loop/events.py`:

```python
"""Events the loop yields while it runs. A non-streamed run reads them and keeps the last."""

from dataclasses import dataclass

from anthropic.types import MessageParam

from weather_agents.agent_loop.result import RunResult, TokenUsage

__all__ = ["Event", "ModelTurn", "RunFinished", "ToolCallFinished", "ToolCallStarted"]


# Dataclasses, not pydantic: `RunFinished.messages` holds the SDK's TypedDicts unvalidated.
@dataclass(frozen=True, slots=True)
class ModelTurn:
    """One model call came back. `usage` is the run's running total."""

    step: int
    stop_reason: str | None
    usage: TokenUsage
    tool_uses: list[str]


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    """A tool call the model asked for is about to run."""

    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCallFinished:
    """A tool call returned."""

    id: str
    name: str
    is_error: bool
    content: str


@dataclass(frozen=True, slots=True)
class RunFinished:
    """The run's last event. `messages` is the whole conversation, the answer included."""

    result: RunResult
    messages: list[MessageParam]


Event = ModelTurn | ToolCallStarted | ToolCallFinished | RunFinished
```

- [ ] **Step 7: Write the ledger and the truncation helper**

Create `src/weather_agents/agent_loop/ledger.py`:

```python
"""The sources a session touched, so the answer can only cite those."""

import json

__all__ = ["SourceLedger"]


class SourceLedger:
    """Tool calls and URLs one session touched, kept for as long as the session lives."""

    def __init__(self) -> None:
        self._tool_calls: list[tuple[str, object]] = []
        self._urls: set[str] = set()

    def record_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """Remember a tool call by its prefixed name and its arguments."""
        self._tool_calls.append((name, arguments))

    def has_tool_call(self, name: str, arguments_json: str) -> bool:
        """Whether a call with this name and these arguments was made. Key order is ignored."""
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError:
            return False
        return any(
            recorded == name and recorded_arguments == arguments
            for recorded, recorded_arguments in self._tool_calls
        )

    def record_url(self, url: str) -> None:
        """Remember a URL a tool searched or fetched."""
        self._urls.add(url)

    def has_url(self, url: str) -> bool:
        """Whether this URL was recorded."""
        return url in self._urls
```

Create `src/weather_agents/agent_loop/truncate.py`:

```python
"""Cuts logged values to a fixed length so debug logs stay readable."""

import json

__all__ = ["truncate"]


def truncate(value: object, limit: int) -> str:
    """Render `value` as text and cut it to `limit` characters, saying how much was cut.

    Dicts and lists render as JSON. Everything else uses `str`.
    """
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict | list):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [cut {len(text) - limit} chars]"
```

- [ ] **Step 8: Export the package**

Create `src/weather_agents/agent_loop/__init__.py`:

```python
"""The API runtime's agent loop. It depends on a model caller and a tool provider, not on MCP."""

from weather_agents.agent_loop.answer import Answer, Resource, ToolCallResource, UrlResource
from weather_agents.agent_loop.errors import (
    ApiCallError,
    InvalidAnswerError,
    RunError,
    StopReasonError,
)
from weather_agents.agent_loop.events import (
    Event,
    ModelTurn,
    RunFinished,
    ToolCallFinished,
    ToolCallStarted,
)
from weather_agents.agent_loop.interfaces import (
    ModelCaller,
    ModelRequest,
    ToolOutcome,
    ToolProvider,
    ToolSpec,
)
from weather_agents.agent_loop.ledger import SourceLedger
from weather_agents.agent_loop.result import RunResult, TokenUsage

__all__ = [
    "Answer",
    "ApiCallError",
    "Event",
    "InvalidAnswerError",
    "ModelCaller",
    "ModelRequest",
    "ModelTurn",
    "Resource",
    "RunError",
    "RunFinished",
    "RunResult",
    "SourceLedger",
    "StopReasonError",
    "TokenUsage",
    "ToolCallFinished",
    "ToolCallResource",
    "ToolCallStarted",
    "ToolOutcome",
    "ToolProvider",
    "ToolSpec",
    "UrlResource",
]
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop -v`
Expected: 12 passed.

- [ ] **Step 10: Commit**

```bash
git add src/weather_agents/agents src/weather_agents/agent_loop tests/agent_loop
git commit -m "[feature] (weather-agents) Add the agent loop's answer, events, errors, and seams"
```

---

### Task 3: The SDK-backed model caller

**Files:**
- Create: `src/weather_agents/agent_loop/model.py`
- Modify: `src/weather_agents/agent_loop/__init__.py` (export `AnthropicModelCaller`)
- Modify: `tests/agent_loop/fakes.py` (message builders)
- Test: `tests/agent_loop/test_model.py`

**Interfaces:**
- Consumes: `Settings` (Task 1), `Answer`, `ApiCallError`, `ModelRequest`, `ToolSpec` (Task 2).
- Produces:
  - `ANSWER_SCHEMA: dict[str, Any]`, which is `anthropic.transform_schema(Answer)`.
  - `FAST_MODE_BETA = "fast-mode-2026-02-01"`.
  - `AnthropicModelCaller(client: AsyncAnthropic, settings: Settings)` with `async call(request: ModelRequest) -> Message`.
  - In `tests/agent_loop/fakes.py`: `usage(input_tokens=10, output_tokens=5) -> Usage`, `text(value) -> TextBlock`, `tool_use(block_id, name, arguments) -> ToolUseBlock`, `thinking(value, signature="sig") -> ThinkingBlock`, `reply(*content, stop_reason="end_turn") -> Message`, `answer_reply(answer="Sunny and 21 °C.", resources=None) -> Message`, `content_of(message: MessageParam) -> list[dict[str, object]]`, and the constants `FORECAST = "open-meteo__forecast"`, `BERLIN = {"latitude": 52.52, "longitude": 13.41}`.

- [ ] **Step 1: Add the message builders to the fakes**

Replace `tests/agent_loop/fakes.py` with:

```python
"""Fakes and builders for the agent loop and runtime tests."""

import json
from typing import cast

from anthropic.types import (
    ContentBlock,
    Message,
    MessageParam,
    StopReason,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)

from weather_agents.settings import Settings

FORECAST = "open-meteo__forecast"
BERLIN: dict[str, object] = {"latitude": 52.52, "longitude": 13.41}


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore `.env` and carry a dummy API key."""
    return Settings(_env_file=None, anthropic_api_key="test-key", **overrides)


def usage(input_tokens: int = 10, output_tokens: int = 5) -> Usage:
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def text(value: str) -> TextBlock:
    return TextBlock(type="text", text=value)


def tool_use(block_id: str, name: str, arguments: dict[str, object]) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=block_id, name=name, input=arguments)


def thinking(value: str, signature: str = "sig") -> ThinkingBlock:
    return ThinkingBlock(type="thinking", thinking=value, signature=signature)


def reply(*content: ContentBlock, stop_reason: StopReason = "end_turn") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-haiku-5-5",
        content=list(content),
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=usage(),
    )


def answer_reply(
    answer: str = "Sunny and 21 °C.", resources: list[dict[str, str]] | None = None
) -> Message:
    return reply(text(json.dumps({"answer": answer, "resources": resources or []})))


def content_of(message: MessageParam) -> list[dict[str, object]]:
    """A message's content blocks as plain dicts, for assertions."""
    return cast(list[dict[str, object]], message["content"])
```

- [ ] **Step 2: Write the failing caller tests**

Create `tests/agent_loop/test_model.py`:

```python
from typing import cast

import anthropic
import httpx2
import pytest
from anthropic import AsyncAnthropic, omit

from tests.agent_loop.fakes import FORECAST, answer_reply, make_settings
from weather_agents.agent_loop import ApiCallError, ModelRequest, ToolSpec
from weather_agents.agent_loop.model import ANSWER_SCHEMA, FAST_MODE_BETA, AnthropicModelCaller

pytestmark = pytest.mark.anyio

SCHEMA: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}
REQUEST = ModelRequest(
    system="Be brief.",
    messages=[{"role": "user", "content": "Weather in Berlin?"}],
    tools=[ToolSpec(name=FORECAST, description="Forecast", input_schema=SCHEMA)],
)
API_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeStream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def get_final_message(self):
        return self.message


class FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeStream(self.outcome)


class FakeSdkClient:
    def __init__(self, outcome):
        self.messages = FakeMessages(outcome)


def caller_over(client: FakeSdkClient, **overrides: object) -> AnthropicModelCaller:
    return AnthropicModelCaller(cast(AsyncAnthropic, client), make_settings(**overrides))


async def test_the_request_carries_strict_tools_the_answer_schema_effort_and_thinking():
    client = FakeSdkClient(answer_reply())
    message = await caller_over(client).call(REQUEST)
    assert message.stop_reason == "end_turn"
    (kwargs,) = client.messages.calls
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["max_tokens"] == 32_000
    assert kwargs["system"] == "Be brief."
    assert kwargs["messages"] == REQUEST.messages
    assert kwargs["tools"] == [
        {"name": FORECAST, "description": "Forecast", "input_schema": SCHEMA, "strict": True}
    ]
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
    }
    assert kwargs["speed"] is omit
    assert kwargs["extra_headers"] is None
    assert "output_format" not in kwargs


async def test_no_tools_sends_no_tools_field():
    client = FakeSdkClient(answer_reply())
    await caller_over(client).call(ModelRequest(system="s", messages=REQUEST.messages, tools=[]))
    assert client.messages.calls[0]["tools"] is omit


async def test_thinking_off_and_fast_mode_on_change_the_request():
    client = FakeSdkClient(answer_reply())
    await caller_over(client, thinking=False, fast_mode=True, effort="high").call(REQUEST)
    (kwargs,) = client.messages.calls
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["speed"] == "fast"
    assert kwargs["extra_headers"] == {"anthropic-beta": FAST_MODE_BETA}
    assert kwargs["output_config"]["effort"] == "high"


async def test_an_api_status_error_becomes_an_api_call_error():
    error = anthropic.BadRequestError(
        "fast mode is not supported",
        response=httpx2.Response(400, request=API_REQUEST),
        body=None,
    )
    with pytest.raises(ApiCallError, match="400") as caught:
        await caller_over(FakeSdkClient(error)).call(REQUEST)
    assert caught.value.status_code == 400
    assert caught.value.__cause__ is error


async def test_a_connection_error_becomes_an_api_call_error_without_a_status():
    error = anthropic.APIConnectionError(request=API_REQUEST)
    with pytest.raises(ApiCallError, match="Connection error") as caught:
        await caller_over(FakeSdkClient(error)).call(REQUEST)
    assert caught.value.status_code is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'weather_agents.agent_loop.model'`.

- [ ] **Step 4: Write the caller**

Create `src/weather_agents/agent_loop/model.py`:

```python
"""The model caller backed by the Anthropic SDK."""

import anthropic
from anthropic import AsyncAnthropic, omit
from anthropic.types import Message, OutputConfigParam, ThinkingConfigParam, ToolParam

from weather_agents.agent_loop.answer import Answer
from weather_agents.agent_loop.errors import ApiCallError
from weather_agents.agent_loop.interfaces import ModelRequest
from weather_agents.settings import Settings

__all__ = ["ANSWER_SCHEMA", "FAST_MODE_BETA", "AnthropicModelCaller"]

ANSWER_SCHEMA = anthropic.transform_schema(Answer)
FAST_MODE_BETA = "fast-mode-2026-02-01"


class AnthropicModelCaller:
    """Sends one request to the Messages API and returns the assembled final message.

    It always streams, so a long request never trips the SDK's limit on non-streamed calls.
    The answer schema goes in `output_config`, never `output_format`: with `output_format` the
    SDK parses every text block as the stream ends, and raises on a tool-use preamble or on a
    reply cut off at `max_tokens` before the loop can see the stop reason.

    Args:
        client: The SDK client. It keeps its own retries.
        settings: The model, effort, thinking, token limit, and fast mode for every call.
    """

    def __init__(self, client: AsyncAnthropic, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def call(self, request: ModelRequest) -> Message:
        """Send one request and return the model's final message.

        Raises:
            ApiCallError: The SDK raised, after its own retries.
        """
        settings = self._settings
        tools: list[ToolParam] = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "strict": True,
            }
            for spec in request.tools
        ]
        thinking: ThinkingConfigParam = (
            {"type": "adaptive"} if settings.thinking else {"type": "disabled"}
        )
        output_config: OutputConfigParam = {
            "effort": settings.effort,
            "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
        }
        try:
            async with self._client.messages.stream(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=request.system,
                messages=request.messages,
                tools=tools or omit,
                thinking=thinking,
                output_config=output_config,
                speed="fast" if settings.fast_mode else omit,
                extra_headers={"anthropic-beta": FAST_MODE_BETA} if settings.fast_mode else None,
            ) as stream:
                return await stream.get_final_message()
        except anthropic.APIStatusError as error:
            raise ApiCallError(
                f"the API returned {error.status_code}: {error.message}",
                status_code=error.status_code,
            ) from error
        except anthropic.APIError as error:
            raise ApiCallError(f"the API call failed: {error.message}", status_code=None) from error
```

In `src/weather_agents/agent_loop/__init__.py`, add `from weather_agents.agent_loop.model import AnthropicModelCaller` with the other imports and `"AnthropicModelCaller"` to `__all__` in sorted position.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop -v`
Expected: 17 passed.

- [ ] **Step 6: Commit**

```bash
git add src/weather_agents/agent_loop tests/agent_loop
git commit -m "[feature] (weather-agents) Add the SDK-backed model caller with strict tools and the answer schema"
```

---

### Task 4: The agent loop

**Files:**
- Create: `src/weather_agents/agent_loop/loop.py`
- Modify: `src/weather_agents/agent_loop/__init__.py` (export `run_agent`)
- Modify: `tests/agent_loop/fakes.py` (append `FakeModelCaller`, `FakeToolProvider`)
- Test: `tests/agent_loop/test_loop.py`

**Interfaces:**
- Consumes: everything from Task 2, `Settings` (Task 1), the builders in `tests/agent_loop/fakes.py` (Task 3).
- Produces:
  - `run_agent(*, caller: ModelCaller, tools: ToolProvider, tool_specs: list[ToolSpec], agent: AgentDefinition, settings: Settings, history: list[MessageParam], question: str, ledger: SourceLedger) -> AsyncIterator[Event]`. It ends with one `RunFinished`, or raises a `RunError` whose `session_id` is `""`.
  - Log events, all through `get_logger("weather_agents.agent_loop.loop")`: `model call` (debug: `step`, `input`), `model replied` (debug: `step`, `stop_reason`, `output`, `tool_uses`, `tokens`, `elapsed_s`), `tool call` (debug: `tool`, `arguments`), `tool result` (debug: `tool`, `result`, `is_error`), `run finished` (info: `tokens`, `elapsed_s`, `turns`, `tool_calls`), `resource dropped` (warning: `resource`, `reason`). Task 7 tests these names and fields.
  - In `tests/agent_loop/fakes.py`: `FakeModelCaller(*replies: Message | Exception)` with `.requests: list[ModelRequest]`, and `FakeToolProvider(outcomes: dict[str, ToolOutcome | Exception] | None = None, *, barrier: int = 0)` with `.calls: list[tuple[str, dict[str, object]]]`.

- [ ] **Step 1: Append the fakes**

Append to `tests/agent_loop/fakes.py` (add `import asyncio` to the stdlib imports and `from weather_agents.agent_loop import ModelRequest, ToolOutcome, ToolSpec` to the local imports):

```python
class FakeModelCaller:
    """Returns scripted replies in order, or raises the scripted exception, and records requests."""

    def __init__(self, *replies: Message | Exception) -> None:
        self._replies = list(replies)
        self.requests: list[ModelRequest] = []

    async def call(self, request: ModelRequest) -> Message:
        self.requests.append(request)
        next_reply = self._replies.pop(0)
        if isinstance(next_reply, Exception):
            raise next_reply
        return next_reply


class FakeToolProvider:
    """Returns scripted outcomes by tool name.

    With `barrier=n`, each call waits until n calls are in flight at once, and gives up after two
    seconds. Calls made one after another never get there, so they time out.
    """

    def __init__(
        self, outcomes: dict[str, ToolOutcome | Exception] | None = None, *, barrier: int = 0
    ) -> None:
        self.outcomes = outcomes or {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._barrier = barrier
        self._arrived = 0
        self._all_arrived = asyncio.Event()

    async def list_tools(self) -> list[ToolSpec]:
        schema: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}
        return [ToolSpec(name=name, description=name, input_schema=schema) for name in self.outcomes]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        self.calls.append((name, arguments))
        if self._barrier:
            self._arrived += 1
            if self._arrived >= self._barrier:
                self._all_arrived.set()
            await asyncio.wait_for(self._all_arrived.wait(), timeout=2)
        outcome = self.outcomes.get(name, ToolOutcome(content=f"{name} ok"))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
```

- [ ] **Step 2: Write the failing loop tests**

Create `tests/agent_loop/test_loop.py`:

```python
import pytest

from tests.agent_loop.fakes import (
    BERLIN,
    FORECAST,
    FakeModelCaller,
    FakeToolProvider,
    answer_reply,
    content_of,
    make_settings,
    reply,
    text,
    thinking,
    tool_use,
)
from weather_agents.agent_loop import (
    ApiCallError,
    InvalidAnswerError,
    RunFinished,
    SourceLedger,
    StopReasonError,
    ToolCallFinished,
    ToolOutcome,
)
from weather_agents.agent_loop.loop import run_agent
from weather_agents.agents import WEATHER_AGENT

pytestmark = pytest.mark.anyio

QUESTION = "Weather in Berlin?"


async def run(caller, tools=None, *, history=None, ledger=None):
    tools = tools if tools is not None else FakeToolProvider()
    events = []
    async for event in run_agent(
        caller=caller,
        tools=tools,
        tool_specs=await tools.list_tools(),
        agent=WEATHER_AGENT,
        settings=make_settings(),
        history=history if history is not None else [],
        question=QUESTION,
        ledger=ledger if ledger is not None else SourceLedger(),
    ):
        events.append(event)
    return events


async def test_an_end_turn_reply_finishes_the_run_with_its_answer():
    caller = FakeModelCaller(answer_reply("Sunny."))
    events = await run(caller)
    finished = events[-1]
    assert isinstance(finished, RunFinished)
    assert finished.result.answer.answer == "Sunny."
    assert (finished.result.turns, finished.result.tool_calls) == (1, 0)
    assert finished.result.usage.input == 10
    assert caller.requests[0].system == WEATHER_AGENT.system_prompt
    assert caller.requests[0].messages == [{"role": "user", "content": QUESTION}]
    assert [m["role"] for m in finished.messages] == ["user", "assistant"]


async def test_tool_calls_from_one_turn_run_at_once_and_return_in_one_message():
    marine, flood = "open-meteo__marine", "open-meteo__flood"
    tools = FakeToolProvider(
        {
            FORECAST: ToolOutcome(content="21 °C"),
            marine: ToolOutcome(content="calm"),
            flood: ToolOutcome(content="low"),
        },
        barrier=3,
    )
    caller = FakeModelCaller(
        reply(
            tool_use("t1", FORECAST, BERLIN),
            tool_use("t2", marine, BERLIN),
            tool_use("t3", flood, BERLIN),
            stop_reason="tool_use",
        ),
        answer_reply(),
    )
    events = await run(caller, tools)
    results = content_of(caller.requests[1].messages[-1])
    assert [r["tool_use_id"] for r in results] == ["t1", "t2", "t3"]
    assert [r["content"] for r in results] == ["21 °C", "calm", "low"]
    assert [r["is_error"] for r in results] == [False, False, False]
    assert [type(e).__name__ for e in events] == [
        "ModelTurn",
        "ToolCallStarted",
        "ToolCallStarted",
        "ToolCallStarted",
        "ToolCallFinished",
        "ToolCallFinished",
        "ToolCallFinished",
        "ModelTurn",
        "RunFinished",
    ]
    assert (events[-1].result.turns, events[-1].result.tool_calls) == (2, 3)


async def test_pause_turn_calls_again_with_nothing_added():
    caller = FakeModelCaller(reply(text("Searching"), stop_reason="pause_turn"), answer_reply())
    events = await run(caller)
    assert len(caller.requests) == 2
    assert caller.requests[1].messages[-1]["role"] == "assistant"
    assert isinstance(events[-1], RunFinished)


@pytest.mark.parametrize(
    "stop_reason", ["max_tokens", "stop_sequence", "refusal", "model_context_window_exceeded"]
)
async def test_a_stop_reason_the_loop_cannot_continue_on_raises(stop_reason):
    caller = FakeModelCaller(reply(text('{"answer": "Sun'), stop_reason=stop_reason))
    with pytest.raises(StopReasonError) as caught:
        await run(caller)
    assert caught.value.stop_reason == stop_reason
    assert caught.value.partial_text == '{"answer": "Sun'
    assert caught.value.usage.input == 10
    assert caught.value.session_id == ""


async def test_thinking_and_tool_use_blocks_go_back_unchanged():
    caller = FakeModelCaller(
        reply(
            thinking("Need the forecast.", "sig-1"),
            tool_use("t1", FORECAST, BERLIN),
            stop_reason="tool_use",
        ),
        answer_reply(),
    )
    await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assistant = content_of(caller.requests[1].messages[1])
    assert assistant[0] == {"type": "thinking", "thinking": "Need the forecast.", "signature": "sig-1"}
    assert assistant[1] == {"type": "tool_use", "id": "t1", "name": FORECAST, "input": BERLIN}


async def test_a_final_reply_that_is_not_an_answer_raises():
    caller = FakeModelCaller(reply(text("It is sunny.")))
    with pytest.raises(InvalidAnswerError) as caught:
        await run(caller)
    assert caught.value.partial_text == "It is sunny."


async def test_resources_the_session_never_touched_are_dropped():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        answer_reply(
            resources=[
                {
                    "kind": "tool_call",
                    "tool": FORECAST,
                    "arguments": '{"longitude": 13.41, "latitude": 52.52}',
                    "title": "Forecast",
                },
                {
                    "kind": "tool_call",
                    "tool": FORECAST,
                    "arguments": '{"latitude": 0, "longitude": 0}',
                    "title": "Invented call",
                },
                {"kind": "url", "url": "https://example.com", "title": "Invented page"},
            ]
        ),
    )
    events = await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assert [r.title for r in events[-1].result.answer.resources] == ["Forecast"]


async def test_a_resource_from_earlier_in_the_session_is_kept():
    ledger = SourceLedger()
    ledger.record_tool_call(FORECAST, BERLIN)
    resource = {
        "kind": "tool_call",
        "tool": FORECAST,
        "arguments": '{"latitude": 52.52, "longitude": 13.41}',
        "title": "Earlier forecast",
    }
    events = await run(FakeModelCaller(answer_reply(resources=[resource])), ledger=ledger)
    assert [r.title for r in events[-1].result.answer.resources] == ["Earlier forecast"]


async def test_a_tool_that_raises_becomes_an_error_result():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply()
    )
    events = await run(caller, FakeToolProvider({FORECAST: RuntimeError("boom")}))
    (finished,) = [e for e in events if isinstance(e, ToolCallFinished)]
    assert finished.is_error
    assert "RuntimeError: boom" in finished.content
    assert content_of(caller.requests[1].messages[-1])[0]["is_error"] is True


async def test_the_history_passed_in_is_not_changed():
    history = [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]
    snapshot = list(history)
    events = await run(FakeModelCaller(answer_reply()), history=history)
    assert history == snapshot
    assert [m["role"] for m in events[-1].messages] == ["user", "assistant", "user", "assistant"]


async def test_an_api_error_carries_the_usage_so_far():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        ApiCallError("the API returned 529: overloaded", status_code=529),
    )
    with pytest.raises(ApiCallError) as caught:
        await run(caller, FakeToolProvider({FORECAST: ToolOutcome(content="21")}))
    assert caught.value.usage.input == 10
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop/test_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'weather_agents.agent_loop.loop'`.

- [ ] **Step 4: Write the loop**

Create `src/weather_agents/agent_loop/loop.py`:

```python
"""The agent loop: call the model, run the tools it asks for, and repeat until it answers."""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import cast

from anthropic.types import (
    ContentBlock,
    ContentBlockParam,
    Message,
    MessageParam,
    TextBlock,
    ToolUseBlock,
)
from labs_logging import get_logger
from pydantic import ValidationError

from weather_agents.agent_loop.answer import Answer, Resource, ToolCallResource
from weather_agents.agent_loop.errors import InvalidAnswerError, RunError, StopReasonError
from weather_agents.agent_loop.events import (
    Event,
    ModelTurn,
    RunFinished,
    ToolCallFinished,
    ToolCallStarted,
)
from weather_agents.agent_loop.interfaces import (
    ModelCaller,
    ModelRequest,
    ToolOutcome,
    ToolProvider,
    ToolSpec,
)
from weather_agents.agent_loop.ledger import SourceLedger
from weather_agents.agent_loop.result import RunResult, TokenUsage
from weather_agents.agent_loop.truncate import truncate
from weather_agents.agents import AgentDefinition
from weather_agents.settings import Settings

__all__ = ["run_agent"]

log = get_logger(__name__)


async def run_agent(
    *,
    caller: ModelCaller,
    tools: ToolProvider,
    tool_specs: list[ToolSpec],
    agent: AgentDefinition,
    settings: Settings,
    history: list[MessageParam],
    question: str,
    ledger: SourceLedger,
) -> AsyncIterator[Event]:
    """Answer one question on top of `history`, yielding events as the run goes.

    The run continues on `tool_use` and `pause_turn`, finishes on `end_turn` with one
    `RunFinished`, and raises on every other stop reason. `history` is copied, never changed.

    Args:
        caller: Sends each model request.
        tools: Runs the tools the model asks for.
        tool_specs: The tools offered to the model, listed once by the caller.
        agent: Supplies the system prompt.
        settings: Supplies the debug log truncation length.
        history: The session's earlier messages.
        question: The new user message.
        ledger: The session's touched sources. Every tool call is recorded in it.

    Raises:
        StopReasonError: The model stopped for a reason the loop does not continue on.
        InvalidAnswerError: The final reply is not a valid `Answer`.
        ApiCallError: A model call failed.
    """
    limit = settings.log_truncate
    messages: list[MessageParam] = [*history, {"role": "user", "content": question}]
    added: list[MessageParam] = [messages[-1]]
    usage = TokenUsage()
    tool_calls = 0
    started = time.monotonic()
    step = 0
    while True:
        step += 1
        log.debug("model call", step=step, input=truncate(added, limit))
        request = ModelRequest(system=agent.system_prompt, messages=list(messages), tools=tool_specs)
        try:
            message = await caller.call(request)
        except RunError as error:
            error.usage = usage
            raise
        usage = usage.add(message.usage)
        messages.append({"role": "assistant", "content": [_as_param(b) for b in message.content]})
        tool_uses = [block for block in message.content if isinstance(block, ToolUseBlock)]
        names = [block.name for block in tool_uses]
        log.debug(
            "model replied",
            step=step,
            stop_reason=message.stop_reason,
            output=truncate(_text_of(message), limit),
            tool_uses=names,
            tokens=usage.model_dump(),
            elapsed_s=_elapsed(started),
        )
        yield ModelTurn(step=step, stop_reason=message.stop_reason, usage=usage, tool_uses=names)

        if message.stop_reason == "tool_use":
            for block in tool_uses:
                yield ToolCallStarted(id=block.id, name=block.name, arguments=block.input)
            outcomes = await _run_tools(tools, tool_uses, ledger, limit)
            tool_calls += len(tool_uses)
            results: list[ContentBlockParam] = []
            for block, outcome in zip(tool_uses, outcomes, strict=True):
                yield ToolCallFinished(
                    id=block.id, name=block.name, is_error=outcome.is_error, content=outcome.content
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": outcome.content,
                        "is_error": outcome.is_error,
                    }
                )
            messages.append({"role": "user", "content": results})
            added = [messages[-1]]
        elif message.stop_reason == "pause_turn":
            added = []
        elif message.stop_reason == "end_turn":
            answer = _drop_untouched(_parse_answer(message, usage), ledger)
            result = RunResult(
                answer=answer, session_id="", usage=usage, turns=step, tool_calls=tool_calls
            )
            log.info(
                "run finished",
                tokens=usage.model_dump(),
                elapsed_s=_elapsed(started),
                turns=step,
                tool_calls=tool_calls,
            )
            yield RunFinished(result=result, messages=messages)
            return
        else:
            raise StopReasonError(
                str(message.stop_reason), usage=usage, partial_text=_text_of(message)
            )


async def _run_tools(
    tools: ToolProvider, blocks: list[ToolUseBlock], ledger: SourceLedger, limit: int
) -> list[ToolOutcome]:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(_run_tool(tools, block, ledger, limit)) for block in blocks]
    return [task.result() for task in tasks]


async def _run_tool(
    tools: ToolProvider, block: ToolUseBlock, ledger: SourceLedger, limit: int
) -> ToolOutcome:
    ledger.record_tool_call(block.name, block.input)
    log.debug("tool call", tool=block.name, arguments=truncate(block.input, limit))
    try:
        outcome = await tools.call(block.name, block.input)
    # Any exception: one failing call must not cancel its siblings in the task group.
    except Exception as error:
        outcome = ToolOutcome(content=f"the tool raised {type(error).__name__}: {error}", is_error=True)
    log.debug(
        "tool result",
        tool=block.name,
        result=truncate(outcome.content, limit),
        is_error=outcome.is_error,
    )
    return outcome


def _parse_answer(message: Message, usage: TokenUsage) -> Answer:
    text = _text_of(message)
    try:
        return Answer.model_validate_json(text)
    except ValidationError as error:
        raise InvalidAnswerError(
            f"the final reply is not a valid answer ({error.error_count()} errors)",
            usage=usage,
            partial_text=text,
        ) from error


def _drop_untouched(answer: Answer, ledger: SourceLedger) -> Answer:
    kept: list[Resource] = []
    for resource in answer.resources:
        if isinstance(resource, ToolCallResource):
            is_touched = ledger.has_tool_call(resource.tool, resource.arguments)
        else:
            is_touched = ledger.has_url(resource.url)
        if is_touched:
            kept.append(resource)
        else:
            log.warning(
                "resource dropped",
                resource=resource.model_dump(),
                reason="the session never touched this source",
            )
    return answer.model_copy(update={"resources": kept})


def _as_param(block: ContentBlock) -> ContentBlockParam:
    return cast(ContentBlockParam, block.model_dump(mode="json", exclude_none=True))


def _text_of(message: Message) -> str:
    return "".join(block.text for block in message.content if isinstance(block, TextBlock))


def _elapsed(started: float) -> float:
    return round(time.monotonic() - started, 2)
```

In `src/weather_agents/agent_loop/__init__.py`, add `from weather_agents.agent_loop.loop import run_agent` and `"run_agent"` to `__all__` in sorted position.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/agent_loop -v`
Expected: 31 passed (14 loop tests, with 4 from the parametrized stop reasons).

- [ ] **Step 6: Commit**

```bash
git add src/weather_agents/agent_loop tests/agent_loop
git commit -m "[feature] (weather-agents) Add the agent loop: concurrent tool calls, stop reasons, and the checked answer"
```

---

### Task 5: MCP tools for the loop

**Files:**
- Create: `src/weather_agents/runtimes/__init__.py`, `src/weather_agents/runtimes/mcp_tools.py`
- Create: `tests/runtimes/__init__.py`, `tests/runtimes/fakes.py`
- Test: `tests/runtimes/test_mcp_tools.py`

**Interfaces:**
- Consumes: `ToolSpec`, `ToolOutcome` (Task 2), `McpClientError` and the pool's `list_all_tools` / `call_namespaced_tool` (built), the `client` fixture in `tests/conftest.py` (an in-memory SDK client over the real server with a fake Open-Meteo).
- Produces:
  - `ToolPool` protocol: `failures: dict[str, McpClientError]`, `async __aenter__() -> ToolPool`, `async __aexit__(exc_type, exc, tb) -> bool | None`, `async list_all_tools() -> list[mcp.types.Tool]`, `async call_namespaced_tool(name: str, arguments: dict[str, object] | None = None) -> CallToolResult`. `McpClientPool` satisfies it.
  - `McpToolProvider(pool: ToolPool)`, a `ToolProvider`.
  - In `tests/runtimes/fakes.py`: `FORECAST_TOOL: Tool` (named `open-meteo__forecast`, with a `minimum` in its schema) and `FakePool(tools=None, *, results=None, failures=None)` with `.calls`, `.entered`, `.exited`.

- [ ] **Step 1: Write the pool fake**

Create `tests/runtimes/__init__.py` as an empty file. Create `tests/runtimes/fakes.py`:

```python
"""A pool stand-in for the runtime tests."""

from mcp.types import CallToolResult, TextContent, Tool

from weather_agents.mcp_client import McpClientError

FORECAST_TOOL = Tool(
    name="open-meteo__forecast",
    description="Forecast for one place.",
    input_schema={
        "type": "object",
        "properties": {"latitude": {"type": "number", "minimum": -90, "maximum": 90}},
        "required": ["latitude"],
    },
)


class FakePool:
    """Serves fixed tools and scripted results, and records calls."""

    def __init__(
        self,
        tools: list[Tool] | None = None,
        *,
        results: dict[str, CallToolResult | Exception] | None = None,
        failures: dict[str, McpClientError] | None = None,
    ) -> None:
        self.tools = tools if tools is not None else [FORECAST_TOOL]
        self.results = results or {}
        self.failures = failures or {}
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> "FakePool":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True

    async def list_all_tools(self) -> list[Tool]:
        return self.tools

    async def call_namespaced_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        self.calls.append((name, arguments))
        result = self.results.get(name, CallToolResult(content=[TextContent(type="text", text="ok")]))
        if isinstance(result, Exception):
            raise result
        return result
```

- [ ] **Step 2: Write the failing tests**

Create `tests/runtimes/test_mcp_tools.py`:

```python
import json

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from tests.runtimes.fakes import FakePool
from weather_agents.mcp_client import McpClientError
from weather_agents.runtimes.mcp_tools import McpToolProvider

pytestmark = pytest.mark.anyio

STRICT_FORBIDDEN = {"minimum", "maximum", "minLength", "maxItems", "pattern"}
PREFIX = "open-meteo__"


class ServerPool:
    """The real server's tools behind the pool's two model-facing methods."""

    def __init__(self, client: Client) -> None:
        self.client = client

    async def list_all_tools(self):
        tools = (await self.client.list_tools()).tools
        return [tool.model_copy(update={"name": f"{PREFIX}{tool.name}"}) for tool in tools]

    async def call_namespaced_tool(self, name, arguments=None):
        return await self.client.call_tool(name.removeprefix(PREFIX), arguments)


def keys_in(node: object) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {key for value in node.values() for key in keys_in(value)}
    if isinstance(node, list):
        return {key for item in node for key in keys_in(item)}
    return set()


def objects_in(node: object) -> list[dict]:
    found = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append(node)
        for value in node.values():
            found.extend(objects_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(objects_in(item))
    return found


async def test_the_real_servers_schemas_come_out_strict(client):
    original = {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}
    specs = await McpToolProvider(ServerPool(client)).list_tools()
    assert len(specs) == 11
    for spec in specs:
        assert not keys_in(spec.input_schema) & STRICT_FORBIDDEN, spec.name
        assert all(o["additionalProperties"] is False for o in objects_in(spec.input_schema)), spec.name
        assert spec.input_schema.get("required") == original[spec.name.removeprefix(PREFIX)].get(
            "required"
        )
    forecast = next(spec for spec in specs if spec.name == f"{PREFIX}forecast")
    assert "minimum" in forecast.input_schema["properties"]["latitude"]["description"]


async def test_an_out_of_range_argument_still_comes_back_as_a_server_error(client):
    outcome = await McpToolProvider(ServerPool(client)).call(
        f"{PREFIX}forecast", {"latitude": 95, "longitude": 0}
    )
    assert outcome.is_error
    assert "latitude" in outcome.content


async def test_text_blocks_are_joined_with_newlines():
    result = CallToolResult(
        content=[TextContent(type="text", text="a"), TextContent(type="text", text="b")]
    )
    pool = FakePool(results={f"{PREFIX}forecast": result})
    outcome = await McpToolProvider(pool).call(f"{PREFIX}forecast", {"latitude": 1})
    assert outcome.content == "a\nb"
    assert outcome.is_error is False
    assert pool.calls == [(f"{PREFIX}forecast", {"latitude": 1})]


async def test_structured_content_is_sent_as_json_when_there_is_no_text():
    result = CallToolResult(content=[], structured_content={"temperature": 21})
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": result})).call(
        f"{PREFIX}forecast", {}
    )
    assert json.loads(outcome.content) == {"temperature": 21}


async def test_the_error_flag_is_copied():
    result = CallToolResult(content=[TextContent(type="text", text="bad date")], is_error=True)
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": result})).call(
        f"{PREFIX}forecast", {}
    )
    assert outcome.is_error


async def test_a_client_error_becomes_an_error_result():
    error = McpClientError("open-meteo", "session dropped")
    outcome = await McpToolProvider(FakePool(results={f"{PREFIX}forecast": error})).call(
        f"{PREFIX}forecast", {}
    )
    assert outcome.is_error
    assert outcome.content == "MCP server 'open-meteo': session dropped"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/runtimes -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'weather_agents.runtimes'`.

- [ ] **Step 4: Write the provider**

Create `src/weather_agents/runtimes/mcp_tools.py`:

```python
"""MCP tools as the agent loop's tool provider."""

import json
from types import TracebackType
from typing import Protocol

import anthropic
from mcp.types import CallToolResult, TextContent, Tool

from weather_agents.agent_loop import ToolOutcome, ToolSpec
from weather_agents.mcp_client import McpClientError

__all__ = ["McpToolProvider", "ToolPool"]


class ToolPool(Protocol):
    """The part of `McpClientPool` the API runtime uses."""

    failures: dict[str, McpClientError]

    async def __aenter__(self) -> "ToolPool": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...

    async def list_all_tools(self) -> list[Tool]: ...

    async def call_namespaced_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...


class McpToolProvider:
    """Offers every open server's tools to the model and runs them through the pool.

    Strict mode rejects keywords the Open-Meteo server uses, such as `minimum` and `pattern`.
    `transform_schema` moves them into each property's description, and the server still
    enforces them.

    Args:
        pool: An open pool.
    """

    def __init__(self, pool: ToolPool) -> None:
        self._pool = pool

    async def list_tools(self) -> list[ToolSpec]:
        """Return every open server's tools, named `<server>__<tool>`, with strict schemas.

        Raises:
            McpClientError: Listing failed on an open server.
        """
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=anthropic.transform_schema(tool.input_schema),
            )
            for tool in await self._pool.list_all_tools()
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> ToolOutcome:
        """Run one tool. A client failure becomes an error outcome naming the server."""
        try:
            result = await self._pool.call_namespaced_tool(name, arguments)
        except McpClientError as error:
            return ToolOutcome(content=str(error), is_error=True)
        texts = [block.text for block in result.content if isinstance(block, TextContent)]
        content = "\n".join(texts) if texts else json.dumps(result.structured_content)
        return ToolOutcome(content=content, is_error=result.is_error)
```

Create `src/weather_agents/runtimes/__init__.py`:

```python
"""Agent runtimes behind one interface. The CLI depends on the interface only."""

from weather_agents.runtimes.mcp_tools import McpToolProvider, ToolPool

__all__ = ["McpToolProvider", "ToolPool"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/runtimes -v`
Expected: 6 passed. If the out-of-range test fails because the server's error text names the field differently, print `outcome.content` and assert on the field name it uses. The point of the test is that the server, not strict mode, rejects the value.

- [ ] **Step 6: Commit**

```bash
git add src/weather_agents/runtimes tests/runtimes
git commit -m "[feature] (weather-agents) Offer MCP tools to the agent loop with strict schemas"
```

---

### Task 6: The API runtime and its sessions

**Files:**
- Create: `src/weather_agents/runtimes/base.py`, `src/weather_agents/runtimes/api.py`
- Modify: `src/weather_agents/runtimes/__init__.py` (exports)
- Test: `tests/runtimes/test_api_runtime.py`

**Interfaces:**
- Consumes: `run_agent`, `AnthropicModelCaller`, `RunError`, `StopReasonError`, `RunFinished`, `RunResult`, `SourceLedger`, `ToolSpec`, `ModelCaller` (Tasks 2 to 4), `ToolPool`, `McpToolProvider` (Task 5), `Settings` (Task 1), `WEATHER_AGENT`, `AgentDefinition` (Task 2), `McpClientPool` (built), the fakes from Tasks 3 to 5.
- Produces:
  - `SessionNotFoundError(session_id: str)` with `.session_id`, message `no session '<id>'`.
  - `AgentRuntime` protocol: `async __aenter__() -> Self`, `async __aexit__(...) -> None`, `async send(question: str, session_id: str | None = None) -> RunResult`, `async clear(session_id: str) -> None`, `async close() -> None`.
  - `Session()` with `.id: str` (32 hex characters), `.messages: list[MessageParam]`, `.ledger: SourceLedger`.
  - `ApiRuntime(settings: Settings, *, model_caller: ModelCaller | None = None, pool: ToolPool | None = None, agent: AgentDefinition = WEATHER_AGENT)`.
  - Log events: `MCP server failed to open` (warning: `server`, `reason`), `run failed` (error: `error`, `stop_reason`, `tokens`). Every line logged during `send` carries `session_id` through `bound_context`.

- [ ] **Step 1: Write the failing runtime tests**

Create `tests/runtimes/test_api_runtime.py`:

```python
import pytest
from mcp.types import CallToolResult, TextContent

from tests.agent_loop.fakes import (
    BERLIN,
    FORECAST,
    FakeModelCaller,
    answer_reply,
    make_settings,
    reply,
    text,
    tool_use,
)
from tests.runtimes.fakes import FakePool
from weather_agents.agent_loop import StopReasonError
from weather_agents.mcp_client import McpClientError
from weather_agents.runtimes import ApiRuntime, SessionNotFoundError

pytestmark = pytest.mark.anyio


def runtime(caller, pool=None) -> ApiRuntime:
    return ApiRuntime(make_settings(), model_caller=caller, pool=pool if pool is not None else FakePool())


async def test_a_question_without_a_session_id_starts_a_session():
    caller = FakeModelCaller(answer_reply("Sunny."))
    async with runtime(caller) as rt:
        result = await rt.send("Weather in Berlin?")
    assert result.answer.answer == "Sunny."
    assert len(result.session_id) == 32
    (tool,) = caller.requests[0].tools
    assert tool.name == FORECAST
    assert "minimum" not in tool.input_schema["properties"]["latitude"]
    assert tool.input_schema["additionalProperties"] is False


async def test_a_follow_up_sends_the_earlier_conversation():
    caller = FakeModelCaller(answer_reply("Sunny."), answer_reply("Rain."))
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        second = await rt.send("And tomorrow?", first.session_id)
    assert second.session_id == first.session_id
    messages = caller.requests[1].messages
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "Weather in Berlin?"
    assert messages[2]["content"] == "And tomorrow?"


async def test_two_sessions_do_not_share_history():
    caller = FakeModelCaller(answer_reply(), answer_reply())
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        second = await rt.send("Weather in Paris?")
    assert second.session_id != first.session_id
    assert caller.requests[1].messages == [{"role": "user", "content": "Weather in Paris?"}]


async def test_an_unknown_session_id_fails_before_any_model_call():
    caller = FakeModelCaller()
    async with runtime(caller) as rt:
        with pytest.raises(SessionNotFoundError, match="nope") as caught:
            await rt.send("Hi", "nope")
    assert caught.value.session_id == "nope"
    assert caller.requests == []


async def test_a_failed_request_leaves_the_question_and_the_error_in_the_session():
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"),
        reply(text("I can't"), stop_reason="refusal"),
        answer_reply("Sorry about that."),
    )
    async with runtime(caller) as rt:
        with pytest.raises(StopReasonError) as caught:
            await rt.send("Weather in Berlin?")
        assert len(caught.value.session_id) == 32
        await rt.send("Try again?", caught.value.session_id)
    assert caller.requests[2].messages == [
        {"role": "user", "content": "Weather in Berlin?"},
        {"role": "assistant", "content": "The previous request failed: the model stopped with 'refusal'"},
        {"role": "user", "content": "Try again?"},
    ]


async def test_a_tool_call_reaches_the_pool_by_its_prefixed_name():
    pool = FakePool(results={FORECAST: CallToolResult(content=[TextContent(type="text", text="21")])})
    caller = FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply()
    )
    async with runtime(caller, pool) as rt:
        result = await rt.send("Weather in Berlin?")
    assert pool.calls == [(FORECAST, BERLIN)]
    assert result.tool_calls == 1


async def test_clear_forgets_the_session():
    caller = FakeModelCaller(answer_reply())
    async with runtime(caller) as rt:
        first = await rt.send("Weather in Berlin?")
        await rt.clear(first.session_id)
        with pytest.raises(SessionNotFoundError):
            await rt.send("And tomorrow?", first.session_id)
        with pytest.raises(SessionNotFoundError):
            await rt.clear(first.session_id)


async def test_closing_forgets_every_session_and_closes_the_pool():
    pool = FakePool()
    rt = runtime(FakeModelCaller(answer_reply()), pool)
    async with rt:
        first = await rt.send("Weather in Berlin?")
    assert pool.entered and pool.exited
    with pytest.raises(SessionNotFoundError):
        await rt.send("And tomorrow?", first.session_id)


async def test_close_then_exit_closes_the_pool_once():
    pool = FakePool()
    async with runtime(FakeModelCaller(), pool) as rt:
        await rt.close()
    assert pool.exited


async def test_the_agent_runs_without_tools_when_every_server_failed():
    pool = FakePool([], failures={"open-meteo": McpClientError("open-meteo", "spawn failed")})
    caller = FakeModelCaller(answer_reply())
    async with runtime(caller, pool) as rt:
        await rt.send("Weather in Berlin?")
    assert caller.requests[0].tools == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/runtimes/test_api_runtime.py -v`
Expected: FAIL with `ImportError: cannot import name 'ApiRuntime'`.

- [ ] **Step 3: Write the interface**

Create `src/weather_agents/runtimes/base.py`:

```python
"""The interface every agent runtime offers the CLI."""

from types import TracebackType
from typing import Protocol, Self

from weather_agents.agent_loop import RunResult

__all__ = ["AgentRuntime", "SessionNotFoundError"]


class SessionNotFoundError(Exception):
    """A request named a session the runtime does not hold.

    Args:
        session_id: The id that was asked for.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(f"no session '{session_id}'")
        self.session_id = session_id


class AgentRuntime(Protocol):
    """Answers questions in sessions. Open and close it in the same task."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def send(self, question: str, session_id: str | None = None) -> RunResult:
        """Answer a question, in a new session when `session_id` is `None`.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
            RunError: The run stopped without an answer. Its `session_id` is set.
        """
        ...

    async def clear(self, session_id: str) -> None:
        """Forget one session.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
        """
        ...

    async def close(self) -> None:
        """Forget every session and release what the runtime holds."""
        ...
```

- [ ] **Step 4: Write the API runtime**

Create `src/weather_agents/runtimes/api.py`:

```python
"""The API runtime: our own agent loop on the Messages API, with sessions held in memory."""

from types import TracebackType
from typing import Self
from uuid import uuid4

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from labs_logging import bound_context, get_logger

from weather_agents.agent_loop import (
    AnthropicModelCaller,
    ModelCaller,
    RunError,
    RunFinished,
    RunResult,
    SourceLedger,
    StopReasonError,
    ToolSpec,
    run_agent,
)
from weather_agents.agents import WEATHER_AGENT, AgentDefinition
from weather_agents.mcp_client import McpClientPool
from weather_agents.runtimes.base import SessionNotFoundError
from weather_agents.runtimes.mcp_tools import McpToolProvider, ToolPool
from weather_agents.settings import Settings

__all__ = ["ApiRuntime", "Session"]

log = get_logger(__name__)


class Session:
    """One conversation: its messages and the sources it touched. Held in memory only."""

    def __init__(self) -> None:
        self.id = uuid4().hex
        self.messages: list[MessageParam] = []
        self.ledger = SourceLedger()


class ApiRuntime:
    """Answers questions with the hand-written loop, the MCP servers' tools, and sessions.

    Open it with `async with`, in the same task that closes it, because the MCP pool requires
    that. Tools are listed once on open and reused for every request.

    Args:
        settings: The model, the MCP config file, and the log truncation length.
        model_caller: Replaces the SDK-backed caller. Tests pass a fake.
        pool: Replaces the pool built from `settings.mcp_config`. Tests pass a fake.
        agent: Supplies the system prompt.

    Raises:
        ConfigError: The MCP config file is unusable.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        model_caller: ModelCaller | None = None,
        pool: ToolPool | None = None,
        agent: AgentDefinition = WEATHER_AGENT,
    ) -> None:
        self._settings = settings
        self._client: AsyncAnthropic | None = None
        if model_caller is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
            model_caller = AnthropicModelCaller(self._client, settings)
        self._caller = model_caller
        self._pool: ToolPool = pool if pool is not None else McpClientPool.from_file(settings.mcp_config)
        self._tools = McpToolProvider(self._pool)
        self._agent = agent
        self._tool_specs: list[ToolSpec] = []
        self._sessions: dict[str, Session] = {}
        self._is_open = False

    async def __aenter__(self) -> Self:
        await self._pool.__aenter__()
        self._is_open = True
        try:
            for server, error in self._pool.failures.items():
                log.warning("MCP server failed to open", server=server, reason=str(error))
            self._tool_specs = await self._tools.list_tools()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def send(self, question: str, session_id: str | None = None) -> RunResult:
        """Answer a question, in a new session when `session_id` is `None`.

        On a `RunError`, the session keeps the question and records the error as the answer to
        it, and the partial turns are dropped. Any other exception leaves the session unchanged.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
            RunError: The run stopped without an answer. Its `session_id` is set.
        """
        session = self._find(session_id) if session_id is not None else self._start()
        with bound_context(session_id=session.id):
            try:
                finished = await self._run(session, question)
            except RunError as error:
                error.session_id = session.id
                session.messages.extend(
                    [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": f"The previous request failed: {error}"},
                    ]
                )
                log.error(
                    "run failed",
                    error=str(error),
                    stop_reason=error.stop_reason if isinstance(error, StopReasonError) else None,
                    tokens=error.usage.model_dump(),
                )
                raise
        session.messages = finished.messages
        return finished.result.model_copy(update={"session_id": session.id})

    async def clear(self, session_id: str) -> None:
        """Forget one session.

        Raises:
            SessionNotFoundError: `session_id` names no open session.
        """
        if self._sessions.pop(session_id, None) is None:
            raise SessionNotFoundError(session_id)

    async def close(self) -> None:
        """Forget every session, then close the MCP pool and the SDK client. Safe to repeat."""
        self._sessions.clear()
        if self._is_open:
            self._is_open = False
            await self._pool.__aexit__(None, None, None)
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def _run(self, session: Session, question: str) -> RunFinished:
        events = run_agent(
            caller=self._caller,
            tools=self._tools,
            tool_specs=self._tool_specs,
            agent=self._agent,
            settings=self._settings,
            history=session.messages,
            question=question,
            ledger=session.ledger,
        )
        async for event in events:
            if isinstance(event, RunFinished):
                return event
        raise RuntimeError("the agent loop ended without a RunFinished event")

    def _find(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None

    def _start(self) -> Session:
        session = Session()
        self._sessions[session.id] = session
        return session
```

Replace `src/weather_agents/runtimes/__init__.py` with:

```python
"""Agent runtimes behind one interface. The CLI depends on the interface only."""

from weather_agents.runtimes.api import ApiRuntime, Session
from weather_agents.runtimes.base import AgentRuntime, SessionNotFoundError
from weather_agents.runtimes.mcp_tools import McpToolProvider, ToolPool

__all__ = [
    "AgentRuntime",
    "ApiRuntime",
    "McpToolProvider",
    "Session",
    "SessionNotFoundError",
    "ToolPool",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/runtimes -v`
Expected: 16 passed.

- [ ] **Step 6: Commit**

```bash
git add src/weather_agents/runtimes tests/runtimes
git commit -m "[feature] (weather-agents) Add the API runtime with in-memory sessions"
```

---

### Task 7: The logs a run leaves behind

**Files:**
- Test: `tests/runtimes/test_logging.py`
- Modify, only if a test exposes a gap: `src/weather_agents/agent_loop/loop.py`, `src/weather_agents/runtimes/api.py`

**Interfaces:**
- Consumes: the log events listed in Tasks 4 and 6, `labs_logging.configure` and `LoggingConfig`, the fakes from Tasks 3 to 5.
- Produces: nothing new for later tasks.

`labs-logging` writes one JSON object per line under `<log_dir>/<family>/<run>/main.jsonl`. `level` is lowercase, `event` is the message, and every keyword field, plus the fields from `bound_context`, sits under `context`.

- [ ] **Step 1: Write the tests**

Create `tests/runtimes/test_logging.py`:

```python
import json
import logging

import pytest
from labs_logging import LoggingConfig, configure
from mcp.types import CallToolResult, TextContent

from tests.agent_loop.fakes import (
    BERLIN,
    FORECAST,
    FakeModelCaller,
    answer_reply,
    make_settings,
    reply,
    text,
    tool_use,
)
from tests.runtimes.fakes import FakePool
from weather_agents.agent_loop import StopReasonError
from weather_agents.mcp_client import McpClientError
from weather_agents.runtimes import ApiRuntime

pytestmark = pytest.mark.anyio

RUN_EVENTS = {"model call", "model replied", "tool call", "tool result", "run finished"}


@pytest.fixture
def log_lines(tmp_path):
    config = LoggingConfig(
        app="weather-agents-test",
        family="weather_agents",
        level=logging.DEBUG,
        log_dir=tmp_path,
        console=False,
        synchronous=True,
    )
    with configure(config):

        def read():
            paths = sorted(tmp_path.glob("weather_agents/*/main.jsonl"))
            return [json.loads(line) for path in paths for line in path.read_text().splitlines() if line]

        yield read


def named(lines, event):
    return [line for line in lines if line["event"] == event]


def tool_turn_then_answer(**answer):
    return FakeModelCaller(
        reply(tool_use("t1", FORECAST, BERLIN), stop_reason="tool_use"), answer_reply(**answer)
    )


async def test_every_line_of_a_run_names_its_session(log_lines):
    async with ApiRuntime(make_settings(), model_caller=tool_turn_then_answer(), pool=FakePool()) as rt:
        result = await rt.send("Weather in Berlin?")
    run_lines = [line for line in log_lines() if line["event"] in RUN_EVENTS]
    assert len(run_lines) == 7
    assert {line["context"]["session_id"] for line in run_lines} == {result.session_id}


async def test_debug_lines_carry_each_step_cut_to_the_truncation_length(log_lines):
    pool = FakePool(results={FORECAST: CallToolResult(content=[TextContent(type="text", text="x" * 100)])})
    settings = make_settings(log_truncate=20)
    async with ApiRuntime(settings, model_caller=tool_turn_then_answer(), pool=pool) as rt:
        await rt.send("Weather in Berlin, please, as soon as you can?")
    lines = log_lines()
    first_call = named(lines, "model call")[0]
    assert first_call["level"] == "debug"
    assert first_call["context"]["step"] == 1
    assert "[cut " in first_call["context"]["input"]
    replied = named(lines, "model replied")[0]["context"]
    assert replied["stop_reason"] == "tool_use"
    assert replied["tool_uses"] == [FORECAST]
    assert replied["tokens"]["input"] == 10
    assert "elapsed_s" in replied
    tool_call = named(lines, "tool call")[0]["context"]
    assert tool_call["tool"] == FORECAST
    assert tool_call["arguments"].startswith('{"latitude": 52.52')
    tool_result = named(lines, "tool result")[0]["context"]
    assert tool_result["result"] == "x" * 20 + "… [cut 80 chars]"
    assert tool_result["is_error"] is False


async def test_the_end_of_a_run_logs_a_summary_at_info(log_lines):
    async with ApiRuntime(make_settings(), model_caller=tool_turn_then_answer(), pool=FakePool()) as rt:
        await rt.send("Weather in Berlin?")
    (summary,) = named(log_lines(), "run finished")
    assert summary["level"] == "info"
    assert summary["context"]["turns"] == 2
    assert summary["context"]["tool_calls"] == 1
    assert summary["context"]["tokens"]["input"] == 20
    assert "elapsed_s" in summary["context"]


async def test_a_failed_run_logs_one_error_line(log_lines):
    caller = FakeModelCaller(reply(text("No."), stop_reason="refusal"))
    async with ApiRuntime(make_settings(), model_caller=caller, pool=FakePool()) as rt:
        with pytest.raises(StopReasonError):
            await rt.send("Weather in Berlin?")
    (failure,) = named(log_lines(), "run failed")
    assert failure["level"] == "error"
    assert failure["context"]["stop_reason"] == "refusal"
    assert "refusal" in failure["context"]["error"]


async def test_a_dropped_resource_logs_a_warning(log_lines):
    invented = {"kind": "url", "url": "https://example.com", "title": "Invented page"}
    caller = FakeModelCaller(answer_reply(resources=[invented]))
    async with ApiRuntime(make_settings(), model_caller=caller, pool=FakePool()) as rt:
        await rt.send("Weather in Berlin?")
    (warning,) = named(log_lines(), "resource dropped")
    assert warning["level"] == "warning"
    assert warning["context"]["resource"]["url"] == "https://example.com"


async def test_a_server_that_failed_to_open_logs_a_warning(log_lines):
    pool = FakePool([], failures={"open-meteo": McpClientError("open-meteo", "spawn failed")})
    async with ApiRuntime(make_settings(), model_caller=FakeModelCaller(), pool=pool):
        pass
    (warning,) = named(log_lines(), "MCP server failed to open")
    assert warning["level"] == "warning"
    assert warning["context"]["server"] == "open-meteo"
    assert "spawn failed" in warning["context"]["reason"]
```

- [ ] **Step 2: Run the tests**

Run: `uv run --package weather-agents --group dev pytest tests/runtimes/test_logging.py -v`
Expected: 6 passed. These test code from Tasks 4 and 6, so they should pass at once. If one fails, the failure names the missing event or field: fix the log call in `loop.py` or `api.py` to match the names in Tasks 4 and 6, not the test. If `session_id` does not appear under `context`, read `packages/labs-logging/src/labs_logging/envelope.py` to see where bound fields land, and assert on that key instead.

- [ ] **Step 3: Run the whole suite**

Run: `uv run --package weather-agents --group dev pytest`
Expected: all pass. The logging tests configure and shut down `labs-logging` per test, so the order of the run does not matter.

- [ ] **Step 4: Commit**

```bash
git add tests/runtimes/test_logging.py src/weather_agents
git commit -m "[feature] (weather-agents) Test the session, step, summary, and warning lines a run logs"
```

---

### Task 8: Live check against the real API and the real server

**Files:**
- Create: `tests/live/test_agent_live.py`
- Modify: `Makefile` (the `test-live` help text)
- Create, run, then delete without committing: `scripts/try_agent.py`

**Interfaces:**
- Consumes: `ApiRuntime` (Task 6), `Settings` (Task 1), `ToolCallResource` (Task 2).
- Produces: nothing for later tasks.

This task needs `ANTHROPIC_API_KEY` in `packages/weather-agents/.env` and network access to the Anthropic API, so run its commands outside the sandbox. One run of it costs well under a cent on Haiku 5.5.

- [ ] **Step 1: Write the live test**

Create `tests/live/test_agent_live.py`:

```python
"""The API runtime against the real Anthropic API and the real stdio server.

Run with `make test-live`. Needs ANTHROPIC_API_KEY in packages/weather-agents/.env. The server
calls the real Open-Meteo.
"""

import json
import sys

import pytest

from weather_agents.agent_loop import ToolCallResource
from weather_agents.runtimes import ApiRuntime
from weather_agents.settings import Settings

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_a_question_and_a_follow_up_through_the_real_api(tmp_path):
    config = tmp_path / "mcp.json"
    entry = {"command": sys.executable, "args": ["-m", "weather_agents.server"]}
    config.write_text(json.dumps({"mcpServers": {"open-meteo": entry}}))
    async with ApiRuntime(Settings(mcp_config=config)) as runtime:
        first = await runtime.send("What is tomorrow's forecast high in Berlin, in Celsius?")
        second = await runtime.send("Which city did I just ask about?", first.session_id)
    assert first.answer.answer
    assert first.tool_calls >= 1
    assert any(isinstance(r, ToolCallResource) for r in first.answer.resources)
    assert second.session_id == first.session_id
    assert "Berlin" in second.answer.answer
```

- [ ] **Step 2: Run it**

Run (outside the sandbox): `uv run --package weather-agents --group dev pytest tests/live/test_agent_live.py -m live -o addopts="" -v`
Expected: 1 passed. If the first answer comes back with no `ToolCallResource`, the model wrote `arguments` differently from what it sent: read the `resource dropped` warning in the output, and tighten the resource paragraph in `WEATHER_AGENT`'s prompt (Task 2) rather than loosening the check.

- [ ] **Step 3: Try it by hand with the throwaway driver**

Create `scripts/try_agent.py`:

```python
"""Throwaway: ask two questions on one session and print the answers. Never committed."""

import asyncio
import logging

from labs_logging import LoggingConfig, configure

from weather_agents.agent_loop import RunResult
from weather_agents.runtimes import ApiRuntime
from weather_agents.settings import Settings


def show(result: RunResult) -> None:
    print(f"\n[{result.session_id}] {result.answer.answer}")
    for resource in result.answer.resources:
        print(f"  - {resource.title}: {resource.model_dump_json()}")
    print(f"  turns={result.turns} tool_calls={result.tool_calls} tokens={result.usage.model_dump()}")


async def main() -> None:
    settings = Settings()
    level = logging.getLevelNamesMapping()[settings.log_level]
    with configure(LoggingConfig(app="weather-agents", family="weather_agents", level=level)):
        async with ApiRuntime(settings) as runtime:
            first = await runtime.send("Is this weekend good for a hike near Lviv?")
            show(first)
            show(await runtime.send("And how windy will it be on Sunday?", first.session_id))


asyncio.run(main())
```

Run (outside the sandbox): `WEATHER_AGENTS_LOG_LEVEL=DEBUG uv run --package weather-agents python scripts/try_agent.py`
Expected: two answers with resources. The console shows a `model call`, `model replied`, `tool call`, and `tool result` line for each step, each value cut to 200 characters, and one `run finished` line per question.

- [ ] **Step 4: Delete the driver**

```bash
rm scripts/try_agent.py
rmdir scripts 2>/dev/null || true
```

Expected: `git status` shows no `scripts/` entry.

- [ ] **Step 5: Update the Makefile help text**

In `Makefile`, change the `test-live` line to:

```make
test-live: ## Run the live tests against the real Open-Meteo and Anthropic APIs. Needs ANTHROPIC_API_KEY in .env.
```

- [ ] **Step 6: Commit**

```bash
git add tests/live/test_agent_live.py Makefile
git commit -m "[feature] (weather-agents) Check the API runtime live against the real API and server"
```

---

### Task 9: Check the architecture doc against what got built

**Files:**
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: everything built in Tasks 1 to 8.
- Produces: nothing.

- [ ] **Step 1: Update the doc**

**REQUIRED SUB-SKILL:** use `writing-architecture` in update mode for `packages/weather-agents/docs/architecture.md`. Compare each row against the code, not against this plan. The likely drift:

- The `agent_loop`, `runtimes`, `agents`, and `settings` module rows: Planned to Built for what this plan built. The loop stops on `end_turn` or a stop-reason error. The USD cap and the deadline are still Planned (slice 2).
- The `runtimes` row: `AgentRuntime` now takes a session id on `send` and `clear`.
- The "API runtime's message list" data store: one message list per session, keyed by an id that every result returns, in memory only.
- The `.env` interface row: the `WEATHER_AGENTS_` settings and `.env.example`.
- The error-handling row: it still says no retries anywhere. That stays true until slice 2. Do not change it here.
- The `agents` row links ADR-0001, which ADR-0004 superseded. Point it at ADR-0004.

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "[docs] (weather-agents) Mark the agent loop core as Built in the architecture doc"
```
