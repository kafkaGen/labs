# PRD: API agent loop

**Status:** Draft
**In one line:** A hand-written agent loop on the Claude Messages API, wrapped as the API runtime, that answers questions in in-memory sessions with our MCP tools and Anthropic's own tools, inside a deadline and a USD cap per request, and returns a structured answer with its sources.
**Serves:** "the agent layer implemented twice, once on the Claude API" from the goal in [`../vision.md`](../vision.md), and the in-scope line on two interchangeable agent runtimes.

## Why this feature

The MCP server and client from [PRD-0001](0001-open-meteo-mcp-server-and-client.md) work, but nothing drives them: no model sees the tools yet. The loop is the next piece the CLI, the orchestrator, and the SDK runtime comparison all wait on, and writing it by hand is where most of the Messages API I came to learn lives: tool use, stop reasons, streaming, retries, thinking, compaction, caching, and Anthropic's server tools.

## What we build

A caller hands the API runtime a weather question and gets back a structured answer, made of the answer text and the resources that back it, plus a session id. Sending that id with the next question continues the same conversation. Sessions live in memory only, for as long as the runtime is open. In between, the agent calls the tools of every MCP server in the config file, several at once when the model asks for several, and Anthropic's web search, web fetch, code execution, tool search, and programmatic tool calling when settings switch them on. The caller picks a streamed run, which shows text, tool calls, and tool input as they happen, or a plain one that returns only the result. Every request runs under a deadline and a USD cap. It survives transient API failures, stops at once on terminal ones, and logs each step well enough to reconstruct the run afterwards. Every knob lives in one settings object.

## Use cases

The caller is any Python code that uses the API runtime: today the tests and a throwaway script, later the Textual chat.

### 1. A caller asks a question and gets a structured answer

The caller sends one weather question through the API runtime and gets back a structured answer it can use without parsing prose.

**Acceptance criteria**

- The runtime opens every server in the MCP config file and offers the model all their tools. A question that needs weather data gets an answer built from those tools' results.
- A question sent without a session id starts a new session, and the result carries that session's id.
- The result has an `answer` and a list of resources. Each resource names its source, either a URL or an MCP tool call with its tool name and arguments, and carries a short title.
- Every resource points at a URL or a tool call that the run actually touched.
- When one model turn asks for several tools, they run concurrently, and their results all go back to the model in the next request.
- A tool call that fails, or that the server returns as an error, goes back to the model as an error result, and the run continues.
- MCP tools are registered in strict mode unless settings choose programmatic mode. A strict MCP tool whose server schema has limits strict mode can't express, such as a latitude range, still registers. An out-of-range argument still comes back from the server as an error result.
- The run ends normally only on `end_turn`. `tool_use`, `pause_turn`, and `compaction` continue the loop.
- `max_tokens`, `stop_sequence`, `refusal`, and `model_context_window_exceeded` each raise a run error the caller can catch. The error names the stop reason and carries the usage, cost, and any partial text.
- When no MCP server opens, the run still goes ahead without MCP tools. The servers that failed are named in the log.

### 2. A caller continues a conversation by its session id

The caller sends a follow-up question with the session id from an earlier result, and the agent answers with everything said earlier in that session in view.

**Acceptance criteria**

- A follow-up such as "and the day after?" is answered in the context of the session's earlier questions and answers.
- Each result carries the session id, the same one for every request in a session.
- After a compaction, the session keeps the compacted history, and later requests in it start from that history rather than the full one.
- When a request fails, the session keeps the user's question and records the run error as the assistant's answer to it, so the next request sees what failed. The failed request's partial assistant and tool turns are not kept.
- A session id the runtime does not hold, whether mistyped, cleared, or from an earlier process, fails before any model call with an error naming the id.
- `clear` forgets one session. `close` forgets them all. Sessions also end when the process exits.
- A session's history lives only in the runtime's memory. Nothing writes it to a file, a database, or any other store. The debug log's truncated steps are the only trace left behind.
- The runtime keeps `send`, `clear`, and `close` from the architecture's `AgentRuntime` interface, with the session id added to `send` and `clear`.

### 3. A caller streams the run as it happens

The caller asks for a streamed run and receives events while the agent works, ending with the same structured answer and session id as in use case 1.

