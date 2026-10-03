---
status: accepted
date: 2026-10-01
tags: [technology]
---

# The MCP server and the MCP client are built on the official `mcp` SDK, not the standalone `fastmcp` package

The plan was to build both the server and the client with FastMCP, until a docs check showed that `fastmcp` 4 had removed server-pushed sampling (`ctx.sample`) and only allows elicitation on legacy-mode connections. The scope doc's location dossier depends on the server asking the client to sample. The user chose the official `mcp` SDK (`MCPServer` and its `Client`) for both sides, because it still supports sampling the way the server needs it.

## Considered options

- `fastmcp` 4 with clients pinned to legacy mode. Rejected: the library itself had dropped push sampling.
- `fastmcp` 4 on the modern protocol, with sampling and elicitation redesigned around `InputRequiredResult`. Rejected for the same reason: sampling would no longer be the server pushing a request.
- Pinning `fastmcp` 3.x. Rejected along with the other FastMCP options.
- The official `mcp` SDK for server and client. Chosen.

## Consequences

- In `mcp` 2.x the client defaults to the 2026-07-28 protocol, where a server cannot send requests to a client. Push sampling and elicitation only work on stateful sessions opened with `Client(..., mode="legacy")`, so our client has to pin that mode. Stateless HTTP and any client on the 2026 protocol always get the fallback paths.
- If the official SDK later drops the legacy handshake, this record is what has to be revisited.
