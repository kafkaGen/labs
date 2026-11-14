# Backlog: API runtime

**Serves:** "the agent layer implemented twice, once on the Claude API" from the goal in [`../vision.md`](../vision.md), and the in-scope line on two interchangeable agent runtimes. Anthropic's server tools run on this runtime only, per [ADR-0004](../adr/0004-anthropic-server-tools-only-on-the-api-runtime.md).
**In one line:** A hand-written agent loop on the Claude Messages API, wrapped as the API runtime, that answers weather questions in in-memory sessions with our MCP tools and Anthropic's server tools, inside a deadline and a USD cap per request, and returns a structured answer with its sources.

## Rules

- The caller is any Python code that uses the runtime: tests and scripts now, the Textual chat later. This area has no UI of its own.
- The runtime keeps `send`, `clear`, and `close` from the architecture's `AgentRuntime` interface, with a session id added to `send` and `clear`.
- The loop reaches tools through a tool-provider interface, and PRD-0001's MCP client fills it as built. The loop passes none of the client's sampling, elicitation, progress, or log handlers.
- The loop never runs commands on my machine. Shell work happens only in Anthropic's sandbox.
- Only calls to the Anthropic API ever retry. MCP tool calls and Open-Meteo keep PRD-0001's no-retry rule.
- A run ends normally only on `end_turn`. Every other stop is a run error the caller can catch.
- Every request uses automatic prompt caching with the 5-minute lifetime.
- Every knob lives in one settings object, read from defaults, then `.env` and the environment, then overrides passed for one run. An invalid value fails when settings load and names the field.
- A setting that cannot work, for the chosen model or with the other settings, fails before any model call and names the setting.
- Every run error logs its cause once, where it is raised.
- Each feature ships offline tests against a faked API. `live` tests against the real API and MCP server run only by hand.

## Index

| ID | Feature | Status | Depends on | Change |
|----|---------|--------|------------|--------|
| F1 | Answer one weather question | building | | `f1-answer-one-weather-question` |
| F2 | Continue a session | todo | F1 | |
| F3 | Traceable run logs | todo | F1 | |
| F4 | Tool failures reach the model | todo | F1 | |
| F5 | Structured answer with sources | todo | F1 | |
| F6 | Stop reasons as run errors | todo | F2 | |
| F7 | Per-request USD cap | todo | F6 | |
| F8 | Per-request deadline | todo | F6 | |
| F9 | Streamed runs | todo | F6 | |
| F10 | API retries | todo | F8, F9 | |
| F11 | Context compaction | todo | F2 | |
| F12 | Model behaviour settings | todo | F7, F9 | |
| F13 | Sandboxed code execution | todo | F7, F9 | |
| F14 | Web search and fetch | todo | F5, F7, F9 | |
| F15 | MCP tools found by search | todo | F1 | |
| F16 | MCP tools called from code | todo | F5, F13 | |

## Features

### F1 Answer one weather question

A caller sends one weather question through the API runtime and gets back the answer text and a new session id. The runtime opens every server in the MCP config file, offers the model all their tools, and calls them until the model ends its turn.

- The default model is Haiku 5.5.
- When one model turn asks for several tools, they run concurrently and all their results go back in the next request.

**Done when:** a live question such as "what's the weather in Lviv tomorrow?" returns an answer built from MCP tool results, with a session id.

### F2 Continue a session

Sending a session id with the next question continues that conversation with everything said earlier in view.

- Every result in a session carries the same session id.
- A session id the runtime does not hold, whether mistyped, cleared, or from an earlier process, fails before any model call with an error naming the id.
- `clear` forgets one session and `close` forgets them all. Sessions also end when the process exits.
- History lives only in memory. Nothing writes it to a file, a database, or any other store.

**Done when:** "and the day after?" sent with the earlier session id is answered for the same place.

### F3 Traceable run logs

After a run that failed or surprised me, its logs alone show what the agent did at each step, without re-running it with prints added.

- Every log line of a run names its session id.
- At debug level, each step logs the input sent to the model, the model's output, each tool call with its arguments, each tool result, and the tokens used so far.
- Each logged value is cut to the truncation length, 200 characters by default, and the log says it was cut.
- At info level, the end of a run logs total tokens, elapsed time, the number of tool calls, and the number of turns. A turn is one model call.

**Done when:** a debug log of a two-tool run reads as a step-by-step account of the run, with every long value marked as cut.

### F4 Tool failures reach the model

A failing tool or server does not end the run. The model sees what failed and carries on.

- A tool call that fails, or that the server returns as an error, goes back to the model as an error result.
- When no MCP server opens, the run goes ahead without MCP tools, and the log names the servers that failed.

**Done when:** a question with an out-of-range latitude gets an answer that reflects the server's error, and a run with a broken config entry still answers.

### F5 Structured answer with sources

The result is a structured answer the caller can use without parsing prose: the answer text and a list of resources that back it.

- Each resource names its source, either a URL or an MCP tool call with its tool name and arguments, and carries a short title.
- Every resource points at a URL or a tool call the run actually touched.
- The answer's schema and every tool the loop defines itself are strict. MCP tools are strict too, unless settings choose programmatic mode (F16).
- A strict MCP tool whose server schema has limits strict mode cannot express, such as a latitude range, still registers.
- More than 20 strict tools in one request fails before any model call, naming the count.

