# Design: MCP client, level 1

**Date:** 2026-10-03
**Implements:** use case 4 of [PRD-0001](../../prd/0001-open-meteo-mcp-server-and-client.md), without its handler criteria (see Out of scope).
**Built on:** the official `mcp` 2.x SDK ([ADR-0003](../../adr/0003-official-mcp-sdk-over-fastmcp.md)). This is a thin layer over the SDK's `Client`. It writes no protocol code.
**Fits:** the `mcp_client` module in [`architecture.md`](../../architecture.md).

## Goal

A Python caller opens a pool of MCP servers from a Claude Code `mcpServers` file, lists and uses their tools, resources, resource templates, and prompts over stdio, and closes the pool when done. The client knows nothing about weather.

## Package layout

New files under `packages/weather-agents/`:

```
mcp.stdio.json                  one "open-meteo" entry that starts the server with uv
src/weather_agents/mcp_client/
    __init__.py                 exports McpClientPool, McpClientError, ConfigError, load_config
    errors.py                   McpClientError(server, cause), ConfigError
    config.py                   StdioServerConfig, load_config(path)
    session.py                  McpSession: one server, one SDK Client
    pool.py                     McpClientPool: opens every configured server, routes by name
tests/client/
    test_config.py  test_session.py  test_pool.py  test_stdio_integration.py
```

`mcp_client` imports nothing from `weather_agents.server`. No dependency is added.

## Config

- File format: `{"mcpServers": {"<name>": {"command", "args", "env"}}}`, as in Claude Code.
- `type` is optional and defaults to `stdio`. A module constant `SUPPORTED_TYPES = {"stdio"}` lists what the loader accepts. Level 2 adds `http`.
- `StdioServerConfig` is a pydantic model with `extra="forbid"`: `command: str`, `args: list[str] = []`, `env: dict[str, str] | None = None`, `type: Literal["stdio"] = "stdio"`.
- `load_config(path) -> dict[str, StdioServerConfig]` raises `ConfigError`, which names the server where one applies, for:
  - a missing file or invalid JSON (names the path)
  - a missing `mcpServers` key
  - a `type` outside `SUPPORTED_TYPES` (`server 'x': type 'http' is not supported, supported: stdio`)
  - an unknown key in an entry
- A config error fails the whole load. It is a mistake in the file, not a server that is down.
- There is no `${VAR}` expansion. The architecture ties it to HTTP headers, so it arrives with level 2.

## Session

`McpSession(name, config, *, client_factory=Client)` is an async context manager over one SDK client.

- The factory is called as `client_factory(StdioServerParameters(...), mode="legacy")` and nothing else. `mode="legacy"` is pinned by ADR-0003. No sampling, elicitation, list-roots, logging, or message callbacks are passed, so the SDK declares none of those capabilities. A unit test asserts the call has no callback arguments.
- `list_tools()`, `list_resources()`, `list_resource_templates()`, and `list_prompts()` follow `next_cursor` until it is empty and return flat lists of the SDK's types (`list[Tool]`, `list[Resource]`, `list[ResourceTemplate]`, `list[Prompt]`).
- `call_tool(name, arguments)`, `read_resource(uri)`, and `get_prompt(name, arguments)` return the SDK result unchanged (`CallToolResult`, `ReadResourceResult`, `GetPromptResult`). A tool result with `is_error=True` is a normal return. The agent loop feeds it back to the model.
- Spawn failures, a dead session, and protocol errors raise `McpClientError(server, cause)`, chained from the original with `from`. The message starts with the server name.
- What the SDK raises, probed on `mcp` 2.x on 2026-10-03:
  - A command that does not exist raises a plain `FileNotFoundError` (an `OSError`) from entering the client.
  - A child that exits at once, or dies mid-session, raises `MCPError(-32000, "Connection closed")`. Nothing hangs.
  - Entering the client wraps that `MCPError` in nested `ExceptionGroup`s, so the session unwraps to the first leaf before it names the cause. It catches `OSError`, `MCPError`, and `ExceptionGroup`, never `BaseExceptionGroup` (which would swallow cancellation) and never bare `Exception`.
  - A call that fails on a dead session raises the bare `MCPError`. Once the session turns it into a `McpClientError` and the caller catches it, closing the session raises nothing.
