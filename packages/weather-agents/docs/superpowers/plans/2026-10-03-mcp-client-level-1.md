# MCP Client, Level 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A weather-agnostic MCP client layer that opens every server in a Claude Code `mcpServers` file over stdio, routes calls by server name, and names the server in every failure.

**Architecture:** A thin layer over the official SDK's `mcp.Client`, pinned to `mode="legacy"`. `config.py` parses the file, `session.py` wraps one SDK client (pagination, error naming), and `pool.py` opens one session per server and routes by name. It writes no protocol code. Spec: [`../specs/2026-10-03-mcp-client-level-1-design.md`](../specs/2026-10-03-mcp-client-level-1-design.md).

**Tech Stack:** Python 3.12, `mcp>=2,<3` (already a dependency), pydantic v2 (comes with `mcp`), pytest with the anyio plugin, Ruff, ty.

## Global Constraints

- Python 3.12, in the `labs` uv workspace. No new dependency, so `pyproject.toml` and `uv.lock` do not change.
- The client is pinned to `mode="legacy"` (ADR-0003). No sampling, elicitation, list-roots, logging, or message callbacks are passed to the SDK, so the client declares no capabilities.
- `weather_agents.mcp_client` imports nothing from `weather_agents.server` and mentions nothing about weather.
- No retries and no timeouts in the client.
- Supported server types: `stdio` only, held in `SUPPORTED_TYPES`. Any other `type` is a `ConfigError` naming the server.
- SDK result fields are snake_case: `is_error`, `next_cursor`, `resource_templates`, `uri_template`.
- Catch `OSError`, `MCPError`, and `ExceptionGroup` only. Never `BaseExceptionGroup` (it swallows cancellation) and never a bare `Exception`.
- Repo conventions (`.cursor/rules/python-conventions.mdc`): `uv run` for every command, type hints everywhere, no `Any`, Google-style docstrings on public names, `__all__` in every public module, absolute imports, f-strings for human-facing text, Ruff line length 100.
- Commit messages follow the log: `[feature] (weather-agents) <what>` or `[docs] (weather-agents) <what>`. Pre-commit hooks run Ruff and ty. Fix what they report. Never use `--no-verify`.
- Work in the worktree `/Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1` on branch `weather-agents/mcp-client-level-1`. Run package commands from `packages/weather-agents/`. `uv` must read the root `uv.lock`; if the sandbox blocks it, run outside the sandbox.
- The test command is `uv run --package weather-agents --group dev pytest <path> -v` (the Makefile's `make test` wraps it).

## File Structure

```
mcp.stdio.json                                     Task 1
src/weather_agents/mcp_client/__init__.py          Task 1 (docstring), Task 3 (exports)
src/weather_agents/mcp_client/errors.py            Task 1: McpClientError, ConfigError
src/weather_agents/mcp_client/config.py            Task 1: SUPPORTED_TYPES, StdioServerConfig, load_config
src/weather_agents/mcp_client/session.py           Task 2: SdkClient, ClientFactory, McpSession
src/weather_agents/mcp_client/pool.py              Task 3: McpClientPool
tests/client/__init__.py                           Task 1
tests/client/fakes.py                              Task 2: FakeClient, FakeFactory, make_* builders
tests/client/test_config.py                        Task 1
tests/client/test_session.py                       Task 2
tests/client/test_pool.py                          Task 3
tests/client/test_stdio_integration.py             Task 4
docs/architecture.md                               Task 5
```

All paths below are relative to `packages/weather-agents/` unless they start with `/`.

## Docs Check

- `docs/architecture.md` could drift: the `mcp_client` module row and the `mcp.stdio.json` row say Planned. Task 5 checks it.
- `docs/prd/0001-open-meteo-mcp-server-and-client.md` is not edited. Its `Status` stays `Building`, because two criteria of use case 4 (handlers and notification pass-through) stay unbuilt.
- `docs/vision.md` and `docs/adr/` are not touched. No ADR came out of the design session.
- The package has no README.

---

### Task 1: Errors, config loader, and `mcp.stdio.json`

**Files:**
- Create: `src/weather_agents/mcp_client/__init__.py`, `src/weather_agents/mcp_client/errors.py`, `src/weather_agents/mcp_client/config.py`
- Create: `mcp.stdio.json`, `tests/client/__init__.py`, `tests/client/test_config.py`
- Also commit: the spec and this plan, which are untracked in the worktree.

**Interfaces:**
- Produces:
  - `McpClientError(server: str, cause: str)` with attributes `.server` and `.cause`. Its message is `MCP server '<server>': <cause>`.
  - `ConfigError(Exception)`.
  - `SUPPORTED_TYPES: frozenset[str]`.
  - `StdioServerConfig(command: str, args: list[str] = [], env: dict[str, str] | None = None, type: Literal["stdio"] = "stdio")`, which rejects unknown keys (`extra="forbid"`).
  - `load_config(path: Path) -> dict[str, StdioServerConfig]`.

- [ ] **Step 1: Commit the spec and the plan on their own**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/docs/superpowers/specs/2026-10-03-mcp-client-level-1-design.md \
        packages/weather-agents/docs/superpowers/plans/2026-10-03-mcp-client-level-1.md
git commit -m "[docs] (weather-agents) Add level 1 MCP client spec and plan"
```

Expected: the hooks pass and one commit is created.

- [ ] **Step 2: Write the failing config tests**

Create `tests/client/__init__.py` as an empty file. Create `tests/client/test_config.py`:

```python
import json
from pathlib import Path

import pytest

from weather_agents.mcp_client.config import StdioServerConfig, load_config
from weather_agents.mcp_client.errors import ConfigError

SHIPPED_CONFIG = Path(__file__).parents[2] / "mcp.stdio.json"


def write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps(payload))
    return path


