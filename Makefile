.PHONY: help install lint format type-check test pre-commit-verify pre-commit-fix conventional-commits-verify clean

help: ## Show this help message.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies (incl. dev tools) with uv.
	uv sync --all-packages

lint: ## Lint the code with ruff.
	uv run ruff check .

format: ## Format the code with ruff.
	uv run ruff format .

type-check: ## Type-check the code with ty.
	uv run ty check

PACKAGES := $(notdir $(wildcard packages/*))

# Each package runs from its own directory so its [tool.pytest.ini_options] applies.
# One root pytest run is not possible: every package has tests/__init__.py, and they collide.
test: ## Run pytest with coverage for every package, or one with PKG=<name>.
	@set -e; for p in $(or $(PKG),$(PACKAGES)); do \
		echo "==> $$p"; \
		(cd packages/$$p && uv run --locked --package $$p --group dev pytest --cov=src --cov-report=term); \
	done

pre-commit-verify: ## Run every pre-commit hook on all files. Fails if any hook fails or modifies a file (used by CI).
	uv run pre-commit run --all-files --show-diff-on-failure

pre-commit-fix: lint format type-check ## Fix locally: lint, format, and type-check (rewrites files).

conventional-commits-verify: ## Check commits in BASE..HEAD_REF are conventional. Usage: make conventional-commits-verify BASE=origin/main
	scripts/verify-conventional-commits.sh $(or $(BASE),origin/main) $(or $(HEAD_REF),HEAD)

clean: ## Remove caches, coverage reports, build artifacts, and logs (repo-wide).
	find . -path ./.venv -prune -o -path ./.git -prune -o -type d \( \
		-name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o \
		-name '.ty_cache' -o -name 'htmlcov' -o -name '*.egg-info' -o -name '.eggs' \
	\) -exec rm -rf {} +
	find . -path ./.venv -prune -o -path ./.git -prune -o -type f \( \
		-name '*.py[co]' -o -name '*.log' -o -name '.coverage' -o -name '.coverage.*' \
	\) -exec rm -f {} +
	rm -rf build dist
