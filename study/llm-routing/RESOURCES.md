# Routing in LLM applications Resources

## Knowledge

- [Article: "Building effective agents" by Erik S. and Barry Zhang (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
  Defines routing as a workflow pattern next to prompt chaining and orchestrator-workers, with both intent routing and model routing as examples. Use for: what routing is for and when it pays off.
- [Docs: Prompt caching (Claude API)](https://docs.claude.com/en/docs/build-with-claude/prompt-caching)
  The authoritative rules: prefix order `tools` → `system` → `messages`, the invalidation table, TTLs, the 20-block lookback, and minimum lengths. Use for: predicting whether a change breaks the cache.
- [Article: "Context Engineering for AI Agents: Lessons from Building Manus" by Yichao 'Peak' Ji](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
  A production team calls KV-cache hit rate the most important agent metric. Covers keeping the prefix stable, keeping context append-only, and masking tools instead of removing them. Use for: cache-preserving agent design in practice.
- [Docs: Prompt caching (OpenAI)](https://platform.openai.com/docs/guides/prompt-caching)
  Explains that cached state lives on individual machines, so requests must be routed to the machine that holds the prefix (`prompt_cache_key`). Use for: routing at the inference-server layer.
- [Paper: "RouteLLM: Learning to Route LLMs with Preference Data" by Ong et al. (2024)](https://arxiv.org/abs/2406.18665)
  Trains strong/weak model routers from Chatbot Arena preference data and reports over 2x cost reduction at similar quality. Use for: how learned model routers work and what they buy.

- [Article: "How we built our multi-agent research system" (Anthropic)](https://www.anthropic.com/engineering/multi-agent-research-system)
  An Opus lead agent delegates to Sonnet subagents with their own context windows. Multi-agent runs used about 15x the tokens of a chat. Use for: application-layer routing, choosing a model at the delegation boundary.
- [Docs: Router load balancing (LiteLLM)](https://docs.litellm.ai/docs/routing)
  Gateway routing strategies, fallbacks, cooldowns, and `session_affinity` for deployments that don't share a prompt cache. Use for: the gateway layer.
- [Docs: Prompt caching, provider sticky routing (OpenRouter)](https://openrouter.ai/docs/features/prompt-caching)
  How a hosted gateway keeps a conversation on one provider: `session_id`, 10-minute expiry, and how auto routers interact with stickiness. Use for: the gateway layer and the cache.
- [Docs: Automatic Prefix Caching (vLLM)](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html)
  KV cache reuse inside one self-hosted instance, and its limits (it speeds up prefill only). Use for: the server layer.
- [Docs: Kubernetes Gateway API Inference Extension](https://gateway-api-inference-extension.sigs.k8s.io/)
  An endpoint picker that routes requests to replicas using model-server metrics such as prefix cache status. Use for: cache-aware load balancing in self-hosted clusters.

- [Docs: Ticket routing use-case guide (Claude)](https://docs.claude.com/en/docs/about-claude/use-case-guides/ticket-routing)
  A complete worked intent router: category design, a reasoning-then-label prompt, model choice, hierarchical classifiers, success criteria, and an evaluation script. Use for: building and testing a classifier router.
- [Paper: "FrugalGPT" by Chen, Zaharia, Zou (2023)](https://arxiv.org/abs/2305.05176)
  Defines the LLM cascade: query cheap models first and escalate only when the answer is judged unreliable. Use for: the cascade shape of model routing.

## Wisdom (Communities)

- Not yet proposed. Ask the user before adding one.

## Gaps

- None blocking the planned lessons. Lesson 4 runs on the Claude prompt caching docs plus the user's own API calls.
