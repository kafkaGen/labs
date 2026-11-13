# Spec Delta

## Purpose

Runs one weather question to a structured answer on the Claude Messages API, using the tools of every configured MCP server, inside a per-request USD cap and deadline, and leaves logs that explain the run afterwards.

## ADDED Requirements

### Requirement: The agent offers the model every open MCP server's tools
A run SHALL offer the model every tool of every MCP server that opened from the MCP config file, under its `<server>__<tool>` name. When no server opens, the run SHALL go ahead with no MCP tools, and the log SHALL name each server that failed.

#### Scenario: A question that needs weather data uses the MCP tools
- **WHEN** a caller asks "What is the weather in Lviv tomorrow?" and the `open-meteo` server is open
- **THEN** the model is offered the `open-meteo__*` tools, and the answer is built from their results

#### Scenario: No MCP server opens
- **WHEN** every server in the MCP config file fails to open
- **THEN** the run still calls the model, with no MCP tools, and the log names each failed server

### Requirement: MCP tools carry their server's schema, and the server validates arguments
Every MCP tool SHALL be offered to the model as a non-strict tool, with its server's input schema unchanged. The run SHALL NOT validate tool arguments itself. The MCP server SHALL be the only judge of an argument's type, presence and range.

#### Scenario: A tool keeps its latitude range
- **WHEN** a server tool's schema gives `latitude` a `minimum` of -90 and a `maximum` of 90
- **THEN** the tool is offered to the model with that schema, limits included, and not marked strict

#### Scenario: An out-of-range argument comes back from the server
- **WHEN** the model calls that tool with `latitude` 120
- **THEN** the server's validation error reaches the model as an error result, and the run continues

#### Scenario: A wrongly typed argument comes back from the server
- **WHEN** the model calls that tool with `latitude` as the string "north"
- **THEN** the call still goes to the server, its validation error reaches the model as an error result, and the run continues

### Requirement: Tool calls from one model turn run concurrently
When one model turn asks for several tool calls, the run SHALL start them all without waiting for each other. All their results SHALL go back to the model together in the next request, one result per call.

#### Scenario: Two tool calls in one turn
- **WHEN** one model turn asks for `open-meteo__forecast` for Lviv and for Kyiv
- **THEN** both calls are in flight at the same time, and the next model request carries both results in one message

### Requirement: A failed tool call goes back to the model as an error result
A tool call that raises, or that the server returns as an error, SHALL go back to the model as an error result for that call. The run SHALL continue.

#### Scenario: The server returns an error result
- **WHEN** a tool call returns a result marked as an error
- **THEN** the model receives it as an error result, and the next model call happens

#### Scenario: The tool call itself fails
- **WHEN** calling a tool raises, for example because its server is gone
- **THEN** the model receives an error result naming the failure, and the run continues

### Requirement: The run ends normally only on end_turn
The run SHALL end with a result only when the model stops with `end_turn`. A stop with `tool_use` or `pause_turn` SHALL continue the loop with another model call.

#### Scenario: pause_turn continues the loop
- **WHEN** a model call stops with `pause_turn`
- **THEN** the run sends the conversation back to the model without adding a user turn, and continues

#### Scenario: end_turn ends the run
- **WHEN** a model call stops with `end_turn`
- **THEN** the run returns its structured answer

### Requirement: Any other stop reason raises a run error
A model stop with `max_tokens`, `stop_sequence`, `refusal` or `model_context_window_exceeded` SHALL raise a run error the caller can catch. The error SHALL name the stop reason and carry the run's usage, its cost, and any partial answer text.

#### Scenario: The model hits max_tokens
- **WHEN** a model call stops with `max_tokens`
- **THEN** the caller catches a run error whose stop reason is `max_tokens`, with the tokens used, the cost so far, and the text written so far

#### Scenario: The model refuses
- **WHEN** a model call stops with `refusal`
- **THEN** the caller catches a run error whose stop reason is `refusal`, and no tool from that turn runs

