# Spec Delta

## Purpose

The agent loop is the hand-written cycle on the Claude Messages API that calls the model, runs the tools it asks for, sends their results back, and stops when the model ends its turn.

## ADDED Requirements

### Requirement: The loop calls tools until the model ends its turn
The loop SHALL send the conversation to the model, run every tool the model asks for, send the results back in the next request, and repeat until the model stops with `end_turn`. The answer SHALL be the text of the final model turn.

#### Scenario: Two tool rounds, then an answer
- **GIVEN** a model that asks for a geocoding tool, then a forecast tool, then ends its turn with text
- **WHEN** the loop runs a question
- **THEN** both tools are called in that order, the model gets each result in the following request, and the run returns the final text

#### Scenario: No tool needed
- **GIVEN** a model that ends its first turn with text
- **WHEN** the loop runs a question
- **THEN** no tool is called and the run returns that text after one model call

### Requirement: Tools asked for in one turn run concurrently
When one model turn asks for several tools, the loop SHALL start them all before waiting for any, and SHALL send every result back in one message, in the order the model asked for them.

#### Scenario: Two slow tools overlap
- **GIVEN** a model turn that asks for two tools that each take 200 ms
- **WHEN** the loop runs them
- **THEN** both finish in well under 400 ms, and the next request holds both results in one user message, in the requested order

### Requirement: A tool's own error result goes back to the model as an error
A tool result that the tool provider marks as an error SHALL go back to the model as a tool result flagged as an error, and the run SHALL continue.

#### Scenario: The server rejects an argument
- **GIVEN** a tool call whose result is marked as an error
- **WHEN** the loop sends it back
- **THEN** the model's next request holds that result flagged as an error, and the loop keeps going

### Requirement: The model's turns go back unchanged
The loop SHALL send every assistant turn back to the model exactly as the API returned it, thinking blocks included.

#### Scenario: Thinking blocks survive a tool round
- **GIVEN** a model turn with a thinking block and a tool call
- **WHEN** the loop sends the next request
- **THEN** that request holds the assistant turn with the thinking block unchanged

### Requirement: The loop reaches tools only through the tool-provider interface
The loop SHALL list and call tools only through a tool-provider interface, and SHALL NOT depend on MCP.

#### Scenario: A fake provider drives the loop
- **GIVEN** a tool provider that is not backed by MCP
- **WHEN** the loop runs a question
- **THEN** the loop offers that provider's tools and calls them as it would MCP tools

### Requirement: Every request uses automatic prompt caching
Every model request SHALL ask for automatic prompt caching with the 5-minute lifetime.

#### Scenario: Caching on every request
- **WHEN** the loop makes any model request
- **THEN** the request carries the automatic cache control with the 5-minute lifetime

### Requirement: A run ends normally only on end_turn
Any stop reason other than `end_turn` and `tool_use` SHALL end the run with a run error that names the stop reason. No tool from that turn SHALL run.

#### Scenario: The model runs out of tokens
- **GIVEN** a model turn that stops with `max_tokens` and holds a cut-off tool call
- **WHEN** the loop reads that turn
- **THEN** the run raises a run error naming `max_tokens`, and the cut-off tool is not called

### Requirement: A failing tool call ends the run with a run error
A tool call that raises, rather than returning an error result, SHALL end the run with a run error that names the tool.

#### Scenario: The tool provider raises
- **GIVEN** a tool call that raises an exception
- **WHEN** the loop runs it
- **THEN** the run raises a run error naming the tool and the cause

### Requirement: A failed model call ends the run with a run error
A model call that still fails after the API client's own retries SHALL end the run with a run error that carries the API error as its cause. Only calls to the Anthropic API SHALL be retried.

#### Scenario: The API rejects the key
- **GIVEN** a model call that fails with an authentication error
- **WHEN** the loop makes it
- **THEN** the run raises a run error whose cause is the authentication error

### Requirement: Every run error logs its cause once
Every run error SHALL log its cause once, at the point where it is raised, and nowhere else.

#### Scenario: One log line per failure
- **WHEN** a run raises a run error
- **THEN** exactly one error log record names its cause
