# Spec Delta

## Purpose

Holds every knob the agent reads in one settings object, so its model and limits change through `.env`, the environment, or per-run overrides, without code changes.

## ADDED Requirements

### Requirement: Settings come from defaults, then .env and the environment, then per-run overrides
The agent's settings SHALL load from defaults in code, overridden by `.env` and the environment, overridden in turn by values passed for one run. A later source SHALL win over an earlier one, field by field.

#### Scenario: An environment variable overrides a default
- **WHEN** the environment sets the USD cap to 0.05
- **THEN** a run uses a $0.05 cap

#### Scenario: A per-run override wins over the environment
- **WHEN** the environment sets the deadline to 60 seconds and the caller passes 30 seconds for one run
- **THEN** that run uses a 30 second deadline

### Requirement: Settings cover the fields the core loop reads, with fixed defaults
Settings SHALL cover the model, the deadline, the USD cap, the maximum output tokens per model call, the MCP config file, the log level, and the debug log truncation length. The defaults SHALL be Haiku 5.5, 120 seconds, $0.10, `mcp.stdio.json`, and 200 characters.

#### Scenario: No overrides
- **WHEN** settings load with no `.env`, no environment overrides, and no per-run values
- **THEN** the model is Haiku 5.5, the deadline 120 seconds, the cap $0.10, the MCP config `mcp.stdio.json`, and the truncation length 200 characters

### Requirement: An invalid value fails when settings load
A setting with an invalid value SHALL fail when settings load, before any run starts, with an error naming the field.

#### Scenario: A negative cap
- **WHEN** the environment sets the USD cap to -1
- **THEN** loading settings fails with an error naming the USD cap field

#### Scenario: A zero deadline
- **WHEN** a per-run override sets the deadline to 0
- **THEN** loading settings fails with an error naming the deadline field

### Requirement: The API key comes only from .env or the environment
The Anthropic API key SHALL be read from `.env` or the environment, never from a per-run override or a config file, and SHALL never appear in a log line.

#### Scenario: A run at debug level
- **WHEN** a run logs at debug level
- **THEN** no log line contains the API key