def test_a_stdio_entry_loads_with_its_command_args_and_env(tmp_path):
    entry = {"command": "uv", "args": ["run", "server"], "env": {"A": "1"}}
    servers = load_config(write(tmp_path, {"mcpServers": {"weather": entry}}))
    assert servers == {
        "weather": StdioServerConfig(command="uv", args=["run", "server"], env={"A": "1"})
    }


def test_type_defaults_to_stdio_and_may_be_given(tmp_path):
    payload = {
        "mcpServers": {
            "plain": {"command": "a"},
            "typed": {"type": "stdio", "command": "b"},
        }
    }
    servers = load_config(write(tmp_path, payload))
    assert servers["plain"].type == "stdio"
    assert servers["typed"].type == "stdio"
    assert servers["plain"].args == []
    assert servers["plain"].env is None


def test_an_unsupported_type_names_the_server_and_the_supported_types(tmp_path):
    payload = {"mcpServers": {"web": {"type": "http", "url": "http://127.0.0.1:8000/mcp"}}}
    with pytest.raises(ConfigError, match="server 'web': type 'http' is not supported, supported: stdio"):
        load_config(write(tmp_path, payload))


def test_a_type_that_is_not_a_string_is_unsupported_too(tmp_path):
    payload = {"mcpServers": {"odd": {"type": ["stdio"], "command": "a"}}}
    with pytest.raises(ConfigError, match="server 'odd': type"):
        load_config(write(tmp_path, payload))


def test_an_unknown_key_names_the_server_and_the_key(tmp_path):
    payload = {"mcpServers": {"weather": {"command": "a", "cwd": "/tmp"}}}
    with pytest.raises(ConfigError, match="server 'weather': cwd"):
        load_config(write(tmp_path, payload))


def test_a_missing_command_names_the_server_and_the_field(tmp_path):
    with pytest.raises(ConfigError, match="server 'weather': command"):
        load_config(write(tmp_path, {"mcpServers": {"weather": {"args": []}}}))


def test_an_entry_that_is_not_an_object_names_the_server(tmp_path):
    with pytest.raises(ConfigError, match="server 'weather': entry must be an object"):
        load_config(write(tmp_path, {"mcpServers": {"weather": "uv run server"}}))


def test_a_missing_file_names_the_path(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(ConfigError, match=f"cannot read {missing}"):
        load_config(missing)


def test_invalid_json_names_the_path(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError, match=f"{path} is not valid JSON"):
        load_config(path)


def test_a_file_without_mcp_servers_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="no 'mcpServers' object"):
        load_config(write(tmp_path, {"servers": {}}))


def test_the_shipped_stdio_config_loads():
    servers = load_config(SHIPPED_CONFIG)
    assert list(servers) == ["open-meteo"]
    assert servers["open-meteo"].command == "uv"
    assert servers["open-meteo"].args[-2:] == ["-m", "weather_agents.server"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_config.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'weather_agents.mcp_client'`.

- [ ] **Step 4: Write the errors module**

Create `src/weather_agents/mcp_client/__init__.py`:

```python
"""A weather-agnostic MCP client layer over the official SDK."""
```

Create `src/weather_agents/mcp_client/errors.py`:

```python
"""Errors the MCP client raises. Every runtime failure names its server."""

__all__ = ["ConfigError", "McpClientError"]


class McpClientError(Exception):
    """A server could not be reached, dropped, or answered with a protocol error.

    Args:
        server: The name of the server in the `mcpServers` file.
        cause: What went wrong, in one sentence.
    """

    def __init__(self, server: str, cause: str) -> None:
        super().__init__(f"MCP server '{server}': {cause}")
        self.server = server
        self.cause = cause


class ConfigError(Exception):
    """The `mcpServers` file is missing, unreadable, or has an entry the client cannot use."""
```

- [ ] **Step 5: Write the config module**

Create `src/weather_agents/mcp_client/config.py`:

```python
"""Reads a Claude Code `mcpServers` file into stdio server settings."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from weather_agents.mcp_client.errors import ConfigError

__all__ = ["SUPPORTED_TYPES", "StdioServerConfig", "load_config"]

# Level 2 adds "http". Anything outside this set fails loudly instead of being skipped.
SUPPORTED_TYPES = frozenset({"stdio"})


class StdioServerConfig(BaseModel):
    """One `mcpServers` entry that starts a server as a child process."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None


def load_config(path: Path) -> dict[str, StdioServerConfig]:
    """Read the `mcpServers` object of a config file.

    Args:
        path: A JSON file in Claude Code's `mcpServers` format.

    Returns:
        The servers by name, in the file's order.

    Raises:
        ConfigError: The file cannot be read or parsed, has no `mcpServers` object, or has an
            entry with an unsupported type, an unknown key, or a missing field. The whole load
            fails, because this is a mistake in the file and not a server that is down.
    """
    try:
        text = path.read_text()
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror or error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path} is not valid JSON: {error}") from error
    entries = raw.get("mcpServers") if isinstance(raw, dict) else None
    if not isinstance(entries, dict):
        raise ConfigError(f"{path} has no 'mcpServers' object")
    return {name: _parse_entry(name, entry) for name, entry in entries.items()}


def _parse_entry(name: str, entry: object) -> StdioServerConfig:
    if not isinstance(entry, dict):
        raise ConfigError(f"server '{name}': entry must be an object")
    kind = entry.get("type", "stdio")
    # The isinstance check also keeps an unhashable JSON value from raising TypeError below.
    if not isinstance(kind, str) or kind not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ConfigError(f"server '{name}': type {kind!r} is not supported, supported: {supported}")
    try:
        return StdioServerConfig.model_validate(entry)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise ConfigError(f"server '{name}': {where}: {first['msg']}") from error
