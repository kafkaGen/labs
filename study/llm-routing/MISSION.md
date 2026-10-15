# Mission: Routing in LLM applications and agents

## Why
I want a working mental model of routing in LLM systems, so that when I design an agent I can decide where a routing decision belongs and what it costs. That covers sending a task to the right prompt, agent, or tool, and sending a request to a cheaper or stronger model. Today I know routing exists but not its trade-offs, and I can't predict when it will quietly throw away my prompt cache.

## Success looks like
- Given an agent design, I can say which layer each routing decision belongs in: the application, a model gateway, or the inference server. I can also explain why.
- I can predict, before running it, whether a routing decision keeps or breaks the prompt cache for a conversation, and which part of the prefix breaks.
- I can sketch a routed multi-turn conversation that keeps a high cache hit rate, and check it against the `usage` fields on real API responses.
- I can name the main best practices for routers, such as a cheap classifier, a stable prefix per route, and routing at task boundaries, and back each one with a source.

## Constraints
- Evenings and weekends, a few hours a week, no deadline.
- API spend capped at roughly $10 to $20 a month. Any hands-on exercise uses cheap models.
- Already practises with the Anthropic stack (Claude API, Agent SDK, MCP). Examples default to it.

## Out of scope
- Mixture-of-experts routing inside model weights.
- Training a router model from scratch. Reading how RouteLLM-style routers work is in scope; building one is not.
- Agent frameworks such as LangChain or LangGraph, except as a contrast.