**Acceptance criteria**

- The stream carries text deltas, tool input deltas as the model writes them, each tool call when it starts, each tool result when it returns, and Anthropic server-tool activity. It ends with the structured answer and the session id.
- Thinking summaries appear in the stream only when settings turn them on. They are off by default.
- A streamed and a non-streamed run of the same question go through the same steps, limits, retries, and errors. Only the delivery differs.
- When a streamed model call fails midway and is retried, the stream first emits a retry event telling the caller to drop the partial output of that call, then streams the new attempt.
- When the run fails, the stream ends with the same run error as in use case 1, not a silent close.

### 4. The agent reaches beyond the MCP tools

With the right settings on, the agent searches and fetches the web, runs code in Anthropic's sandbox, finds tools through tool search, and calls MCP tools from code. The structured answer still comes back with its sources.

**Acceptance criteria**

- Web search, web fetch, code execution, tool search, and programmatic tool calling each switch on and off in settings. Code execution and tool search are on by default. Web search, web fetch, and programmatic tool calling are off.
- A question that needs current web information, with web search on, returns a structured answer whose resources include the URLs it used.
- With tool search on, MCP tools are discovered through search rather than all loaded up front, and a question still reaches the MCP tool it needs.
- With programmatic tool calling on, the model can call MCP tools from code it runs in the sandbox, and those calls return the same results as direct calls.
- Tool calls made from code are logged and streamed like direct ones.
- Turning on programmatic tool calling while code execution is off fails before any model call, with a configuration error naming both settings.

### 5. A long session compacts its context, and every request stays inside its limits

A long session, or one question that needs many tool rounds, keeps going past the compaction threshold. Every request stops at its own deadline or USD cap, whichever comes first.

**Acceptance criteria**

- When a request's input, the session's history included, passes the compaction threshold, the context is compacted and the run continues to an answer. The default threshold is 100,000 input tokens.
- The deadline and the USD cap apply to each request, not to the session as a whole.
- No model call starts once the request's cost has reached its USD cap. The cap is overshot by at most the one model call already in flight. The default cap is $0.10.
- Cost counts every model call in the request at that model's prices, including cache writes and reads, fast mode, and the charges for Anthropic's server tools.
- When the deadline passes, the in-flight model call and tool calls are cancelled, and the run error reaches the caller within one second. The default deadline is 120 seconds.
- A cap or deadline stop raises the same run error family as use case 1, naming which limit stopped it.
- Assumed: the price table is maintained by hand in the package. A model with no price entry fails before any model call, because the USD cap could not be enforced.

### 6. I tune a run through settings

I change the agent's model and behaviour through `.env`, the environment, or overrides passed for one run, without touching code.

**Acceptance criteria**

- Settings cover the model, the effort level, adaptive thinking on or off, thinking summaries in the stream, fast mode, the deadline, the USD cap, the compaction threshold, the API retry count, each Anthropic tool's switch, strict or programmatic mode for MCP tools, the MCP config file, the log level, and the debug log truncation length.
- The defaults are Haiku 5.5, fast mode off, strict MCP tools, a 120 second deadline, a $0.10 cap, 100,000 tokens for compaction, and 200 characters for truncation.
- A setting the chosen model does not support, such as fast mode on a model without it, fails before any model call with an error naming the setting.
- An invalid value, such as a negative cap or an unknown effort level, fails when settings load and names the field.

### 7. I trace a run from its logs

After a run that failed or surprised me, I read its logs and see what the agent did at each step, and how much it spent doing it.

**Acceptance criteria**

- Every log line of a run names its session id.
- At debug level, each step logs the input sent to the model, the model's output, each tool called with its arguments, and each tool result.
- Each of those logged values is cut to the truncation length, 200 characters by default, and the log says it was cut.
- Each step logs the tokens used so far and the time left before the deadline.
- At info level, the end of a run logs total tokens, cost, elapsed time against the deadline, the number of tool calls, and the number of turns. A turn is one model call.
- Every retry logs the error, the attempt number, and how long it waits. Every run error logs its cause once, at the point where it is raised.

## Functional requirements

