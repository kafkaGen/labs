# Spec Delta

## Purpose

One settings object holds every knob of the agent layer, so a value is set in one place and a bad value fails early with the field it belongs to.

## ADDED Requirements

### Requirement: Settings load in a fixed order
Settings SHALL take each value from, in rising priority: the default in code, then `.env` and the environment, then overrides passed for one run.

#### Scenario: The environment beats the default
- **GIVEN** the model is set in the environment
- **WHEN** settings load
- **THEN** the model is the environment's value, not the default

#### Scenario: An override beats the environment
- **GIVEN** the model is set in the environment
- **WHEN** settings load with a model override for one run
- **THEN** the model is the override

### Requirement: The defaults answer a weather question
With nothing set but the API key, settings SHALL select Claude Haiku 5.5 as the model and the package's stdio MCP config file as the MCP config.

#### Scenario: Default model
- **WHEN** settings load with only the API key set
- **THEN** the model is `claude-haiku-5-5`

### Requirement: An invalid value fails at load and names the field
A value that does not fit its field SHALL fail when settings load, before any model call, with an error that names the field. The error SHALL NOT include the value of a secret.

#### Scenario: A bad max_tokens
- **GIVEN** `max_tokens` is set to `-5`
- **WHEN** settings load
- **THEN** loading fails with an error naming `max_tokens`

#### Scenario: A missing API key
- **GIVEN** no API key is set anywhere
- **WHEN** settings load
- **THEN** loading fails with an error naming the API key field

#### Scenario: A missing MCP config file
- **GIVEN** the MCP config path points at a file that does not exist
- **WHEN** settings load
- **THEN** loading fails with an error naming the MCP config field

### Requirement: Secrets never reach a log or an error message
The API key SHALL be held so that printing, logging, or formatting the settings never shows its value.

#### Scenario: Printing settings
- **WHEN** the settings object is printed
- **THEN** the API key's value does not appear in the output