### Requirement: The result is a structured answer with its resources
A successful run SHALL return an answer text and a list of resources. Each resource SHALL carry a short title and name its source: either a URL, or an MCP tool call with its tool name and arguments.

#### Scenario: An answer built from one tool call
- **WHEN** the run answers from one `open-meteo__forecast` call
- **THEN** the result's answer is the text, and its resources include that call with its tool name, its arguments, and a title

### Requirement: Every resource points at something the run touched
Every resource in the result SHALL match a tool call the run actually made, by tool name and arguments, or a URL that appeared in the run's tool results. A resource the model names that matches nothing SHALL NOT reach the caller, and the log SHALL record that it was dropped.

#### Scenario: The model cites a call it never made
- **WHEN** the model's answer lists a resource for a tool call that did not happen in the run
- **THEN** that resource is dropped from the result, and a log line names it

### Requirement: No model call starts once the request's USD cap is reached
Each request SHALL have a USD cap, $0.10 by default, counted from every model call in that request at the model's prices. No model call SHALL start once the cost has reached the cap, so the cap is overshot by at most the one call already in flight. Reaching the cap SHALL raise a run error that names the cap as the limit.

#### Scenario: The cap stops the loop between calls
- **WHEN** the cost after a model call that asked for tools has reached the cap
- **THEN** the tools of that turn do not lead to another model call, and the caller catches a run error naming the USD cap

#### Scenario: The cap applies to each request, not the session
- **WHEN** two requests in one session each spend $0.06 under a $0.10 cap
- **THEN** both requests complete

### Requirement: A model with no price entry fails before any model call
The run SHALL fail before any model call when the configured model has no entry in the package's price table, because the USD cap could not be enforced. The error SHALL name the model.

#### Scenario: An unpriced model
- **WHEN** settings choose a model that is missing from the price table
- **THEN** the request fails with an error naming that model, and no model call is made

### Requirement: Each request stops at its deadline
Each request SHALL have a deadline, 120 seconds by default, measured from the start of the request. When it passes, the in-flight model call and tool calls SHALL be cancelled, and a run error naming the deadline as the limit SHALL reach the caller.

#### Scenario: A slow tool call outlives the deadline
- **WHEN** a tool call is still running when the deadline passes
- **THEN** the tool call is cancelled, and the caller catches a run error naming the deadline

### Requirement: Every log line of a run names its session
Every log line written during a run SHALL carry the run's session id.

#### Scenario: Lines from the loop and from tool calls
- **WHEN** a run makes a model call and a tool call
- **THEN** each log line about either carries the same session id

### Requirement: Each step is traceable from the debug log
At debug level, each step SHALL log the input sent to the model, the model's output, each tool call with its arguments, and each tool result. Each step SHALL also log the tokens used so far and the time left before the deadline.

#### Scenario: One tool round at debug level
- **WHEN** a run with one tool round finishes at debug level
- **THEN** the log holds the model input, the model output, the tool call and its arguments, and the tool result, each with tokens so far and time left

### Requirement: Logged values are cut to the truncation length
Each logged model input, model output, tool argument set and tool result SHALL be cut to the truncation length, 200 characters by default. A cut value SHALL say that it was cut.

#### Scenario: A long tool result
- **WHEN** a tool result is 5,000 characters long and the truncation length is 200
- **THEN** the log shows its first 200 characters and marks the value as truncated

### Requirement: The end of a run logs its totals
At info level, the end of every run, successful or not, SHALL log total tokens, cost, elapsed time against the deadline, the number of tool calls, and the number of turns. A turn is one model call. A run error SHALL log its cause once, where it is raised.

#### Scenario: A successful run with two turns
- **WHEN** a run makes two model calls and one tool call and then ends
- **THEN** one info line reports its tokens, cost, elapsed time and deadline, 1 tool call, and 2 turns
