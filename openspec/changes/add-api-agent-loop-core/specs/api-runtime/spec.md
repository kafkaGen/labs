# Spec Delta

## Purpose

Gives callers one `AgentRuntime` contract on the Claude API: send a question with an optional session id, get a structured answer and the session id back, and forget sessions on demand. Conversations live in memory only.

## ADDED Requirements

### Requirement: The runtime offers send, clear and close
The API runtime SHALL implement the `AgentRuntime` interface with three operations: `send` takes a question and an optional session id and returns a result. `clear` takes a session id and forgets that session. `close` forgets every session and releases the runtime's MCP connections.

#### Scenario: A caller uses the runtime through the interface
- **WHEN** a caller holds the API runtime as an `AgentRuntime` and calls `send`, `clear` and `close`
- **THEN** each works without the caller knowing the runtime is the API one

### Requirement: A question without a session id starts a new session
`send` without a session id SHALL start a new session, and the result SHALL carry that session's id.

#### Scenario: A first question
- **WHEN** a caller sends "What is the weather in Lviv tomorrow?" with no session id
- **THEN** the result carries a new session id along with the structured answer

### Requirement: A follow-up continues its session
`send` with a session id the runtime holds SHALL run with that session's earlier questions and answers in view. The result SHALL carry the same session id.

#### Scenario: A follow-up question
- **WHEN** a caller sends "and the day after?" with the session id from the Lviv question
- **THEN** the answer is about Lviv two days ahead, and the result carries the same session id

### Requirement: An unknown session id fails before any model call
`send` with a session id the runtime does not hold SHALL fail before any model call, with an error naming the id. This covers a mistyped id, a cleared session, and an id from an earlier process.

#### Scenario: A cleared session
- **WHEN** a caller clears a session and then sends a question with its id
- **THEN** the call fails with an error naming that id, and no model call is made

### Requirement: A failed request leaves its question and its error in the session
When a request in a session raises a run error, the session SHALL keep the user's question and record the run error as the assistant's answer to it. The failed request's partial assistant turns and tool turns SHALL NOT be kept.

#### Scenario: The next request sees what failed
- **WHEN** a request hits its deadline after one tool round, and the caller sends a follow-up in the same session
- **THEN** the history sent to the model holds the failed question and an assistant answer describing the deadline error, and none of the failed request's tool calls or results

### Requirement: A successful request keeps its full exchange
When a request ends with a result, the session SHALL keep the question and every assistant and tool turn of that request, so later requests see the tool results as well as the answer.

#### Scenario: A follow-up can reuse an earlier tool result
- **WHEN** a request looked up Lviv's coordinates, and the next request in the session asks about Lviv again
- **THEN** the history sent to the model includes the earlier tool call and its result

### Requirement: Sessions live only in memory
A session's history SHALL live only in the runtime's memory. Nothing SHALL write it to a file, a database or any other store. Sessions SHALL end on `clear`, on `close`, or when the process exits.

#### Scenario: close forgets every session
- **WHEN** a caller closes the runtime and then sends with an earlier session id to a new runtime
- **THEN** the call fails with an error naming the unknown id
