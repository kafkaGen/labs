---
status: accepted
date: 2026-10-16
tags: [structure, constraint]
---

# Both agent runtimes share the MCP tools and the prompts, and Anthropic's server tools run only on the API runtime

Supersedes [ADR-0001](0001-two-agent-runtimes-over-one-tool-layer.md).

The agent layer is still built twice, on the Claude API and the Claude Agent SDK, selected when the CLI starts, over the same MCP tools and the same prompts. The API runtime also gets Anthropic's server tools: web search, web fetch, code execution, tool search, and programmatic tool calling, which exist only on the Messages API. ADR-0001 said anything one runtime offers and the other does not stays unused. The user decided that rule no longer holds for these tools, because they are part of the stack this project exists to learn, and keeping the runtimes identical would mean never learning them.

## Considered options

- Keep ADR-0001 as written and leave the server tools out. Rejected: the server tools would never be learned.
- Share the MCP tools and prompts, and let the server tools run on the API runtime only. Chosen.

## Consequences

- The vision's success criterion, that the same conversation runs correctly under both runtimes, now holds only for questions the MCP tools can answer. A question that needs web search or code execution can differ between runtimes by design.
- The MCP tools and the prompts still cannot lean on either runtime's conveniences. The exception covers Anthropic's server tools and nothing else.