- **Retries.** Only calls to the Anthropic API are retried. MCP tool calls and Open-Meteo keep PRD-0001's no-retry rule. The SDK keeps the retries it already makes on the initial response, with its retry count taken from settings. The loop retries only what the SDK leaves alone: errors that arrive mid-stream, such as an overload, retried with backoff.
- **Rate limits.** When a rate-limit error says when the limit resets, the next attempt waits until then rather than for the backoff guess.
- **Retries respect the deadline.** No retry waits past the deadline. A retry that would has to fail at once with the run error.
- **Terminal errors.** Authentication, permission, bad-request, not-found, and request-too-large errors, and a spend-limit rate limit with no reset time, raise the run error at once, with no retry.
- **Caching.** Every request uses automatic prompt caching with the 5-minute lifetime. From the second model call in a request on, the usage reports cached input tokens read.
- **Strict schemas.** Every tool the loop defines itself, and the structured answer's schema, are strict. MCP tools are strict unless settings pick programmatic mode, because a tool cannot be both. Assumed: the API's limit of 20 strict tools per request is enough for the MCP servers in use. Crossing it fails before any model call, naming the count.
- **Structured answer.** The answer is always structured, including when web search ran, even though web search citations and structured output cannot share one request. The spec finds how.
- **Tests.** Offline unit tests drive the loop against a faked API and cover every stop reason, retry, terminal error, limit, and stream event. A few `live` tests run by hand against the real API and the real MCP server. The throwaway script is not kept.

## In scope

- The `agent_loop` and `runtimes` modules from [`../architecture.md`](../architecture.md), up to and including the API runtime behind the `AgentRuntime` interface. The `settings` module, for every setting the loop reads.
- In-memory sessions on the API runtime, which own each conversation's history, including its compacted form.
- PRD-0001's MCP client, used as built: it opens the servers, lists their tools for a model, and calls them by prefixed name.
- Anthropic's web search, web fetch, code execution, tool search, and programmatic tool calling. Not the client-side bash tool: code execution's sandboxed bash covers it, and the loop never runs commands on my machine.
- Effort, adaptive thinking, and fast mode, as settings.
- Logging through the workspace's `labs-logging` package.

## Out of scope

- The Textual chat and the `weather-agents chat` command. Comes back in its own PRD, built on this runtime.
- The orchestrator and specialists, running as nested loops on the parent's deadline and cap. Comes back in its own PRD once a single loop works.
- The SDK runtime. Comes back in its own PRD.
- The MCP client's sampling, elicitation, progress, and log handlers. They stay with PRD-0001, and the loop passes none.

## Success criteria

- When a run fails or surprises me, the debug log alone tells me why, without re-running it with prints added.
- I can explain from memory the loop, every stop reason and what the loop does with it, which retries the SDK makes and which the loop adds, programmatic tool calling, and compaction.

## Non-functional requirements

None as a separate section. The numbers this feature introduces (the deadline, the USD cap and its one-call overshoot, the one-second cancellation, the compaction threshold, the truncation length, and the cache lifetime) each belong to one use case or one rule, and are stated there.

## Approach note

- [ADR-0004](../adr/0004-anthropic-server-tools-only-on-the-api-runtime.md) keeps both runtimes on the same MCP tools and prompts, and lets Anthropic's server tools run on the API runtime only.
- [`../architecture.md`](../architecture.md) says "no retries anywhere", and that a hit cap or deadline becomes a visible stop reason rather than an exception. This PRD changes both: API calls retry, and every stop other than `end_turn` is a catchable run error. The doc changes when the loop is built.
- The SDK runtime gets a session id from the Claude Code binary. Returning a session id from every request gives both runtimes the same contract, even though the API runtime has to hold the history itself. The architecture's "API runtime's message list" store becomes one message list per session.
- The loop depends on a tool-provider interface rather than on MCP, as the architecture lays out, and the MCP client's pool fills it.
- The facts this scope rests on, looked up on 2026-10-09 in the Claude platform docs: structured output returns a 400 when citations are on, and web search citations are always on. A tool cannot be both strict and callable from code. The SDK retries 408, 409, 429, and 5xx on the initial response and honours `retry-after`, but never retries an error that arrives mid-stream. The API has no per-request USD cap, so the loop enforces its own. Only Opus 5.5 offers fast mode.