```

Note: `{kind!r}` prints `'http'` with quotes, which matches the test's `type 'http'`.

- [ ] **Step 6: Write the shipped config**

Create `mcp.stdio.json` (in `packages/weather-agents/`):

```json
{
  "mcpServers": {
    "open-meteo": {
      "command": "uv",
      "args": ["run", "--package", "weather-agents", "python", "-m", "weather_agents.server"]
    }
  }
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_config.py -v`
Expected: 11 passed.

If `test_an_unknown_key_names_the_server_and_the_key` fails, print the pydantic error with `StdioServerConfig.model_validate({"command": "a", "cwd": "/tmp"})` and fix the message format in `_parse_entry`. Do not loosen the test.

- [ ] **Step 8: Commit**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/mcp.stdio.json \
        packages/weather-agents/src/weather_agents/mcp_client \
        packages/weather-agents/tests/client
git commit -m "[feature] (weather-agents) Add the MCP client config loader and the stdio config file"
```

Expected: hooks pass. If Ruff reformats files, run `git add` on them again and re-commit.

---

### Task 2: `McpSession` and the client fakes

**Files:**
- Create: `src/weather_agents/mcp_client/session.py`, `tests/client/fakes.py`, `tests/client/test_session.py`

**Interfaces:**
- Consumes: `StdioServerConfig` and `McpClientError` from Task 1.
- Produces:
  - `SdkClient` (Protocol): the seven `mcp.Client` methods the session uses.
  - `ClientFactory = Callable[..., AbstractAsyncContextManager[SdkClient]]`. The session calls it as `factory(StdioServerParameters, mode="legacy")`.
  - `McpSession(name: str, config: StdioServerConfig, *, client_factory: ClientFactory = Client)`, an async context manager. It has `name: str` and these methods:
    - `list_tools() -> list[Tool]`
    - `list_resources() -> list[Resource]`
    - `list_resource_templates() -> list[ResourceTemplate]`
    - `list_prompts() -> list[Prompt]`
    - `call_tool(name: str, arguments: dict[str, object] | None = None) -> CallToolResult`
    - `read_resource(uri: str) -> ReadResourceResult`
    - `get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult`
  - Test helpers in `tests/client/fakes.py`: `FakeClient`, `FakeFactory`, `make_tool`, `make_resource`, `make_template`, `make_prompt`.

- [ ] **Step 1: Write the fakes**

Create `tests/client/fakes.py`:

```python
"""Stand-ins for `mcp.Client`, so session and pool tests need no child process."""

from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Self

from mcp import StdioServerParameters
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)


def make_tool(name: str) -> Tool:
    return Tool(name=name, input_schema={"type": "object"})


def make_resource(uri: str) -> Resource:
    return Resource(name=uri, uri=uri)


def make_template(uri_template: str) -> ResourceTemplate:
    return ResourceTemplate(name=uri_template, uri_template=uri_template)


def make_prompt(name: str) -> Prompt:
    return Prompt(name=name)


class FakeClient:
    """Serves canned lists in pages of `page_size`, and can fail on entry or on every call.

    `open_error` raises when the client is entered, like a spawn failure. Set `error` after
    entering to simulate a session that drops.
    """

    def __init__(
        self,
        *,
        tools: Sequence[Tool] = (),
        resources: Sequence[Resource] = (),
        templates: Sequence[ResourceTemplate] = (),
        prompts: Sequence[Prompt] = (),
        page_size: int = 2,
        open_error: BaseException | None = None,
    ) -> None:
        self.tools = tools
        self.resources = resources
        self.templates = templates
        self.prompts = prompts
        self.page_size = page_size
        self.open_error = open_error
        self.error: BaseException | None = None
        self.calls: list[tuple[str, object]] = []
        self.tool_result = CallToolResult(content=[TextContent(type="text", text="ok")])
        self.resource_result = ReadResourceResult(contents=[])
        self.prompt_result = GetPromptResult(messages=[])
        self.closed = False

    async def __aenter__(self) -> Self:
        if self.open_error is not None:
            raise self.open_error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def _record(self, method: str, detail: object) -> None:
        self.calls.append((method, detail))
        if self.error is not None:
            raise self.error

    def _page[T](self, items: Sequence[T], cursor: str | None) -> tuple[list[T], str | None]:
        start = int(cursor or 0)
        end = start + self.page_size
        return list(items[start:end]), (str(end) if end < len(items) else None)

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult:
        self._record("list_tools", cursor)
        page, next_cursor = self._page(self.tools, cursor)
        return ListToolsResult(tools=page, next_cursor=next_cursor)

    async def list_resources(self, *, cursor: str | None = None) -> ListResourcesResult:
        self._record("list_resources", cursor)
        page, next_cursor = self._page(self.resources, cursor)
        return ListResourcesResult(resources=page, next_cursor=next_cursor)

    async def list_resource_templates(
        self, *, cursor: str | None = None
    ) -> ListResourceTemplatesResult:
        self._record("list_resource_templates", cursor)
        page, next_cursor = self._page(self.templates, cursor)
        return ListResourceTemplatesResult(resource_templates=page, next_cursor=next_cursor)

    async def list_prompts(self, *, cursor: str | None = None) -> ListPromptsResult:
        self._record("list_prompts", cursor)
        page, next_cursor = self._page(self.prompts, cursor)
        return ListPromptsResult(prompts=page, next_cursor=next_cursor)

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        self._record("call_tool", (name, arguments))
        return self.tool_result

    async def read_resource(self, uri: str) -> ReadResourceResult:
        self._record("read_resource", uri)
        return self.resource_result

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        self._record("get_prompt", (name, arguments))
        return self.prompt_result


class FakeFactory:
    """Stands in for the `Client` class. Picks a client by the spawn command."""

    def __init__(self, clients: Mapping[str, FakeClient]) -> None:
        self.clients = clients
        self.calls: list[tuple[StdioServerParameters, dict[str, object]]] = []

    def __call__(self, params: StdioServerParameters, **kwargs: object) -> FakeClient:
        self.calls.append((params, kwargs))
        return self.clients[params.command]
```

- [ ] **Step 2: Write the failing session tests**

Create `tests/client/test_session.py`:

```python
import pytest
from mcp import MCPError
from mcp.types import CallToolResult, TextContent

from tests.client.fakes import (
    FakeClient,
    FakeFactory,
    make_prompt,
    make_resource,
    make_template,
    make_tool,
)
from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.mcp_client.errors import McpClientError
from weather_agents.mcp_client.session import McpSession

pytestmark = pytest.mark.anyio

CONFIG = StdioServerConfig(command="fake", args=["--flag"], env={"K": "v"})


def session_for(client: FakeClient) -> tuple[McpSession, FakeFactory]:
    factory = FakeFactory({"fake": client})
    return McpSession("weather", CONFIG, client_factory=factory), factory


async def test_the_session_starts_the_sdk_client_in_legacy_mode_with_no_handlers():
    session, factory = session_for(FakeClient())
    async with session:
        pass
    ((params, kwargs),) = factory.calls
    assert kwargs == {"mode": "legacy"}
    assert (params.command, params.args, params.env) == ("fake", ["--flag"], {"K": "v"})


async def test_the_session_closes_the_sdk_client_on_exit():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        assert not client.closed
    assert client.closed


async def test_list_tools_follows_every_page_and_returns_a_flat_list():
    client = FakeClient(tools=[make_tool(name) for name in "abcde"], page_size=2)
    session, _ = session_for(client)
    async with session:
        tools = await session.list_tools()
    assert [tool.name for tool in tools] == list("abcde")
    assert client.calls == [("list_tools", None), ("list_tools", "2"), ("list_tools", "4")]


async def test_the_other_three_lists_are_flat_lists_too():
    client = FakeClient(
        resources=[make_resource("x://1"), make_resource("x://2"), make_resource("x://3")],
        templates=[make_template("x://{a}"), make_template("y://{b}"), make_template("z://{c}")],
        prompts=[make_prompt("p1"), make_prompt("p2"), make_prompt("p3")],
    )
    session, _ = session_for(client)
    async with session:
        resources = await session.list_resources()
        templates = await session.list_resource_templates()
        prompts = await session.list_prompts()
    assert [str(resource.uri) for resource in resources] == ["x://1", "x://2", "x://3"]
    assert [template.uri_template for template in templates] == ["x://{a}", "y://{b}", "z://{c}"]
    assert [prompt.name for prompt in prompts] == ["p1", "p2", "p3"]


async def test_call_tool_returns_an_error_result_as_it_is():
    client = FakeClient()
    client.tool_result = CallToolResult(
        content=[TextContent(type="text", text="boom")], is_error=True
    )
    session, _ = session_for(client)
    async with session:
        result = await session.call_tool("forecast", {"latitude": 95})
    assert result is client.tool_result
    assert result.is_error
    assert client.calls == [("call_tool", ("forecast", {"latitude": 95}))]


async def test_read_resource_and_get_prompt_return_the_sdk_results():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        resource = await session.read_resource("x://1")
        prompt = await session.get_prompt("p1", {"month": "June"})
    assert resource is client.resource_result
    assert prompt is client.prompt_result
    assert client.calls == [("read_resource", "x://1"), ("get_prompt", ("p1", {"month": "June"}))]


async def test_a_protocol_error_names_the_server_and_the_operation():
    client = FakeClient()
    session, _ = session_for(client)
    async with session:
        client.error = MCPError(-32000, "Connection closed")
        with pytest.raises(McpClientError) as caught:
            await session.call_tool("forecast", {})
    assert caught.value.server == "weather"
    assert str(caught.value) == "MCP server 'weather': call_tool 'forecast' failed: Connection closed"
    assert isinstance(caught.value.__cause__, MCPError)


async def test_a_spawn_failure_names_the_server_and_the_command():
    client = FakeClient(open_error=FileNotFoundError(2, "No such file or directory"))
    session, _ = session_for(client)
    with pytest.raises(McpClientError) as caught:
        async with session:
            pass
    assert caught.value.server == "weather"
    assert "could not start 'fake': No such file or directory" in str(caught.value)


async def test_an_exception_group_from_the_sdk_is_unwrapped_to_its_cause():
    nested = ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [ExceptionGroup("unhandled errors in a TaskGroup", [MCPError(-32000, "Connection closed")])],
    )
    session, _ = session_for(FakeClient(open_error=nested))
    with pytest.raises(McpClientError) as caught:
        async with session:
            pass
    assert "could not connect: Connection closed" in str(caught.value)


async def test_calling_before_the_session_is_open_is_an_error():
    session, _ = session_for(FakeClient())
    with pytest.raises(McpClientError, match="session is not open"):
        await session.list_tools()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_session.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'weather_agents.mcp_client.session'`.

- [ ] **Step 4: Write the session**

Create `src/weather_agents/mcp_client/session.py`:

```python
"""One MCP server, reached through one SDK client."""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, contextmanager
from types import TracebackType
from typing import Protocol, Self

from mcp import Client, MCPError, StdioServerParameters
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    Tool,
)

from weather_agents.mcp_client.config import StdioServerConfig
from weather_agents.mcp_client.errors import McpClientError

__all__ = ["ClientFactory", "McpSession", "SdkClient"]


class SdkClient(Protocol):
    """The part of `mcp.Client` the session uses. Tests satisfy it with a fake."""

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult: ...

    async def list_resources(self, *, cursor: str | None = None) -> ListResourcesResult: ...

    async def list_resource_templates(
        self, *, cursor: str | None = None
    ) -> ListResourceTemplatesResult: ...

    async def list_prompts(self, *, cursor: str | None = None) -> ListPromptsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...

    async def read_resource(self, uri: str) -> ReadResourceResult: ...

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult: ...


# Called as `factory(params, mode="legacy")`. The default is the SDK's own `Client` class.
type ClientFactory = Callable[..., AbstractAsyncContextManager[SdkClient]]


class McpSession:
    """An open connection to one stdio server.

    Use it as an async context manager. Open and close it in the same task, because the SDK's
    client runs a task group.

    Args:
        name: The server's name in the `mcpServers` file. Every error names it.
        config: How to start the server.
        client_factory: Builds the SDK client. Tests pass a fake.
    """

    def __init__(
        self,
        name: str,
        config: StdioServerConfig,
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        self.name = name
        self._config = config
        self._client_factory = client_factory
        self._stack = AsyncExitStack()
        self._client: SdkClient | None = None

    async def __aenter__(self) -> Self:
        params = StdioServerParameters(
            command=self._config.command, args=self._config.args, env=self._config.env
        )
        try:
            # Legacy mode is pinned by ADR-0003. No handlers are passed, so the SDK declares
            # no client capabilities.
            self._client = await self._stack.enter_async_context(
                self._client_factory(params, mode="legacy")
            )
        except (OSError, ExceptionGroup) as error:
            raise McpClientError(self.name, _open_failure(error, self._config.command)) from error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._client = None
        return await self._stack.__aexit__(exc_type, exc, tb)

    async def list_tools(self) -> list[Tool]:
        """List every tool, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Tool], str | None]:
            page = await client.list_tools(cursor=cursor)
            return page.tools, page.next_cursor

        return await self._collect("list_tools", fetch)

    async def list_resources(self) -> list[Resource]:
        """List every fixed resource, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Resource], str | None]:
            page = await client.list_resources(cursor=cursor)
            return page.resources, page.next_cursor

        return await self._collect("list_resources", fetch)

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        """List every resource template, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[ResourceTemplate], str | None]:
            page = await client.list_resource_templates(cursor=cursor)
            return page.resource_templates, page.next_cursor

        return await self._collect("list_resource_templates", fetch)

    async def list_prompts(self) -> list[Prompt]:
        """List every prompt, following pagination."""
        client = self._open_client()

        async def fetch(cursor: str | None) -> tuple[list[Prompt], str | None]:
            page = await client.list_prompts(cursor=cursor)
            return page.prompts, page.next_cursor

        return await self._collect("list_prompts", fetch)

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Call a tool.

        Returns:
            The SDK result as it is. A result with `is_error=True` is a normal return, because
            the agent loop feeds it back to the model.

        Raises:
            McpClientError: The call failed at the protocol level, for example a dropped session.
        """
        client = self._open_client()
        with self._named(f"call_tool '{name}'"):
            return await client.call_tool(name, arguments)

    async def read_resource(self, uri: str) -> ReadResourceResult:
        """Read a resource by URI."""
        client = self._open_client()
        with self._named(f"read_resource '{uri}'"):
            return await client.read_resource(uri)

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        """Get a prompt by name."""
        client = self._open_client()
        with self._named(f"get_prompt '{name}'"):
            return await client.get_prompt(name, arguments)

    def _open_client(self) -> SdkClient:
        if self._client is None:
            raise McpClientError(self.name, "session is not open")
        return self._client

    @contextmanager
    def _named(self, operation: str) -> Iterator[None]:
        try:
            yield
        except MCPError as error:
            raise McpClientError(self.name, f"{operation} failed: {error.message}") from error

    async def _collect[T](
        self,
        operation: str,
        fetch: Callable[[str | None], Awaitable[tuple[list[T], str | None]]],
    ) -> list[T]:
        items: list[T] = []
        cursor: str | None = None
        with self._named(operation):
            while True:
                page, cursor = await fetch(cursor)
                items.extend(page)
                if cursor is None:
                    return items


def _root_cause(error: BaseException) -> BaseException:
    # Entering the SDK client wraps its failure in nested ExceptionGroups. Take the first leaf.
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def _open_failure(error: BaseException, command: str) -> str:
    root = _root_cause(error)
    if isinstance(root, OSError):
        return f"could not start '{command}': {root.strerror or root}"
    if isinstance(root, MCPError):
        return f"could not connect: {root.message}"
    return f"could not connect: {root!r}"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_session.py -v`
Expected: 10 passed.

- [ ] **Step 6: Check types and lint before committing**

Run from the worktree root: `uv run ruff check packages/weather-agents && uv run ruff format --check packages/weather-agents`
Expected: no findings.

If `ty` (run by the commit hook) rejects `Client` as the default `client_factory`, the Protocol's signatures do not match the SDK's. Change the Protocol so `Client` satisfies it. Look at `inspect.signature(Client.<method>)` and align the parameters. Do not add a blanket ignore.

- [ ] **Step 7: Commit**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/src/weather_agents/mcp_client/session.py \
        packages/weather-agents/tests/client/fakes.py \
        packages/weather-agents/tests/client/test_session.py
git commit -m "[feature] (weather-agents) Add the MCP client session over the SDK client"
```

---

### Task 3: `McpClientPool` and the package exports

**Files:**
- Create: `src/weather_agents/mcp_client/pool.py`, `tests/client/test_pool.py`
- Modify: `src/weather_agents/mcp_client/__init__.py`

**Interfaces:**
- Consumes: `McpSession`, `ClientFactory` from Task 2. `StdioServerConfig`, `load_config` from Task 1. `FakeClient`, `FakeFactory`, `make_tool` from `tests/client/fakes.py`.
- Produces:
  - `McpClientPool(servers: Mapping[str, StdioServerConfig], *, client_factory: ClientFactory = Client)`, an async context manager returning itself.
  - `McpClientPool.from_file(path: Path, *, client_factory: ClientFactory = Client) -> McpClientPool`.
  - `pool.failures: dict[str, McpClientError]`, `pool.server_names: list[str]`.
  - Seven methods that take the server name first: `list_tools(server)`, `list_resources(server)`, `list_resource_templates(server)`, `list_prompts(server)`, `call_tool(server, name, arguments=None)`, `read_resource(server, uri)`, `get_prompt(server, name, arguments=None)`. They return what the session's methods return.
  - Package exports: `McpClientPool`, `McpClientError`, `ConfigError`, `load_config`.

- [ ] **Step 1: Write the failing pool tests**

Create `tests/client/test_pool.py`:

```python
import json
from pathlib import Path

import pytest
from mcp import MCPError

from tests.client.fakes import FakeClient, FakeFactory, make_prompt, make_tool
from weather_agents.mcp_client import McpClientError, McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig

pytestmark = pytest.mark.anyio

CONFIGS = {"a": StdioServerConfig(command="a"), "b": StdioServerConfig(command="b")}


def pool_with(a: FakeClient, b: FakeClient) -> McpClientPool:
    return McpClientPool(CONFIGS, client_factory=FakeFactory({"a": a, "b": b}))


async def test_every_call_goes_to_the_named_server_only():
    a = FakeClient(tools=[make_tool("from_a")], prompts=[make_prompt("pa")])
    b = FakeClient(tools=[make_tool("from_b")])
    async with pool_with(a, b) as pool:
        tools_a = await pool.list_tools("a")
        tools_b = await pool.list_tools("b")
        await pool.call_tool("b", "from_b", {"x": 1})
        prompts_a = await pool.list_prompts("a")
    assert [tool.name for tool in tools_a] == ["from_a"]
    assert [tool.name for tool in tools_b] == ["from_b"]
    assert [prompt.name for prompt in prompts_a] == ["pa"]
    assert ("call_tool", ("from_b", {"x": 1})) in b.calls
    assert all(method != "call_tool" for method, _ in a.calls)


async def test_the_other_routed_methods_reach_the_named_server():
    a, b = FakeClient(), FakeClient()
    async with pool_with(a, b) as pool:
        await pool.list_resources("a")
        await pool.list_resource_templates("a")
        await pool.read_resource("b", "x://1")
        await pool.get_prompt("b", "p1", {"month": "June"})
    assert [method for method, _ in a.calls] == ["list_resources", "list_resource_templates"]
    assert b.calls == [("read_resource", "x://1"), ("get_prompt", ("p1", {"month": "June"}))]


async def test_servers_open_in_file_order_and_close_on_exit():
    a, b = FakeClient(), FakeClient()
    async with pool_with(a, b) as pool:
        assert pool.server_names == ["a", "b"]
        assert pool.failures == {}
        assert not a.closed
        assert not b.closed
    assert a.closed
    assert b.closed


async def test_a_server_that_fails_to_open_is_recorded_and_the_others_still_work():
    a = FakeClient(tools=[make_tool("from_a")])
    b = FakeClient(open_error=FileNotFoundError(2, "No such file or directory"))
    async with pool_with(a, b) as pool:
        assert pool.server_names == ["a"]
        assert list(pool.failures) == ["b"]
        assert pool.failures["b"].server == "b"
        assert [tool.name for tool in await pool.list_tools("a")] == ["from_a"]
        with pytest.raises(McpClientError, match="'b'.*could not start") as caught:
            await pool.list_tools("b")
    assert caught.value is pool.failures["b"]


async def test_a_name_that_is_not_in_the_file_is_an_error():
    async with pool_with(FakeClient(), FakeClient()) as pool:
        with pytest.raises(McpClientError, match="'ghost': no such server"):
            await pool.list_tools("ghost")


async def test_a_dropped_session_fails_its_calls_and_leaves_the_other_server_working():
    a = FakeClient()
    b = FakeClient(tools=[make_tool("from_b")])
    async with pool_with(a, b) as pool:
        a.error = MCPError(-32000, "Connection closed")
        with pytest.raises(McpClientError, match="'a'.*Connection closed"):
            await pool.list_tools("a")
        assert [tool.name for tool in await pool.list_tools("b")] == ["from_b"]
    assert a.closed
    assert b.closed


async def test_from_file_opens_the_servers_in_the_file(tmp_path: Path):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"a": {"command": "a"}}}))
    client = FakeClient(tools=[make_tool("from_a")])
    pool = McpClientPool.from_file(path, client_factory=FakeFactory({"a": client}))
    async with pool:
        assert [tool.name for tool in await pool.list_tools("a")] == ["from_a"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_pool.py -v`
Expected: collection error, `ImportError: cannot import name 'McpClientError' from 'weather_agents.mcp_client'`.

- [ ] **Step 3: Write the pool**

Create `src/weather_agents/mcp_client/pool.py`:

```python
"""Opens every server in an `mcpServers` file and routes calls to them by name."""

from collections.abc import Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import Self

from mcp import Client
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    Tool,
)