- SDK result fields are snake_case (`is_error`, `next_cursor`, `resource_templates`, `uri_template`), not the wire names.
- No retries. No timeouts, because the PRD sets no timeout numbers.

## Pool

`McpClientPool(servers: dict[str, StdioServerConfig], *, client_factory=Client)` is an async context manager. `McpClientPool.from_file(path)` is a classmethod that calls `load_config`.

- On enter, it opens one `McpSession` per server, in the file's order, on one `AsyncExitStack`.
- A server that fails to open is recorded in `pool.failures: dict[str, McpClientError]` and left out of the open set. The other servers still open. This follows the chosen partial-startup policy: a broken server does not block the rest.
- `pool.server_names` lists the open servers.
- Every method takes the server name first and delegates to that server's session: `pool.call_tool("open-meteo", "forecast", args)`, `pool.list_tools("open-meteo")`, and so on. The seven delegating methods repeat the session's signatures. Repeating them beats a dynamic `__getattr__` proxy, which would hide the API from the type checker.
- A call to a server in `failures` raises that recorded error. A call to a name not in the file raises `McpClientError(name, "no such server")`.
- If a session drops mid-run, calls to that server raise `McpClientError`. The other servers keep working.
- On exit, the stack closes every open session.
- For a model, the pool adds two methods (added after review). `list_all_tools()` returns every open server's tools as the SDK's `Tool`, with `name` changed to `<server>__<tool>` and `input_schema` left as the server's JSON Schema. `call_namespaced_tool(name, arguments)` splits the name at the first `__`, so a tool name may hold `__`. A server name may not, and the pool rejects one with `ConfigError` when it is built. A name with no server part or no tool part, or a server that is not open, raises `McpClientError`. The per-server methods stay as they are. The pool does not check provider limits on tool name length or characters.

**Limit.** The SDK's `Client` runs a task group, so the same task must open and close the pool. That holds for tests and a plain `async with`. The Textual app will have to open and close it in one task.

## Tests

| Layer | What it covers | Upstream |
|---|---|---|
| `test_config.py` | Valid file, default `type`, unsupported `type`, unknown key, missing file, bad JSON, missing `mcpServers`. Loads the shipped `mcp.stdio.json`. | Files in `tmp_path` |
| `test_session.py` | Pagination over several pages, each method delegates, `is_error` result returned as it is, SDK failures wrapped with the server name, factory called with `mode="legacy"` and no callbacks. | A fake client passed as `client_factory` |
| `test_pool.py` | Routing by name, partial startup with `failures` filled, a call to a failed server, an unknown name, one session dropping while another works, all sessions closed on exit. | Fake clients |
| `test_stdio_integration.py` | Our pool against the real stdio server, with a config written to `tmp_path` that uses `sys.executable`. Lists 11 tools, 2 prompts, the guide resource, and the endpoint template. Reads the guide and gets `weekend_check`. Calls `forecast` with latitude 95 and gets `is_error=True` with no network call. A nonexistent command, and a child that exits at once, each fail with an error naming the server inside a fixed time limit. | The real server. No network. |

- `make test` runs all of it. The shipped `mcp.stdio.json` is parsed only, not spawned, because it starts the server through `uv`.
- The existing live tests stay on the SDK's `Client`.

## Docs and files

- `mcp.stdio.json`: `{"mcpServers": {"open-meteo": {"command": "uv", "args": ["run", "--package", "weather-agents", "python", "-m", "weather_agents.server"]}}}`.
- `architecture.md`: the `mcp_client` module row and the config-files row change from Planned to Built for level 1 stdio, and the row says handlers are not built. The PRD is not edited. Its `Status` stays `Building`.

## Deviations from the PRD

PRD use case 4 lists a caller-supplied sampling and elicitation handlers criterion, and a progress and log pass-through criterion. This spec builds neither, by the user's decision, because the level 1 server never sends them. Both stay open on the PRD. The declared-capabilities half of the first criterion holds by construction and is tested: with no handlers, the client declares none.

## Out of scope

Sampling, elicitation, log and progress handlers. HTTP entries and transport. `${VAR}` expansion. Timeouts and retries. A CLI or terminal driver. Moving the live tests onto this client.
