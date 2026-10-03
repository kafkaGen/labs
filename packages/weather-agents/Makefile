.PHONY: help test test-live inspect

help: ## Show this help message.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## Run the unit and server tests. No network.
	uv run --package weather-agents --group dev pytest

test-live: ## Run the live test against the real Open-Meteo API.
	uv run --package weather-agents --group dev pytest -m live -o addopts=""

inspect: ## Start the server over stdio with MCP Inspector attached. Needs npx.
	uv run --package weather-agents mcp dev src/weather_agents/server/app.py:mcp --with-editable .
