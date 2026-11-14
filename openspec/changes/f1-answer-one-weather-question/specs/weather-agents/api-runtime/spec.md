# Spec Delta

## Purpose

The API runtime is what a caller uses to ask the weather agent a question on the Claude Messages API: it opens the MCP servers, runs the agent loop over their tools, and returns the answer with a session id.

## ADDED Requirements

### Requirement: The runtime opens every configured MCP server
Opening the runtime SHALL open every server in the MCP config file named by settings, and SHALL offer the model every tool of every server that opened, named `<server>__<tool>`.

#### Scenario: Tools from the config reach the model
- **GIVEN** an MCP config with one server named `open-meteo` that lists a tool `forecast`
- **WHEN** the caller opens the runtime and sends a question
- **THEN** the first model request offers a tool named `open-meteo__forecast` with that server's description and input schema

#### Scenario: Only servers that opened contribute tools
- **GIVEN** an MCP config with two servers, one of which fails to start
- **WHEN** the caller opens the runtime and sends a question
- **THEN** the run goes ahead with the tools of the server that opened

### Requirement: Sending a question returns the answer and a new session id
`send` SHALL take one question and return a result holding the answer text and a session id. Each `send` in this change SHALL start a new session with a new, unique id.

#### Scenario: One question, one answer
- **WHEN** the caller sends "what's the weather in Lviv tomorrow?"
- **THEN** the result holds the model's final answer text and a non-empty session id

#### Scenario: Two sends get two sessions
- **WHEN** the caller sends two questions
- **THEN** the two results carry different session ids

### Requirement: Closing the runtime closes the MCP servers
`close` SHALL close every MCP session the runtime opened. Leaving the runtime's async context SHALL close it the same way.

#### Scenario: Leaving the context closes the servers
- **WHEN** the caller leaves the runtime's `async with` block
- **THEN** every MCP session it opened is closed

### Requirement: The runtime passes no MCP client handlers
The runtime SHALL open MCP sessions without sampling, elicitation, progress, or log handlers.

#### Scenario: No client capabilities are declared
- **WHEN** the runtime opens its MCP sessions
- **THEN** no sampling, elicitation, progress, or log handler is passed to the MCP client

### Requirement: Run errors reach the caller
A run that cannot produce an answer SHALL raise a run error from `send` that the caller can catch as one exception type. The runtime SHALL stay usable for the next `send`.

#### Scenario: A failed run leaves the runtime usable
- **GIVEN** a run that raises a run error
- **WHEN** the caller sends another question
- **THEN** the second question is answered normally