**Done when:** a weather question returns resources that each match a tool call in the run's log.

### F6 Stop reasons as run errors

Every way a run can stop other than `end_turn` reaches the caller as one catchable run error family, and the session stays usable.

- `tool_use`, `pause_turn`, and `compaction` continue the loop.
- `max_tokens`, `stop_sequence`, `refusal`, and `model_context_window_exceeded` each raise a run error that names the stop reason and carries the usage and any partial text.
- When a request fails, the session keeps the user's question and records the run error as the answer to it. The failed request's partial assistant and tool turns are not kept.

**Done when:** a run forced into `max_tokens` raises a run error naming it, and the next question in that session sees what failed.

### F7 Per-request USD cap

Every request stops before it spends more than its USD cap.

- The default cap is $0.10, applied to each request, not to the session.
- No model call starts once the request's cost has reached the cap. The cap is overshot by at most the one call already in flight.
- Cost counts every model call in the request at that model's prices, including cache writes and reads.
- The price table is maintained by hand in the package. A model with no price entry fails before any model call.
- Run errors carry the cost, and the end-of-run log adds it.

**Done when:** a request with a $0.001 cap raises a run error naming the cap after its first model call.

### F8 Per-request deadline

Every request stops at its deadline, and the caller hears about it promptly.

- The default deadline is 120 seconds, applied to each request.
- When it passes, the in-flight model call and tool calls are cancelled, and the run error reaches the caller within one second, naming the deadline.
- Each step's log adds the time left, and the end-of-run log adds elapsed time against the deadline.

**Done when:** a request with a 2 second deadline against a slow fake tool raises the run error within 3 seconds.

### F9 Streamed runs

The caller can pick a streamed run and watch the agent work, ending with the same structured answer and session id as a plain run.

- The stream carries text deltas, tool input deltas as the model writes them, each tool call when it starts, and each tool result when it returns.
- A streamed and a plain run of the same question go through the same steps, limits, and errors. Only the delivery differs.
- When the run fails, the stream ends with the run error, not a silent close.

**Done when:** a streamed run prints text and tool calls as they happen and ends with the structured answer.

### F10 API retries

A run survives transient API failures and stops at once on terminal ones.

- The SDK keeps its own retries on the initial response, with the retry count taken from settings. The loop retries what the SDK leaves alone: errors that arrive mid-stream, such as an overload, with backoff.
- When a rate-limit error says when the limit resets, the next attempt waits until then.
- No retry waits past the deadline. A retry that would fails at once with the run error.
- Authentication, permission, bad-request, not-found, and request-too-large errors, and a spend-limit rate limit with no reset time, raise the run error at once.
- A streamed run emits a retry event telling the caller to drop the partial output of the failed call, then streams the new attempt.
- Every retry logs the error, the attempt number, and the wait.

**Done when:** a faked mid-stream overload is retried and the run still answers, and a faked authentication error fails on the first attempt.

### F11 Context compaction

A long session, or one question that needs many tool rounds, keeps going past the compaction threshold.

- The default threshold is 100,000 input tokens, counting the session's history.
- After a compaction, the session keeps the compacted history, and later requests start from it.

**Done when:** a session pushed past a low threshold compacts, answers, and answers the next follow-up from the compacted history.

### F12 Model behaviour settings

I tune how the model thinks and how fast it runs through settings, without touching code.

- Settings cover the effort level, adaptive thinking on or off, thinking summaries in the stream, and fast mode.
- Thinking summaries and fast mode are off by default.
- Cost counts fast mode at its prices.
- Fast mode on a model without it fails before any model call.

**Done when:** a streamed run with thinking summaries on shows them, and fast mode on Haiku fails naming the setting.

### F13 Sandboxed code execution

The agent can run code in Anthropic's sandbox to compute over weather data.

- On by default, with a switch in settings.
- Its activity appears in the stream, and its charges count toward the cap.

**Done when:** "average max temperature in Lviv over the next week?" shows a code run in the stream and returns the number.

### F14 Web search and fetch

With the switches on, the agent searches and fetches the web, and the answer still comes back structured, with the URLs it used as resources.

- Web search and web fetch each have a switch, both off by default.
- The answer stays structured when web search ran, even though web search citations and structured output cannot share one request.
- Their activity appears in the stream, and their charges count toward the cap.
- Open: how the structured answer is produced after a web search.

**Done when:** a question that needs current news returns an answer whose resources include the URLs searched or fetched.

### F15 MCP tools found by search

With tool search on, MCP tools are discovered through search rather than all loaded up front, and a question still reaches the tool it needs.

- On by default, with a switch in settings.

**Done when:** with tool search on, a weather question's log shows a search step before the MCP tool call, and the answer is correct.

### F16 MCP tools called from code

With programmatic tool calling on, the model calls MCP tools from code it runs in the sandbox, and those calls return the same results as direct calls.

- Off by default. Turning it on registers MCP tools in programmatic mode instead of strict, because a tool cannot be both.
- Turning it on while code execution is off fails before any model call, naming both settings.
- Tool calls made from code are logged and streamed like direct ones.

**Done when:** a question over several days of data shows MCP calls made from sandbox code in the stream and the log, and the answer matches a direct-call run.