from weather_agents.mcp_client.config import StdioServerConfig, load_config
from weather_agents.mcp_client.errors import McpClientError
from weather_agents.mcp_client.session import ClientFactory, McpSession

__all__ = ["McpClientPool"]


class McpClientPool:
    """A set of open MCP sessions, one per configured server.

    A server that fails to open is recorded in `failures` and the others still open, so one
    broken server does not stop the chat. Open and close the pool in the same task.

    Tool names are not merged or prefixed across servers. Every call names its server, and the
    agent loop decides how to present tools to the model.

    Args:
        servers: The servers to open, by name.
        client_factory: Builds each SDK client. Tests pass a fake.
    """

    def __init__(
        self,
        servers: Mapping[str, StdioServerConfig],
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        self._servers = dict(servers)
        self._client_factory = client_factory
        self._sessions: dict[str, McpSession] = {}
        self._stack = AsyncExitStack()
        self.failures: dict[str, McpClientError] = {}

    @classmethod
    def from_file(cls, path: Path, *, client_factory: ClientFactory = Client) -> Self:
        """Build a pool from an `mcpServers` file.

        Raises:
            ConfigError: The file or one of its entries is unusable.
        """
        return cls(load_config(path), client_factory=client_factory)

    @property
    def server_names(self) -> list[str]:
        """The servers that opened, in the file's order."""
        return list(self._sessions)

    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as stack:
            for name, config in self._servers.items():
                session = McpSession(name, config, client_factory=self._client_factory)
                try:
                    self._sessions[name] = await stack.enter_async_context(session)
                except McpClientError as error:
                    self.failures[name] = error
            # Sessions stay open past this block. `pop_all` hands them to the pool's own stack.
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._sessions.clear()
        return await self._stack.__aexit__(exc_type, exc, tb)

    async def list_tools(self, server: str) -> list[Tool]:
        return await self._session(server).list_tools()

    async def list_resources(self, server: str) -> list[Resource]:
        return await self._session(server).list_resources()

    async def list_resource_templates(self, server: str) -> list[ResourceTemplate]:
        return await self._session(server).list_resource_templates()

    async def list_prompts(self, server: str) -> list[Prompt]:
        return await self._session(server).list_prompts()

    async def call_tool(
        self, server: str, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        return await self._session(server).call_tool(name, arguments)

    async def read_resource(self, server: str, uri: str) -> ReadResourceResult:
        return await self._session(server).read_resource(uri)

    async def get_prompt(
        self, server: str, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        return await self._session(server).get_prompt(name, arguments)

    def _session(self, server: str) -> McpSession:
        if server in self._sessions:
            return self._sessions[server]
        if server in self.failures:
            raise self.failures[server]
        raise McpClientError(server, "no such server")
```

The seven routed methods repeat the session's signatures on purpose. A `__getattr__` proxy would hide the API from the type checker.

- [ ] **Step 4: Export the public names**

Replace `src/weather_agents/mcp_client/__init__.py` with:

```python
"""A weather-agnostic MCP client layer over the official SDK."""

from weather_agents.mcp_client.config import load_config
from weather_agents.mcp_client.errors import ConfigError, McpClientError
from weather_agents.mcp_client.pool import McpClientPool

__all__ = ["ConfigError", "McpClientError", "McpClientPool", "load_config"]
```

- [ ] **Step 5: Run the whole client suite**

Run: `uv run --package weather-agents --group dev pytest tests/client -v`
Expected: 28 passed (11 config, 10 session, 7 pool).

- [ ] **Step 6: Commit**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/src/weather_agents/mcp_client \
        packages/weather-agents/tests/client/test_pool.py
git commit -m "[feature] (weather-agents) Add the MCP client pool that routes calls by server name"
```

---

### Task 4: Integration test against the real stdio server

**Files:**
- Create: `tests/client/test_stdio_integration.py`

**Interfaces:**
- Consumes: `McpClientPool`, `McpClientError`, `load_config` from the package root. `StdioServerConfig` from `weather_agents.mcp_client.config`.

No network is needed. The one tool call sends an out-of-range latitude, which the server rejects before it contacts Open-Meteo.

- [ ] **Step 1: Write the integration tests**

Create `tests/client/test_stdio_integration.py`:

```python
"""Our pool against the real stdio server. Nothing here reaches Open-Meteo."""

import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp.types import TextContent, TextResourceContents

from weather_agents.mcp_client import McpClientError, McpClientPool
from weather_agents.mcp_client.config import StdioServerConfig

pytestmark = pytest.mark.anyio

# A hang fails the test instead of stalling the run.
TIME_LIMIT_SECONDS = 30

REAL_SERVER = StdioServerConfig(command=sys.executable, args=["-m", "weather_agents.server"])


def write_config(tmp_path: Path) -> Path:
    path = tmp_path / "mcp.json"
    entry = {"command": REAL_SERVER.command, "args": REAL_SERVER.args}
    path.write_text(json.dumps({"mcpServers": {"open-meteo": entry}}))
    return path


async def test_the_pool_lists_and_uses_everything_the_real_server_offers(tmp_path):
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool.from_file(write_config(tmp_path)) as pool:
            assert pool.failures == {}
            tools = await pool.list_tools("open-meteo")
            prompts = await pool.list_prompts("open-meteo")
            resources = await pool.list_resources("open-meteo")
            templates = await pool.list_resource_templates("open-meteo")
            guide = await pool.read_resource("open-meteo", "open-meteo://guide")
            prompt = await pool.get_prompt("open-meteo", "weekend_check")
    guide_part = guide.contents[0]
    prompt_part = prompt.messages[0].content
    assert isinstance(guide_part, TextResourceContents)
    assert isinstance(prompt_part, TextContent)
    assert len(tools) == 11
    assert {entry.name for entry in prompts} == {"weekend_check", "compare_places"}
    assert [str(resource.uri) for resource in resources] == ["open-meteo://guide"]
    assert [template.uri_template for template in templates] == [
        "open-meteo://endpoints/{endpoint}"
    ]
    assert guide_part.text.startswith("# Open-Meteo guide")
    assert "geocode_search" in prompt_part.text


async def test_a_tool_error_comes_back_as_a_result_not_an_exception(tmp_path):
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool.from_file(write_config(tmp_path)) as pool:
            result = await pool.call_tool("open-meteo", "forecast", {"latitude": 95, "longitude": 0})
    content = result.content[0]
    assert result.is_error
    assert isinstance(content, TextContent)
    assert "latitude" in content.text


async def test_servers_that_cannot_start_are_named_and_the_real_one_still_works():
    servers = {
        "ghost": StdioServerConfig(command="definitely-not-a-command-xyz"),
        "quitter": StdioServerConfig(command=sys.executable, args=["-c", "pass"]),
        "open-meteo": REAL_SERVER,
    }
    with anyio.fail_after(TIME_LIMIT_SECONDS):
        async with McpClientPool(servers) as pool:
            assert pool.server_names == ["open-meteo"]
            assert set(pool.failures) == {"ghost", "quitter"}
            assert len(await pool.list_tools("open-meteo")) == 11
            with pytest.raises(McpClientError, match="'ghost'"):
                await pool.list_tools("ghost")
    assert "definitely-not-a-command-xyz" in str(pool.failures["ghost"])
    assert "Connection closed" in str(pool.failures["quitter"])
```

- [ ] **Step 2: Run the tests**

Run: `uv run --package weather-agents --group dev pytest tests/client/test_stdio_integration.py -v`
Expected: 3 passed in a few seconds. The SDK logs a rejected-arguments line for `forecast` and nothing else.

These tests exercise code from Tasks 1 to 3, so they should pass on the first run. If one fails, the cause is a mismatch with the real SDK, so read the failure before changing code:

- A hang means the time limit fired. Check that the `quitter` entry's failure is caught.
- A bare `ExceptionGroup` escaping `McpClientPool.__aenter__` means `_open_failure` or the `except (OSError, ExceptionGroup)` clause in `McpSession.__aenter__` missed a case. Fix it there, and add a unit case to `tests/client/test_session.py` for what you found.

- [ ] **Step 3: Run the full suite**

Run: `make test` (from `packages/weather-agents/`)
Expected: 148 passed, 31 deselected. That is the 117 existing tests, 28 client unit tests from Tasks 1 to 3, and the 3 integration tests.

- [ ] **Step 4: Commit**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/tests/client/test_stdio_integration.py
git commit -m "[feature] (weather-agents) Test the MCP client against the real stdio server"
```

---

### Task 5: Check the docs against what was built

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update the architecture doc**

Use the `writing-architecture` skill in update mode on `docs/architecture.md`. Check these lines against the code that now exists, and change only what drifted:

- The `mcp_client` row in the module table says Planned. It is Built for level 1 over stdio: it reads an `mcpServers` file, opens one session per server, routes by name, and names the server in every failure. The row must also say that sampling, elicitation, log, and progress handlers are not built.
- The `mcp.stdio.json, mcp.http.json` row in the interfaces table. `mcp.stdio.json` exists with one `open-meteo` entry. `mcp.http.json` is still Planned.
- The `mcp_client` description says it "keeps it open for the chat". That holds until the pool closes. Keep it.
- The "Assumed" entry that the MCP client pins `mode="legacy"`: it is still only settled once the dossier samples successfully. Leave it.

Do not edit `docs/prd/0001-open-meteo-mcp-server-and-client.md`. Its `Status` stays `Building`. Do not edit `docs/vision.md` or any ADR.

- [ ] **Step 2: Verify nothing else mentions the old state**

Run: `rg -n "mcp_client|mcp.stdio.json" docs/architecture.md`
Expected: each hit agrees with the code.

- [ ] **Step 3: Run the suite once more**

Run: `make test`
Expected: 148 passed, 31 deselected.

- [ ] **Step 4: Commit**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/weather-agents-mcp-client-level-1
git add packages/weather-agents/docs/architecture.md
git commit -m "[docs] (weather-agents) Mark the level 1 MCP client as Built in the architecture doc"
```

---

## Self-review notes

- **Spec coverage:** layout, config (all five error cases plus the unhashable `type`), session (legacy mode and no callbacks, pagination, `is_error` passthrough, named errors, unwrapped groups), pool (routing, partial startup, unknown name, dropped session, close on exit, `from_file`), integration test (real server, tool error result, two kinds of spawn failure inside a time limit), `mcp.stdio.json`, and the architecture update each map to a task.
- **Not built, by decision:** handlers and notification pass-through, HTTP, `${VAR}` expansion, tool namespacing, timeouts and retries, a CLI, and moving the live tests onto this client.
- **Types:** `SdkClient`, `ClientFactory`, `McpSession`, and `McpClientPool` signatures match across Tasks 2 to 4. The pool's `call_tool(server, name, arguments)` calls the session's `call_tool(name, arguments)`.
