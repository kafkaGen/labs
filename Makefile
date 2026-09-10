.PHONY: help install lint format type-check pre-commit clean

help: ## Show this help message.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies (incl. dev tools) with uv.
	uv sync --all-packages

lint: ## Lint the code with ruff.
	uv run ruff check .

format: ## Format the code with ruff.
	uv run ruff format .

type-check: ## Type-check the code with ty.
	uv run ty check

# test: ## Run the unit test suite with pytest.
# 	uv run pytest
# There are no tests yet. Add `pytest` as a dev dependency, write tests under
# tests/, then uncomment this target (and add `test` to `pre-commit` below).

pre-commit: lint format type-check ## Run lint, format, and type-check (same checks as the pre-commit hooks).

clean: ## Remove caches, coverage reports, build artifacts, and logs (repo-wide).
	find . -path ./.venv -prune -o -path ./.git -prune -o -type d \( \
		-name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o \
		-name '.ty_cache' -o -name 'htmlcov' -o -name '*.egg-info' -o -name '.eggs' \
	\) -exec rm -rf {} +
	find . -path ./.venv -prune -o -path ./.git -prune -o -type f \( \
		-name '*.py[co]' -o -name '*.log' -o -name '.coverage' -o -name '.coverage.*' \
	\) -exec rm -f {} +
	rm -rf build dist
