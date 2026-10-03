# Open-Meteo MCP server, level 1: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the level 1 Open-Meteo MCP server: 11 endpoint tools, 2 prompts, and 2 resources over stdio, debuggable with MCP Inspector.

**Architecture:** An `openmeteo/` layer holds the HTTP client, pure summarising functions, and variable mapping, and imports nothing from `mcp`. Thin tool modules wrap it, resources read sourced markdown files, and prompts return XML-tagged instructions. `create_server()` assembles everything, and tests inject a mock transport and a fixed clock.

**Tech stack:** Python 3.12, official `mcp` 2.x (`MCPServer`), `httpx`, `pydantic`, `pytest` with the `anyio` plugin, `uv`, `ruff`, `ty`.

**Spec:** [`../specs/2026-10-03-mcp-server-level-1-design.md`](../specs/2026-10-03-mcp-server-level-1-design.md). **PRD:** use cases 1, 2, and 3 of [`../../prd/0001-open-meteo-mcp-server-and-client.md`](../../prd/0001-open-meteo-mcp-server-and-client.md).

## Global constraints

- Work in the worktree `.worktrees/mcp-server-level-1`, on branch `weather-agents/mcp-server-level-1`. Every path below is relative to the repo root unless it starts with `cd`.
- Run `pytest` and `make` targets from `packages/weather-agents`. Run `ruff` and `ty` from the repo root.
- Python `>=3.12`. Pin `mcp[cli]>=2,<3`. Add `httpx>=0.28` as our own dependency, because `mcp` 2.x uses `httpx2` internally.
- ruff line length is 100, with the repo's rule set. `ty` must pass. Commit only files under `packages/weather-agents/`, plus the root `uv.lock` in Task 1.
- Nothing writes to stdout in the server: stdout is the protocol. Logging goes to stderr.
- No retries against Open-Meteo. A failure becomes one error result.
- Open-Meteo HTTP timeout is 30 seconds. Ranges: forecast `days` 1 to 16 (hourly 3 at most), ensemble `days` 1 to 15, seasonal `months` 1 to 7, marine and air quality `days` 1 to 7, flood `days` 1 to 92, climate years 1950 to 2049 with 1 to 5 places, elevation 1 to 100 points, geocoding `count` 1 to 100.
- Default tests never call Open-Meteo. Only `make test-live` does.
- Every `##` section in `content/` ends with a `Source: https://open-meteo.com/...` line. Do not add a claim the Open-Meteo documentation does not support.
- Prose in docs and prompts: sentence-case headings, plain words, no em dashes.
- Do not edit `docs/vision.md`, `docs/open-meteo-mcp-scope.md`, or any ADR. The PRD's `Status` line is the only PRD line you may change.

## File structure

Everything lives under `packages/weather-agents/`.

| File | Responsibility |
|---|---|
| `pyproject.toml`, `Makefile` | Package metadata, pytest config, `test`, `test-live`, `inspect` targets |
| `src/weather_agents/server/openmeteo/tables.py` | `Table`, `table_from_block`, `rollup`, `head`, `drop_empty`, `climatology`, `ensemble_stats`, `climate_yearly` |
| `src/weather_agents/server/openmeteo/variables.py` | Logical variable names and their Open-Meteo names |
| `src/weather_agents/server/openmeteo/client.py` | Endpoint URLs, `OpenMeteoClient`, `OpenMeteoError` |
| `src/weather_agents/server/models.py` | Argument types and result models |
| `src/weather_agents/server/state.py` | `AppState`, handed to tools by the lifespan |
| `src/weather_agents/server/tools/common.py` | Error-mapping decorator, `state_of`, `location_of` |
| `src/weather_agents/server/tools/geocoding.py` | `geocode_search`, `geocode_get` |
| `src/weather_agents/server/tools/forecast.py` | `forecast`, `ensemble`, `seasonal` |
| `src/weather_agents/server/tools/history.py` | `historical`, `climate` |
| `src/weather_agents/server/tools/environment.py` | `marine`, `air_quality`, `flood`, `elevation` |
| `src/weather_agents/server/resources.py` | Guide, endpoint template, completion handler |
| `src/weather_agents/server/content/` | `guide.md` and 10 endpoint guides |
| `src/weather_agents/server/prompts.py` | `weekend_check`, `compare_places` |
| `src/weather_agents/server/app.py`, `__main__.py` | `create_server()`, module-level `mcp`, stdio entry point |
| `tests/fakes.py`, `tests/conftest.py` | Response builders, URL router, `client` fixture |
| `tests/unit/`, `tests/server/`, `tests/live/` | Unit, in-memory server, stdio, and live tests |

## Docs check

Docs this plan could make wrong, each with a task at the end:

- `packages/weather-agents/docs/architecture.md`: the MCP server component, the logging row, and the stdio deployment line change from Planned to partly Built. Task 12 uses `writing-architecture` in update mode.
- `packages/weather-agents/docs/prd/0001-open-meteo-mcp-server-and-client.md`: its `Status` line moves to `Building` in Task 1. Nothing else in it changes.
- `packages/weather-agents/docs/open-meteo-mcp-scope.md`: this plan deviates from it in four places (ensemble 15 days, climate to 2049, a standard-deviation spread, a `weekday` list). It is not in the ownership table, so Task 12 reports the deviations to the user and does not edit it.
- No README exists in the package, and no ADR is affected.

---

### Task 1: Scaffold the package

**Files:**
- Create: `packages/weather-agents/pyproject.toml`
- Create: `packages/weather-agents/Makefile`
- Create: empty `__init__.py` files under `src/weather_agents/` and `tests/`
- Modify: `packages/weather-agents/docs/prd/0001-open-meteo-mcp-server-and-client.md:3` (status only)

**Interfaces:**
- Produces: a uv workspace member named `weather-agents` that imports as `weather_agents`, and `make test`, `make test-live`, `make inspect`.

- [ ] **Step 1: Commit the spec and this plan**

```bash
git add packages/weather-agents/docs/superpowers
git commit -m "[docs] (weather-agents) Add level 1 MCP server spec and plan"
```

- [ ] **Step 2: Create `pyproject.toml`**

**`packages/weather-agents/pyproject.toml`**

```toml
[project]
name = "weather-agents"
version = "0.1.0"
description = "Open-Meteo MCP server and weather chat CLI, a study rig for the Anthropic stack."
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28",
    "mcp[cli]>=2,<3",
]

[dependency-groups]
dev = [
    "pytest>=9",
]

[build-system]
requires = ["uv_build>=0.9,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not live'"
markers = [
    "live: calls the real Open-Meteo API",
]
```

- [ ] **Step 3: Create the `Makefile`**

Recipe lines must start with a tab character.

**`packages/weather-agents/Makefile`**

```makefile
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
```

- [ ] **Step 4: Create the package and test directories**

```bash
cd packages/weather-agents
mkdir -p src/weather_agents/server/openmeteo src/weather_agents/server/tools \
  src/weather_agents/server/content/endpoints tests/unit tests/server tests/live
touch src/weather_agents/__init__.py src/weather_agents/server/__init__.py \
  src/weather_agents/server/openmeteo/__init__.py src/weather_agents/server/tools/__init__.py \
  tests/__init__.py tests/unit/__init__.py tests/server/__init__.py tests/live/__init__.py
cd ../..
```

- [ ] **Step 5: Set the PRD status to Building**

In `packages/weather-agents/docs/prd/0001-open-meteo-mcp-server-and-client.md`, change line 3 from `**Status:** Draft` to `**Status:** Building`. Change nothing else in the file.

- [ ] **Step 6: Verify the workspace resolves**

Run: `uv sync --all-packages && uv run --package weather-agents python -c "import weather_agents, mcp, httpx; print('ok')"`
Expected: the sync ends without the earlier `missing a pyproject.toml` error, and the command prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add packages/weather-agents uv.lock
git commit -m "[feature] (weather-agents) Scaffold the package and mark PRD-0001 as Building"
```

`uv.lock` is at the repo root and changes because the workspace gains a member. It is the one file outside the package that this commit touches, and the workspace needs it. If `git status` shows other changes, leave them alone.

---

### Task 2: Tables and summaries

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/openmeteo/tables.py`
- Test: `packages/weather-agents/tests/unit/test_tables.py`

**Interfaces:**
- Produces:
  - `Table(time: list[str], units: dict[str, str], columns: dict[str, list[float | int | None]], weekday: list[str] | None = None)`, a pydantic model.
  - `Agg = Literal["max", "min", "mean", "sum"]`
  - `table_from_block(payload: dict, block: str) -> Table`. Adds `weekday` only when `block == "daily"`.
  - `by_day(stamp) -> str`, `by_month(stamp) -> str`, `by_year(stamp) -> str`
  - `rollup(table, key, how: dict[str, Agg] | None = None, default: Agg = "mean") -> Table`
  - `head(table, rows) -> Table`
  - `drop_empty(table) -> tuple[Table, list[str]]`
  - `climatology(monthly) -> tuple[Table, int]`
  - `ensemble_stats(table) -> Table`
  - `climate_yearly(table, variables: dict[str, Agg], models: Sequence[str]) -> Table`

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/unit/test_tables.py`**

```python
from weather_agents.server.openmeteo.tables import (
    Table,
    by_day,
    climate_yearly,
    climatology,
    drop_empty,
    ensemble_stats,
    head,
    rollup,
    table_from_block,
)


def test_table_from_block_adds_weekday_for_daily_blocks():
    payload = {
        "daily_units": {"time": "iso8601", "t": "°C"},
        "daily": {"time": ["2026-10-03", "2026-10-04"], "t": [1.0, 2.0]},
    }
    table = table_from_block(payload, "daily")
    assert table.time == ["2026-10-03", "2026-10-04"]
    assert table.units == {"t": "°C"}
    assert table.columns == {"t": [1.0, 2.0]}
    assert table.weekday == ["Saturday", "Sunday"]


def test_table_from_block_has_no_weekday_for_hourly_blocks():
    payload = {
        "hourly_units": {"time": "iso8601", "t": "°C"},
        "hourly": {"time": ["2026-10-03T00:00"], "t": [1.0]},
    }
    assert table_from_block(payload, "hourly").weekday is None


def test_rollup_groups_rows_and_applies_each_columns_aggregate():
    table = Table(
        time=["2026-10-03T00:00", "2026-10-03T01:00", "2026-10-04T00:00"],
        units={"rain": "mm", "temp": "°C"},
        columns={"rain": [0.1, 0.2, None], "temp": [10.0, 12.0, None]},
    )
    result = rollup(table, by_day, {"rain": "sum"})
    assert result.time == ["2026-10-03", "2026-10-04"]
    assert result.columns == {"rain": [0.3, None], "temp": [11.0, None]}
    assert result.units == {"rain": "mm", "temp": "°C"}


def test_rollup_uses_the_default_aggregate_for_unlisted_columns():
    table = Table(time=["a1", "a2"], units={}, columns={"x": [1, 5]})
    assert rollup(table, lambda s: s[:1], default="max").columns == {"x": [5]}


def test_head_keeps_the_first_rows():
    table = Table(time=["a", "b", "c"], units={"x": "u"}, columns={"x": [1, 2, 3]})
    assert head(table, 2) == Table(time=["a", "b"], units={"x": "u"}, columns={"x": [1, 2]})


def test_drop_empty_removes_all_null_columns_and_names_them():
    table = Table(
        time=["a", "b"],
        units={"x": "u", "y": "v"},
        columns={"x": [1, None], "y": [None, None]},
    )
    kept, removed = drop_empty(table)
    assert kept.columns == {"x": [1, None]}
    assert kept.units == {"x": "u"}
    assert removed == ["y"]


def test_climatology_averages_each_calendar_month_across_years():
    monthly = Table(
        time=["2023-01", "2023-02", "2024-01", "2024-02"],
        units={"x": "u"},
        columns={"x": [1.0, 2.0, 3.0, 4.0]},
    )
    table, years = climatology(monthly)
    assert table.time == ["01", "02"]
    assert table.columns == {"x": [2.0, 3.0]}
    assert years == 2


def test_climatology_orders_months_even_when_the_span_starts_mid_year():
    monthly = Table(
        time=["2023-11", "2023-12", "2024-01"], units={}, columns={"x": [11.0, 12.0, 1.0]}
    )
    table, _ = climatology(monthly)
    assert table.time == ["01", "11", "12"]
    assert table.columns == {"x": [1.0, 11.0, 12.0]}


def test_ensemble_stats_returns_mean_and_spread_and_no_members():
    table = Table(
        time=["2026-10-03", "2026-10-04"],
        units={"p": "mm", "p_member01": "mm", "p_member02": "mm"},
        columns={"p": [1.0, None], "p_member01": [2.0, None], "p_member02": [3.0, None]},
        weekday=["Saturday", "Sunday"],
    )
    result = ensemble_stats(table)
    assert result.columns == {"p_mean": [2.0, None], "p_std": [0.82, None]}
    assert result.units == {"p_mean": "mm", "p_std": "mm"}
    assert result.weekday == ["Saturday", "Sunday"]
    assert not any("member" in name for name in result.columns)


def test_ensemble_stats_keeps_variables_with_shared_prefixes_apart():
    table = Table(
        time=["d"],
        units={},
        columns={
            "t_max": [10.0],
            "t_max_member01": [14.0],
            "t_min": [1.0],
            "t_min_member01": [3.0],
        },
    )
    result = ensemble_stats(table)
    assert result.columns["t_max_mean"] == [12.0]
    assert result.columns["t_min_mean"] == [2.0]


def test_climate_yearly_summarises_models_per_year_and_skips_missing_models():
    table = Table(
        time=["2030-01-01", "2030-01-02", "2031-01-01"],
        units={"t_A": "°C", "p_A": "mm"},
        columns={
            "t_A": [1.0, 3.0, 5.0],
            "t_B": [2.0, 4.0, 7.0],
            "p_A": [1.0, 1.0, 2.0],
            "p_B": [None, None, None],
        },
    )
    result = climate_yearly(table, {"t": "mean", "p": "sum"}, ["A", "B", "C"])
    assert result.time == ["2030", "2031"]
    assert result.columns["t_mean"] == [2.5, 6.0]
    assert result.columns["t_min"] == [2.0, 5.0]
    assert result.columns["t_max"] == [3.0, 7.0]
    assert result.columns["p_mean"] == [2.0, 2.0]
    assert result.units["t_mean"] == "°C"
    assert result.units["p_max"] == "mm"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit/test_tables.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'weather_agents.server.openmeteo.tables'`.

- [ ] **Step 3: Write the implementation**

**`packages/weather-agents/src/weather_agents/server/openmeteo/tables.py`**

```python
"""Columnar tables and the pure functions that summarise them. No HTTP, no MCP."""

from collections.abc import Callable, Sequence
from datetime import date
from statistics import mean, pstdev
from typing import Any, Literal

from pydantic import BaseModel

Agg = Literal["max", "min", "mean", "sum"]

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class Table(BaseModel):
    time: list[str]
    units: dict[str, str]
    columns: dict[str, list[float | int | None]]
    weekday: list[str] | None = None


def table_from_block(payload: dict[str, Any], block: str) -> Table:
    """Turn an Open-Meteo `hourly`, `daily`, or `monthly` block into a Table."""
    data = payload[block]
    units = payload.get(f"{block}_units", {})
    weekday = None
    if block == "daily":
        weekday = [_WEEKDAYS[date.fromisoformat(stamp).weekday()] for stamp in data["time"]]
    return Table(
        time=data["time"],
        units={name: unit for name, unit in units.items() if name != "time"},
        columns={name: values for name, values in data.items() if name != "time"},
        weekday=weekday,
    )


def by_day(stamp: str) -> str:
    return stamp[:10]


def by_month(stamp: str) -> str:
    return stamp[:7]


def by_year(stamp: str) -> str:
    return stamp[:4]


def _present(values: Sequence[float | int | None]) -> list[float]:
    return [float(value) for value in values if value is not None]


def _aggregate(values: Sequence[float | int | None], how: Agg) -> float | None:
    present = _present(values)
    if not present:
        return None
    match how:
        case "max":
            result = max(present)
        case "min":
            result = min(present)
        case "sum":
            result = sum(present)
        case "mean":
            result = mean(present)
    return round(result, 2)


def rollup(
    table: Table,
    key: Callable[[str], str],
    how: dict[str, Agg] | None = None,
    default: Agg = "mean",
) -> Table:
    """Group rows by `key(time)` and aggregate each column. Rows keep their first-seen order."""
    groups: dict[str, list[int]] = {}
    for index, stamp in enumerate(table.time):
        groups.setdefault(key(stamp), []).append(index)
    overrides = how or {}
    columns = {
        name: [
            _aggregate([values[i] for i in rows], overrides.get(name, default))
            for rows in groups.values()
        ]
        for name, values in table.columns.items()
    }
    return Table(time=list(groups), units=table.units, columns=columns)


def head(table: Table, rows: int) -> Table:
    return Table(
        time=table.time[:rows],
        units=table.units,
        columns={name: values[:rows] for name, values in table.columns.items()},
    )


def drop_empty(table: Table) -> tuple[Table, list[str]]:
    """Remove columns that hold only nulls. Returns the new table and the removed names."""
    empty = [name for name, values in table.columns.items() if all(v is None for v in values)]
    kept = {name: values for name, values in table.columns.items() if name not in empty}
    units = {name: unit for name, unit in table.units.items() if name in kept}
    return Table(time=table.time, units=units, columns=kept), empty


def climatology(monthly: Table) -> tuple[Table, int]:
    """Average monthly rows ("2023-01") into 12 calendar-month rows ("01" to "12").

    Returns the table and the number of distinct calendar years that went in.
    """
    years = len({stamp[:4] for stamp in monthly.time})
    averaged = rollup(monthly, key=lambda stamp: stamp[5:7])
    order = sorted(range(len(averaged.time)), key=lambda i: averaged.time[i])
    table = Table(
        time=[averaged.time[i] for i in order],
        units=averaged.units,
        columns={name: [values[i] for i in order] for name, values in averaged.columns.items()},
    )
    return table, years


def ensemble_stats(table: Table) -> Table:
    """Collapse `<name>` and `<name>_memberNN` columns into `<name>_mean` and `<name>_std`."""
    bases = [name for name in table.columns if "_member" not in name]
    columns: dict[str, list[float | int | None]] = {}
    units: dict[str, str] = {}
    for base in bases:
        members = [
            values
            for name, values in table.columns.items()
            if name == base or name.startswith(f"{base}_member")
        ]
        means: list[float | int | None] = []
        spreads: list[float | int | None] = []
        for row in range(len(table.time)):
            present = _present([member[row] for member in members])
            means.append(round(mean(present), 2) if present else None)
            spreads.append(round(pstdev(present), 2) if present else None)
        columns[f"{base}_mean"] = means
        columns[f"{base}_std"] = spreads
        units[f"{base}_mean"] = units[f"{base}_std"] = table.units.get(base, "")
    return Table(time=table.time, units=units, columns=columns, weekday=table.weekday)


def climate_yearly(table: Table, variables: dict[str, Agg], models: Sequence[str]) -> Table:
    """Turn daily `<variable>_<MODEL>` columns into yearly `<variable>_mean`, `_min`, `_max`.

    Each model is aggregated to a year first, using the variable's `Agg`. The three output
    columns are the mean, lowest, and highest of those yearly values across the models.
    Models that lack a variable are skipped.
    """
    present = {
        variable: [
            f"{variable}_{model}" for model in models if f"{variable}_{model}" in table.columns
        ]
        for variable in variables
    }
    how: dict[str, Agg] = {
        name: variables[variable] for variable, names in present.items() for name in names
    }
    subset = Table(
        time=table.time,
        units=table.units,
        columns={name: table.columns[name] for name in how},
    )
    yearly = rollup(subset, by_year, how)
    columns: dict[str, list[float | int | None]] = {}
    units: dict[str, str] = {}
    for variable, names in present.items():
        if not names:
            continue
        series = [yearly.columns[name] for name in names]
        reducers: tuple[Agg, ...] = ("mean", "min", "max")
        for reducer in reducers:
            columns[f"{variable}_{reducer}"] = [
                _aggregate([s[row] for s in series], reducer) for row in range(len(yearly.time))
            ]
            units[f"{variable}_{reducer}"] = table.units.get(names[0], "")
    return Table(time=yearly.time, units=units, columns=columns)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit/test_tables.py -v`
Expected: `11 passed`.

- [ ] **Step 5: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: `All checks passed!` from both tools, and no changes to the two files above.

- [ ] **Step 6: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add table summaries: rollup, climatology, ensemble and climate stats"
```

---

### Task 3: Variable mapping

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/openmeteo/variables.py`
- Test: `packages/weather-agents/tests/unit/test_variables.py`

**Interfaces:**
- Produces:
  - `BasicVariable = Literal["temperature", "precipitation", "wind"]`
  - `ForecastVariable = Literal["temperature", "precipitation", "wind", "gusts", "precipitation_probability", "uv_index", "weather_code"]`
  - `DEFAULT_BASIC`, `DEFAULT_FORECAST`: tuples of those names
  - `open_meteo_names(variables: Sequence[str], *, hourly: bool = False) -> list[str]`

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/unit/test_variables.py`**

```python
from weather_agents.server.openmeteo.variables import (
    DEFAULT_BASIC,
    DEFAULT_FORECAST,
    open_meteo_names,
)


def test_daily_names_expand_temperature_to_max_and_min():
    assert open_meteo_names(["temperature", "wind"]) == [
        "temperature_2m_max",
        "temperature_2m_min",
        "wind_speed_10m_max",
    ]


def test_hourly_names_use_the_hourly_variables():
    assert open_meteo_names(["temperature", "gusts"], hourly=True) == [
        "temperature_2m",
        "wind_gusts_10m",
    ]


def test_repeated_variables_are_sent_once():
    assert open_meteo_names(["wind", "wind"]) == ["wind_speed_10m_max"]


def test_default_forecast_bundle_names():
    assert open_meteo_names(DEFAULT_FORECAST) == [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "wind_speed_10m_max",
        "weather_code",
    ]
    assert open_meteo_names(DEFAULT_BASIC)[-1] == "wind_speed_10m_max"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit/test_variables.py -v`
Expected: collection error `ModuleNotFoundError: ... variables`.

- [ ] **Step 3: Write the implementation**

**`packages/weather-agents/src/weather_agents/server/openmeteo/variables.py`**

```python
"""Logical variable names the tools accept, and the Open-Meteo names they stand for."""

from collections.abc import Sequence
from typing import Literal

BasicVariable = Literal["temperature", "precipitation", "wind"]
ForecastVariable = Literal[
    "temperature",
    "precipitation",
    "wind",
    "gusts",
    "precipitation_probability",
    "uv_index",
    "weather_code",
]

DEFAULT_BASIC: tuple[BasicVariable, ...] = ("temperature", "precipitation", "wind")
DEFAULT_FORECAST: tuple[ForecastVariable, ...] = (
    "temperature",
    "precipitation",
    "wind",
    "weather_code",
)

_DAILY: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature_2m_max", "temperature_2m_min"),
    "precipitation": ("precipitation_sum",),
    "wind": ("wind_speed_10m_max",),
    "gusts": ("wind_gusts_10m_max",),
    "precipitation_probability": ("precipitation_probability_max",),
    "uv_index": ("uv_index_max",),
    "weather_code": ("weather_code",),
}

_HOURLY: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature_2m",),
    "precipitation": ("precipitation",),
    "wind": ("wind_speed_10m",),
    "gusts": ("wind_gusts_10m",),
    "precipitation_probability": ("precipitation_probability",),
    "uv_index": ("uv_index",),
    "weather_code": ("weather_code",),
}


def open_meteo_names(variables: Sequence[str], *, hourly: bool = False) -> list[str]:
    """Map logical names to Open-Meteo daily (default) or hourly names, without repeats."""
    mapping = _HOURLY if hourly else _DAILY
    return list(dict.fromkeys(name for variable in variables for name in mapping[variable]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit/test_variables.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add logical variable names and their Open-Meteo mapping"
```

---

### Task 4: Open-Meteo client

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/openmeteo/client.py`
- Test: `packages/weather-agents/tests/unit/test_client.py`

**Interfaces:**
- Produces:
  - URL constants: `FORECAST`, `ELEVATION`, `ENSEMBLE`, `SEASONAL`, `ARCHIVE`, `CLIMATE`, `MARINE`, `AIR_QUALITY`, `FLOOD`, `GEOCODING_SEARCH`, `GEOCODING_GET`
  - `OpenMeteoError(cause, detail)` with `.cause` in `"rejected" | "rate_limited" | "server_error" | "timeout" | "unreachable"` and `.detail: str`
  - `OpenMeteoClient(http: httpx.AsyncClient)` with `async get(url: str, **params) -> Any`. Lists become comma-separated, `None` values are dropped.

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/unit/test_client.py`**

```python
import httpx
import pytest

from weather_agents.server.openmeteo.client import OpenMeteoClient, OpenMeteoError

pytestmark = pytest.mark.anyio

URL = "https://example.test/v1/thing"


def client_for(handler) -> OpenMeteoClient:
    return OpenMeteoClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_get_returns_json_joins_lists_and_drops_none():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"ok": True})

    data = await client_for(handler).get(URL, daily=["a", "b"], timezone="auto", skip=None)
    assert data == {"ok": True}
    assert seen == {"daily": "a,b", "timezone": "auto"}


async def test_a_400_becomes_rejected_with_the_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": True, "reason": "Latitude must be in range"})

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "rejected"
    assert caught.value.detail == "Latitude must be in range"


async def test_a_400_without_a_reason_falls_back_to_the_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="nope")

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "rejected"
    assert caught.value.detail == "HTTP 400"


@pytest.mark.parametrize(
    ("status", "cause"), [(429, "rate_limited"), (500, "server_error"), (503, "server_error")]
)
async def test_other_statuses_map_to_a_cause(status: int, cause: str):
    with pytest.raises(OpenMeteoError) as caught:
        await client_for(lambda request: httpx.Response(status)).get(URL)
    assert caught.value.cause == cause


async def test_a_timeout_becomes_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "timeout"


async def test_a_network_failure_becomes_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(OpenMeteoError) as caught:
        await client_for(handler).get(URL)
    assert caught.value.cause == "unreachable"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit/test_client.py -v`
Expected: collection error `ModuleNotFoundError: ... client`.

- [ ] **Step 3: Write the implementation**

**`packages/weather-agents/src/weather_agents/server/openmeteo/client.py`**

```python
"""The only code that calls Open-Meteo. It knows HTTP and error shapes, nothing about MCP."""

from typing import Any, Literal

import httpx

FORECAST = "https://api.open-meteo.com/v1/forecast"
ELEVATION = "https://api.open-meteo.com/v1/elevation"
ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"
SEASONAL = "https://seasonal-api.open-meteo.com/v1/seasonal"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
CLIMATE = "https://climate-api.open-meteo.com/v1/climate"
MARINE = "https://marine-api.open-meteo.com/v1/marine"
AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
GEOCODING_SEARCH = "https://geocoding-api.open-meteo.com/v1/search"
GEOCODING_GET = "https://geocoding-api.open-meteo.com/v1/get"

Cause = Literal["rejected", "rate_limited", "server_error", "timeout", "unreachable"]


class OpenMeteoError(Exception):
    """Open-Meteo did not give a usable answer. `cause` says why, `detail` says more."""

    def __init__(self, cause: Cause, detail: str) -> None:
        super().__init__(f"{cause}: {detail}")
        self.cause = cause
        self.detail = detail


def _param(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return value


class OpenMeteoClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get(self, url: str, **params: Any) -> Any:
        """GET `url` and return the parsed JSON. Lists become comma-separated, None is dropped."""
        query = {key: _param(value) for key, value in params.items() if value is not None}
        try:
            response = await self._http.get(url, params=query)
        except httpx.TimeoutException as error:
            raise OpenMeteoError("timeout", "no answer within the time limit") from error
        except httpx.HTTPError as error:
            raise OpenMeteoError("unreachable", type(error).__name__) from error
        status = response.status_code
        if status == 429:
            raise OpenMeteoError("rate_limited", "too many requests, try again later")
        if status >= 500:
            raise OpenMeteoError("server_error", f"HTTP {status}")
        if status >= 400:
            raise OpenMeteoError("rejected", self._reason(response))
        return response.json()

    @staticmethod
    def _reason(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return f"HTTP {response.status_code}"
        return str(body.get("reason", f"HTTP {response.status_code}"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/unit -v`
Expected: `23 passed` (tables 11, variables 4, client 8).

- [ ] **Step 5: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the Open-Meteo HTTP client with named failure causes"
```

---

### Task 5: Server skeleton and geocoding tools

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/models.py`
- Create: `packages/weather-agents/src/weather_agents/server/state.py`
- Create: `packages/weather-agents/src/weather_agents/server/tools/common.py`
- Create: `packages/weather-agents/src/weather_agents/server/tools/geocoding.py`
- Create: `packages/weather-agents/src/weather_agents/server/app.py`
- Create: `packages/weather-agents/tests/fakes.py`
- Create: `packages/weather-agents/tests/conftest.py`
- Test: `packages/weather-agents/tests/server/test_geocoding.py`

**Interfaces:**
- Consumes: `OpenMeteoClient`, `OpenMeteoError`, `GEOCODING_SEARCH`, `GEOCODING_GET` (Task 4); `Table` (Task 2).
- Produces:
  - `models.py`: `Latitude`, `Longitude`, `Coordinates`, `Location`, `WeatherResult`, `ClimateResult`, `Place`, `PlaceList`, `ElevationPoint`, `ElevationResult`.
  - `AppState(openmeteo: OpenMeteoClient, today: Callable[[], date])`, frozen dataclass.
  - `tools/common.py`: `upstream_errors` (decorator that turns `OpenMeteoError` into `ToolError("Open-Meteo <cause>: <detail>")`), `state_of(ctx) -> AppState`, `location_of(payload) -> Location`.
  - Every tool module exposes `register(mcp: MCPServer) -> None`.
  - `create_server(*, transport: httpx.AsyncBaseTransport | None = None, today: Callable[[], date] = date.today) -> MCPServer`, and module-level `mcp`.
  - Test helpers: `FakeOpenMeteo` with `route(url, payload, *, status=200)`, `route_with(url, handler)`, `route_response(url, handler)`, `.requests`, `.params(index=-1)`; `iso_days`, `iso_hours`, `om_response`, `constant_daily`, `PLACES`; fixtures `fake` and `client`; the fixed clock `TODAY = date(2026, 10, 3)`.

- [ ] **Step 1: Write the test helpers and the failing tests**

`tests/fakes.py` builds Open-Meteo-shaped responses and routes requests by URL. An unrouted request raises, so a test that calls an endpoint it did not expect fails loudly.

**`packages/weather-agents/tests/fakes.py`**

```python
"""Builders for Open-Meteo-shaped responses, and a router that serves them to the server."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx


def iso_days(start: str, count: int) -> list[str]:
    first = date.fromisoformat(start)
    return [(first + timedelta(days=i)).isoformat() for i in range(count)]


def iso_hours(start: str, count: int) -> list[str]:
    return [f"{day}T{hour:02d}:00" for day in iso_days(start, count // 24) for hour in range(24)]


def om_response(
    block: str,
    times: list[str],
    columns: dict[str, list[Any]],
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """An Open-Meteo reply: grid-cell header, `<block>_units`, and `<block>`."""
    return {
        "latitude": 52.52,
        "longitude": 13.41,
        "generationtime_ms": 0.1,
        "utc_offset_seconds": 7200,
        "timezone": "Europe/Berlin",
        "timezone_abbreviation": "GMT+2",
        "elevation": 38.0,
        f"{block}_units": {"time": "iso8601", **(units or {})},
        block: {"time": times, **columns},
    }


def constant_daily(start: date, end: date, values: dict[str, float]) -> dict[str, Any]:
    """A daily reply with one constant value per column for every day from start to end."""
    times = iso_days(start.isoformat(), (end - start).days + 1)
    columns = {name: [value] * len(times) for name, value in values.items()}
    return om_response("daily", times, columns, {name: "u" for name in values})


PLACES = {
    "springfield_mo": {
        "id": 4409896,
        "name": "Springfield",
        "latitude": 37.21533,
        "longitude": -93.29824,
        "elevation": 396.0,
        "timezone": "America/Chicago",
        "country_code": "US",
        "country": "United States",
        "admin1": "Missouri",
        "population": 170188,
        "postcodes": ["65801"],
    },
    "springfield_il": {
        "id": 4250542,
        "name": "Springfield",
        "latitude": 39.80172,
        "longitude": -89.64371,
        "elevation": 182.0,
        "timezone": "America/Chicago",
        "country_code": "US",
        "country": "United States",
        "admin1": "Illinois",
        "population": 114394,
    },
    "berlin": {
        "id": 2950159,
        "name": "Berlin",
        "latitude": 52.52437,
        "longitude": 13.41053,
        "elevation": 74.0,
        "timezone": "Europe/Berlin",
        "country_code": "DE",
        "country": "Germany",
        "admin1": "State of Berlin",
        "population": 3426354,
    },
}


class FakeOpenMeteo:
    """An httpx handler that answers by URL (scheme, host, path) and records every request."""

    def __init__(self) -> None:
        self._routes: dict[str, Callable[[httpx.Request], httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def route(self, url: str, payload: Any = None, *, status: int = 200) -> None:
        self._routes[url] = lambda _request: httpx.Response(status, json=payload)

    def route_with(self, url: str, handler: Callable[[httpx.Request], Any]) -> None:
        """Answer with `handler(request)`, a JSON-serialisable payload."""
        self._routes[url] = lambda request: httpx.Response(200, json=handler(request))

    def route_response(self, url: str, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self._routes[url] = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = f"{request.url.scheme}://{request.url.host}{request.url.path}"
        handler = self._routes.get(url)
        if handler is None:
            raise AssertionError(f"Unrouted request: {request.url}")
        return handler(request)

    def params(self, index: int = -1) -> dict[str, str]:
        return dict(self.requests[index].url.params)
```

`tests/conftest.py` gives every server test a `client` connected in memory to a server with a mock transport and the fixed clock. The `anyio` pytest plugin needs the `anyio_backend` fixture to pick `asyncio`.

**`packages/weather-agents/tests/conftest.py`**

```python
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from mcp import Client

from tests.fakes import FakeOpenMeteo
from weather_agents.server.app import create_server

TODAY = date(2026, 10, 3)  # a Saturday


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake() -> FakeOpenMeteo:
    return FakeOpenMeteo()


@pytest.fixture
async def client(fake: FakeOpenMeteo) -> AsyncIterator[Client]:
    server = create_server(transport=httpx.MockTransport(fake), today=lambda: TODAY)
    async with Client(server) as connected:
        yield connected
```

**`packages/weather-agents/tests/server/test_geocoding.py`**

```python
import pytest

from tests.fakes import PLACES
from weather_agents.server.openmeteo.client import GEOCODING_GET, GEOCODING_SEARCH

pytestmark = pytest.mark.anyio


async def test_search_returns_every_candidate_with_country_region_and_population(client, fake):
    fake.route(GEOCODING_SEARCH, {"results": [PLACES["springfield_mo"], PLACES["springfield_il"]]})
    result = await client.call_tool("geocode_search", {"name": "Springfield"})
    assert not result.is_error
    places = result.structured_content["results"]
    assert [(p["admin1"], p["population"]) for p in places] == [
        ("Missouri", 170188),
        ("Illinois", 114394),
    ]
    assert places[0]["country"] == "United States"
    assert fake.params() == {"name": "Springfield", "count": "5", "language": "en"}


async def test_search_with_no_match_returns_an_empty_list(client, fake):
    fake.route(GEOCODING_SEARCH, {"generationtime_ms": 0.1})
    result = await client.call_tool("geocode_search", {"name": "Zzyzzyxx"})
    assert not result.is_error
    assert result.structured_content["results"] == []


async def test_search_sends_the_country_code_in_upper_case(client, fake):
    fake.route(GEOCODING_SEARCH, {"results": [PLACES["berlin"]]})
    await client.call_tool("geocode_search", {"name": "Berlin", "country_code": "de"})
    assert fake.params()["countryCode"] == "DE"


async def test_search_rejects_a_one_letter_name_without_calling_open_meteo(client, fake):
    result = await client.call_tool("geocode_search", {"name": "B"})
    assert result.is_error
    assert "name" in result.content[0].text
    assert fake.requests == []


async def test_get_returns_one_place_by_id(client, fake):
    fake.route(GEOCODING_GET, PLACES["berlin"])
    result = await client.call_tool("geocode_get", {"id": 2950159})
    assert not result.is_error
    assert result.structured_content["name"] == "Berlin"
    assert fake.params()["id"] == "2950159"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_geocoding.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'weather_agents.server.app'`.

- [ ] **Step 3: Write the shared models and state**

**`packages/weather-agents/src/weather_agents/server/models.py`**

```python
"""Argument types and result models shared by the tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from weather_agents.server.openmeteo.tables import Table

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude in degrees.")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Longitude in degrees.")]


class Coordinates(BaseModel):
    latitude: Latitude
    longitude: Longitude


class Location(BaseModel):
    """The grid cell Open-Meteo answered for. It can differ slightly from the request."""

    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None


class WeatherResult(BaseModel):
    location: Location
    kind: Literal["hourly", "daily", "monthly", "climatology", "yearly"]
    table: Table
    notes: list[str] = []


class ClimateResult(BaseModel):
    places: list[WeatherResult]


class Place(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    population: int | None = None


class PlaceList(BaseModel):
    results: list[Place]


class ElevationPoint(BaseModel):
    latitude: float
    longitude: float
    elevation: float | None


class ElevationResult(BaseModel):
    points: list[ElevationPoint]
```

**`packages/weather-agents/src/weather_agents/server/state.py`**

```python
"""What the server's lifespan hands to every tool call."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from weather_agents.server.openmeteo.client import OpenMeteoClient


@dataclass(frozen=True)
class AppState:
    openmeteo: OpenMeteoClient
    today: Callable[[], date]
```

- [ ] **Step 4: Write the tool helpers**

`functools.wraps` in `upstream_errors` keeps the real signature and docstring visible. The SDK reads both to build the tool's input schema and description. This was checked on `mcp` 2.3.0.

**`packages/weather-agents/src/weather_agents/server/tools/common.py`**

```python
"""Helpers every tool module uses."""

import functools
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from weather_agents.server.models import Location
from weather_agents.server.openmeteo.client import OpenMeteoError
from weather_agents.server.state import AppState


def upstream_errors[**P, R](fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Turn an OpenMeteoError into a tool error result that names the cause.

    `functools.wraps` keeps the signature and docstring, which the SDK reads to build the
    tool's input schema and description.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except OpenMeteoError as error:
            raise ToolError(f"Open-Meteo {error.cause}: {error.detail}") from error

    return wrapper


def state_of(ctx: Context[AppState]) -> AppState:
    return ctx.request_context.lifespan_context


def location_of(payload: dict[str, Any]) -> Location:
    return Location(
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        elevation=payload.get("elevation"),
        timezone=payload.get("timezone"),
    )
```

- [ ] **Step 5: Write the geocoding tools**

**`packages/weather-agents/src/weather_agents/server/tools/geocoding.py`**

```python
"""Geocoding tools: place name to coordinates and timezone."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from weather_agents.server.models import Place, PlaceList
from weather_agents.server.openmeteo.client import GEOCODING_GET, GEOCODING_SEARCH
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import state_of, upstream_errors


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def geocode_search(
        ctx: Context[AppState],
        name: Annotated[
            str,
            Field(min_length=2, description="Place name, such as 'Springfield' or 'Paris'."),
        ],
        country_code: Annotated[
            str | None,
            Field(
                pattern=r"^[A-Za-z]{2}$",
                description="ISO 3166-1 alpha-2 country code, such as 'US', to narrow the search.",
            ),
        ] = None,
        count: Annotated[int, Field(ge=1, le=100, description="Maximum results.")] = 5,
    ) -> PlaceList:
        """Place name to coordinates and timezone.

        Several results means the name is ambiguous: ask the user which place they mean before
        using any coordinates. Each result has country, region, and population to tell them apart.
        """
        data = await state_of(ctx).openmeteo.get(
            GEOCODING_SEARCH,
            name=name,
            countryCode=country_code.upper() if country_code else None,
            count=count,
            language="en",
        )
        return PlaceList(results=[Place.model_validate(item) for item in data.get("results", [])])

    @mcp.tool()
    @upstream_errors
    async def geocode_get(
        ctx: Context[AppState],
        id: Annotated[int, Field(description="Geocoding id, from a geocode_search result.")],
    ) -> Place:
        """Look up one place by its geocoding id. Returns the same fields as geocode_search."""
        data = await state_of(ctx).openmeteo.get(GEOCODING_GET, id=id, language="en")
        return Place.model_validate(data)
```

- [ ] **Step 6: Write the app skeleton**

This version registers only the geocoding tools. Later tasks add one import and one `register` call each. The final version appears in Task 11.

**`packages/weather-agents/src/weather_agents/server/app.py`**

```python
"""Builds the Open-Meteo MCP server. `mcp` at module level is what `mcp dev` imports."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

import httpx
from mcp.server import MCPServer

from weather_agents.server.openmeteo.client import OpenMeteoClient
from weather_agents.server.state import AppState
from weather_agents.server.tools import geocoding

HTTP_TIMEOUT_SECONDS = 30
INSTRUCTIONS = (
    "Weather data from Open-Meteo (https://open-meteo.com), licensed CC BY 4.0. "
    "Pick the tool by the time horizon of the question: forecast for the next 16 days, "
    "ensemble for how sure that forecast is, seasonal beyond 16 days, historical for the past, "
    "climate for long-term change. Call geocode_search to turn a place name into coordinates. "
    "Read the open-meteo://guide resource for how the data behaves."
)


def create_server(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    today: Callable[[], date] = date.today,
) -> MCPServer:
    """Build a server. Tests pass a mock `transport` and a fixed `today`."""

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[AppState]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, transport=transport) as http:
            yield AppState(openmeteo=OpenMeteoClient(http), today=today)

    server = MCPServer("weather", instructions=INSTRUCTIONS, lifespan=lifespan)
    geocoding.register(server)
    return server


mcp = create_server()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_geocoding.py -v`
Expected: `5 passed`.

- [ ] **Step 8: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 9: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the server skeleton and the geocoding tools"
```

---

### Task 6: Forecast, ensemble, and seasonal tools

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/tools/forecast.py`
- Modify: `packages/weather-agents/src/weather_agents/server/app.py`
- Test: `packages/weather-agents/tests/server/test_forecast_tools.py`
- Test: `packages/weather-agents/tests/server/test_errors.py`

**Interfaces:**
- Consumes: `FORECAST`, `ENSEMBLE`, `SEASONAL` (Task 4); `ensemble_stats`, `head`, `table_from_block` (Task 2); `open_meteo_names`, `DEFAULT_BASIC`, `DEFAULT_FORECAST`, `BasicVariable`, `ForecastVariable` (Task 3); `upstream_errors`, `state_of`, `location_of` (Task 5).
- Produces: tools `forecast`, `ensemble`, `seasonal`, each returning `WeatherResult`.

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/server/test_forecast_tools.py`**

```python
import pytest

from tests.fakes import iso_days, iso_hours, om_response
from weather_agents.server.openmeteo.client import ENSEMBLE, FORECAST, SEASONAL

pytestmark = pytest.mark.anyio

POINT = {"latitude": 52.52, "longitude": 13.41}


async def test_forecast_returns_daily_rows_with_weekdays_for_the_default_variables(client, fake):
    columns = {
        "temperature_2m_max": [19.5, 19.6, 18.0],
        "temperature_2m_min": [13.4, 12.3, 11.0],
        "precipitation_sum": [0.0, 0.0, 2.1],
        "wind_speed_10m_max": [6.3, 7.0, 9.9],
        "weather_code": [3, 3, 61],
    }
    fake.route(FORECAST, om_response("daily", iso_days("2026-10-03", 3), columns))
    result = await client.call_tool("forecast", {**POINT, "days": 3})
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "daily"
    assert data["table"]["time"] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert data["table"]["weekday"] == ["Saturday", "Sunday", "Monday"]
    assert data["table"]["columns"]["precipitation_sum"] == [0.0, 0.0, 2.1]
    assert data["location"]["timezone"] == "Europe/Berlin"
    assert fake.params() == {
        "latitude": "52.52",
        "longitude": "13.41",
        "forecast_days": "3",
        "timezone": "auto",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "wind_speed_10m_max,weather_code",
    }


async def test_forecast_hourly_returns_hourly_rows_without_weekdays(client, fake):
    times = iso_hours("2026-10-03", 48)
    fake.route(FORECAST, om_response("hourly", times, {"temperature_2m": [1.0] * 48}))
    result = await client.call_tool("forecast", {**POINT, "days": 2, "hourly": True})
    assert not result.is_error
    assert result.structured_content["kind"] == "hourly"
    assert result.structured_content["table"]["weekday"] is None
    assert "daily" not in fake.params()
    assert fake.params()["hourly"] == ("temperature_2m,precipitation,wind_speed_10m,weather_code")


async def test_forecast_hourly_over_three_days_is_refused_before_calling_open_meteo(client, fake):
    result = await client.call_tool("forecast", {**POINT, "days": 4, "hourly": True})
    assert result.is_error
    assert "days" in result.content[0].text
    assert fake.requests == []


async def test_forecast_maps_chosen_variables(client, fake):
    fake.route(
        FORECAST,
        om_response("daily", iso_days("2026-10-03", 1), {"wind_gusts_10m_max": [30.0]}),
    )
    await client.call_tool("forecast", {**POINT, "days": 1, "variables": ["gusts"]})
    assert fake.params()["daily"] == "wind_gusts_10m_max"


async def test_forecast_rejects_an_unknown_variable_naming_the_argument(client, fake):
    result = await client.call_tool("forecast", {**POINT, "variables": ["snow"]})
    assert result.is_error
    assert "variables" in result.content[0].text
    assert fake.requests == []


async def test_forecast_rejects_more_than_sixteen_days(client, fake):
    result = await client.call_tool("forecast", {**POINT, "days": 17})
    assert result.is_error
    assert "days" in result.content[0].text
    assert fake.requests == []


async def test_ensemble_returns_mean_and_spread_and_never_members(client, fake):
    columns = {
        "precipitation_sum": [1.0, 0.0],
        "precipitation_sum_member01": [2.0, 0.0],
        "precipitation_sum_member02": [3.0, 0.0],
    }
    fake.route(ENSEMBLE, om_response("daily", iso_days("2026-10-03", 2), columns))
    result = await client.call_tool(
        "ensemble", {**POINT, "days": 2, "variables": ["precipitation"]}
    )
    assert not result.is_error
    table = result.structured_content["table"]
    assert table["columns"] == {
        "precipitation_sum_mean": [2.0, 0.0],
        "precipitation_sum_std": [0.82, 0.0],
    }
    assert table["weekday"] == ["Saturday", "Sunday"]
    assert fake.params()["models"] == "ecmwf_ifs025"
    assert fake.params()["forecast_days"] == "2"


async def test_ensemble_rejects_sixteen_days(client, fake):
    result = await client.call_tool("ensemble", {**POINT, "days": 16})
    assert result.is_error
    assert fake.requests == []


def seasonal_payload() -> dict:
    return om_response(
        "monthly",
        [f"2026-{month:02d}-01" for month in range(10, 13)] + ["2027-01-01", "2027-02-01"],
        {
            "temperature_2m_anomaly": [0.2, 0.6, 1.2, 1.2, 0.3],
            "precipitation_anomaly": [-5.1, 2.8, 6.4, 4.3, 2.6],
        },
        {"temperature_2m_anomaly": "K", "precipitation_anomaly": "mm"},
    )


async def test_seasonal_returns_the_requested_months_labelled_low_confidence(client, fake):
    fake.route(SEASONAL, seasonal_payload())
    result = await client.call_tool("seasonal", {**POINT, "months": 3})
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "monthly"
    assert data["table"]["time"] == ["2026-10-01", "2026-11-01", "2026-12-01"]
    assert data["table"]["columns"]["temperature_2m_anomaly"] == [0.2, 0.6, 1.2]
    assert any("Low confidence" in note for note in data["notes"])
    assert fake.params()["monthly"] == "temperature_2m_anomaly,precipitation_anomaly"
    assert fake.params()["forecast_days"] == "93"


async def test_seasonal_caps_forecast_days_at_the_api_limit(client, fake):
    fake.route(SEASONAL, seasonal_payload())
    await client.call_tool("seasonal", {**POINT, "months": 7})
    assert fake.params()["forecast_days"] == "216"


async def test_seasonal_rejects_eight_months(client, fake):
    result = await client.call_tool("seasonal", {**POINT, "months": 8})
    assert result.is_error
    assert fake.requests == []
```

`test_errors.py` checks the error behaviour that every tool shares, using `forecast`.

**`packages/weather-agents/tests/server/test_errors.py`**

```python
import httpx
import pytest

from tests.fakes import iso_days, om_response
from weather_agents.server.openmeteo.client import FORECAST

pytestmark = pytest.mark.anyio

ARGS = {"latitude": 52.52, "longitude": 13.41, "days": 2}


def ok_forecast() -> dict:
    return om_response("daily", iso_days("2026-10-03", 2), {"temperature_2m_max": [1.0, 2.0]}, {})


async def test_an_open_meteo_rejection_names_the_cause_and_the_reason(client, fake):
    fake.route(FORECAST, {"error": True, "reason": "Latitude must be in range"}, status=400)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "rejected" in result.content[0].text
    assert "Latitude must be in range" in result.content[0].text


async def test_a_server_error_names_the_status(client, fake):
    fake.route(FORECAST, {}, status=503)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "server_error" in result.content[0].text
    assert "503" in result.content[0].text


async def test_a_timeout_is_an_error_result_naming_the_cause(client, fake):
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    fake.route_response(FORECAST, slow)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "timeout" in result.content[0].text


async def test_an_unreachable_open_meteo_is_an_error_result(client, fake):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    fake.route_response(FORECAST, down)
    result = await client.call_tool("forecast", ARGS)
    assert result.is_error
    assert "unreachable" in result.content[0].text


async def test_the_server_keeps_serving_after_a_failed_call(client, fake):
    answers = iter([httpx.Response(500), httpx.Response(200, json=ok_forecast())])
    fake.route_response(FORECAST, lambda request: next(answers))
    first = await client.call_tool("forecast", ARGS)
    second = await client.call_tool("forecast", ARGS)
    assert first.is_error
    assert not second.is_error


async def test_an_out_of_range_latitude_names_the_argument_and_skips_open_meteo(client, fake):
    result = await client.call_tool("forecast", {**ARGS, "latitude": 95})
    assert result.is_error
    assert "latitude" in result.content[0].text
    assert fake.requests == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_forecast_tools.py tests/server/test_errors.py -v`
Expected: the tests fail because the tools are not registered. The call results are errors like `Unknown tool: forecast`.

- [ ] **Step 3: Write the tools**

**`packages/weather-agents/src/weather_agents/server/tools/forecast.py`**

```python
"""Forward-looking tools: forecast, ensemble, seasonal."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from weather_agents.server.models import Latitude, Longitude, WeatherResult
from weather_agents.server.openmeteo.client import ENSEMBLE, FORECAST, SEASONAL
from weather_agents.server.openmeteo.tables import ensemble_stats, head, table_from_block
from weather_agents.server.openmeteo.variables import (
    DEFAULT_BASIC,
    DEFAULT_FORECAST,
    BasicVariable,
    ForecastVariable,
    open_meteo_names,
)
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

HOURLY_MAX_DAYS = 3
ENSEMBLE_MODEL = "ecmwf_ifs025"
SEASONAL_VARIABLES = ["temperature_2m_anomaly", "precipitation_anomaly"]
SEASONAL_MAX_FORECAST_DAYS = 216
SEASONAL_NOTE = (
    "Low confidence. A seasonal forecast shows a tendency against the long-term normal, "
    "not a day-by-day forecast. Anomaly is forecast minus normal."
)
ENSEMBLE_NOTE = (
    "Mean and standard deviation across the ensemble members. A larger standard deviation "
    "means the members disagree and the forecast is less certain."
)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def forecast(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=16, description="Days ahead, starting today.")] = 7,
        hourly: Annotated[
            bool, Field(description="Hourly rows instead of daily. Limited to 3 days.")
        ] = False,
        variables: Annotated[
            list[ForecastVariable] | None,
            Field(
                description="What to include. Defaults to temperature, precipitation, wind, "
                "and weather_code."
            ),
        ] = None,
    ) -> WeatherResult:
        """Weather forecast from today out to 16 days for one point.

        Daily rows carry the weekday of each date, in the place's local timezone. Temperature is
        in degrees Celsius, wind in km/h, precipitation in mm. For how sure the forecast is, call
        ensemble. Beyond 16 days, call seasonal.
        """
        if hourly and days > HOURLY_MAX_DAYS:
            raise ToolError(
                f"Argument 'days': hourly forecasts are limited to {HOURLY_MAX_DAYS} days, "
                f"got {days}. Use hourly=false for longer."
            )
        block = "hourly" if hourly else "daily"
        names = open_meteo_names(variables or DEFAULT_FORECAST, hourly=hourly)
        data = await state_of(ctx).openmeteo.get(
            FORECAST,
            latitude=latitude,
            longitude=longitude,
            forecast_days=days,
            timezone="auto",
            **{block: names},
        )
        return WeatherResult(
            location=location_of(data), kind=block, table=table_from_block(data, block)
        )

    @mcp.tool()
    @upstream_errors
    async def ensemble(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=15, description="Days ahead, starting today.")] = 7,
        variables: Annotated[
            list[BasicVariable] | None,
            Field(description="What to include. Defaults to temperature, precipitation, wind."),
        ] = None,
    ) -> WeatherResult:
        """How sure a forecast is, within 15 days. Daily mean and spread across ensemble members.

        Each variable comes back as `<name>_mean` and `<name>_std`. The raw members are never
        returned. Use it next to forecast: a high standard deviation means low confidence.
        """
        names = open_meteo_names(variables or DEFAULT_BASIC)
        data = await state_of(ctx).openmeteo.get(
            ENSEMBLE,
            latitude=latitude,
            longitude=longitude,
            models=ENSEMBLE_MODEL,
            forecast_days=days,
            timezone="auto",
            daily=names,
        )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=ensemble_stats(table_from_block(data, "daily")),
            notes=[ENSEMBLE_NOTE],
        )

    @mcp.tool()
    @upstream_errors
    async def seasonal(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        months: Annotated[
            int, Field(ge=1, le=7, description="Months ahead, counting the current month.")
        ] = 3,
    ) -> WeatherResult:
        """Seasonal tendency from 16 days to 7 months ahead, one row per month. Low confidence.

        Returns the expected anomaly against normal: temperature in K (degrees above or below
        normal) and precipitation in mm. Do not present it as a forecast for a given day.
        """
        data = await state_of(ctx).openmeteo.get(
            SEASONAL,
            latitude=latitude,
            longitude=longitude,
            monthly=SEASONAL_VARIABLES,
            forecast_days=min(months * 31, SEASONAL_MAX_FORECAST_DAYS),
            timezone="auto",
        )
        return WeatherResult(
            location=location_of(data),
            kind="monthly",
            table=head(table_from_block(data, "monthly"), months),
            notes=[SEASONAL_NOTE],
        )
```

- [ ] **Step 4: Register the tools in `app.py`**

Change the tools import to `from weather_agents.server.tools import forecast, geocoding`. Add `forecast.register(server)` on the line after `geocoding.register(server)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_forecast_tools.py tests/server/test_errors.py tests/server/test_geocoding.py -v`
Expected: `22 passed` (forecast tools 11, errors 6, geocoding 5).

- [ ] **Step 6: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 7: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the forecast, ensemble, and seasonal tools"
```

---

### Task 7: Historical and climate tools

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/tools/history.py`
- Modify: `packages/weather-agents/src/weather_agents/server/app.py`
- Test: `packages/weather-agents/tests/server/test_history_tools.py`

**Interfaces:**
- Consumes: `ARCHIVE`, `CLIMATE` (Task 4); `rollup`, `by_month`, `climatology`, `climate_yearly`, `table_from_block`, `Agg` (Task 2); `open_meteo_names`, `DEFAULT_BASIC`, `BasicVariable` (Task 3); `Coordinates`, `ClimateResult`, `WeatherResult` (Task 5).
- Produces: tools `historical` and `climate`, plus `CLIMATE_MODELS` (the 7 model names) in `tools/history.py`.

- [ ] **Step 1: Write the failing tests**

The archive and climate fakes generate rows from the request's date range, so the 30-year case needs no fixture file.

**`packages/weather-agents/tests/server/test_history_tools.py`**

```python
from datetime import date

import httpx
import pytest

from tests.fakes import constant_daily
from weather_agents.server.openmeteo.client import ARCHIVE, CLIMATE
from weather_agents.server.tools.history import CLIMATE_MODELS

pytestmark = pytest.mark.anyio

POINT = {"latitude": 52.52, "longitude": 13.41}
DAILY_VALUES = {
    "temperature_2m_max": 10.0,
    "temperature_2m_min": 5.0,
    "precipitation_sum": 1.0,
    "wind_speed_10m_max": 20.0,
}


def serve_archive(fake) -> None:
    def archive(request: httpx.Request):
        params = request.url.params
        return constant_daily(
            date.fromisoformat(params["start_date"]),
            date.fromisoformat(params["end_date"]),
            DAILY_VALUES,
        )

    fake.route_with(ARCHIVE, archive)


async def historical(client, start: str, end: str):
    return await client.call_tool("historical", {**POINT, "start_date": start, "end_date": end})


async def test_a_span_up_to_a_month_returns_one_row_per_day(client, fake):
    serve_archive(fake)
    result = await historical(client, "2025-01-01", "2025-01-10")
    assert not result.is_error
    data = result.structured_content
    assert data["kind"] == "daily"
    assert len(data["table"]["time"]) == 10
    assert fake.params()["start_date"] == "2025-01-01"
    assert fake.params()["daily"] == (
        "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
    )


async def test_a_span_over_a_month_returns_one_row_per_month_with_precipitation_summed(
    client, fake
):
    serve_archive(fake)
    result = await historical(client, "2025-01-01", "2025-03-31")
    data = result.structured_content
    assert data["kind"] == "monthly"
    assert data["table"]["time"] == ["2025-01", "2025-02", "2025-03"]
    assert data["table"]["columns"]["precipitation_sum"] == [31.0, 28.0, 31.0]
    assert data["table"]["columns"]["temperature_2m_max"] == [10.0, 10.0, 10.0]
    assert any("Partial" in note or "partial" in note for note in data["notes"])


async def test_a_span_over_two_years_returns_twelve_calendar_month_normals(client, fake):
    serve_archive(fake)
    result = await historical(client, "2021-01-01", "2023-12-31")
    data = result.structured_content
    assert data["kind"] == "climatology"
    assert data["table"]["time"] == [f"{month:02d}" for month in range(1, 13)]
    assert data["table"]["columns"]["precipitation_sum"][:2] == [31.0, 28.0]
    assert any("3 calendar years" in note for note in data["notes"])


async def test_a_thirty_year_normal_returns_twelve_rows(client, fake):
    serve_archive(fake)
    result = await historical(client, "1991-01-01", "2020-12-31")
    data = result.structured_content
    assert len(data["table"]["time"]) == 12
    assert any("30 calendar years" in note for note in data["notes"])


async def test_recent_dates_get_a_lag_note(client, fake):
    serve_archive(fake)
    result = await historical(client, "2026-09-20", "2026-10-01")
    assert any("last 5 days" in note for note in result.structured_content["notes"])


@pytest.mark.parametrize(
    ("start", "end", "argument"),
    [
        ("1939-12-31", "1940-01-10", "start_date"),
        ("2026-09-01", "2026-10-04", "end_date"),
        ("2025-02-01", "2025-01-01", "end_date"),
    ],
)
async def test_a_date_outside_the_horizon_names_the_argument_and_skips_open_meteo(
    client, fake, start, end, argument
):
    result = await historical(client, start, end)
    assert result.is_error
    assert argument in result.content[0].text
    assert fake.requests == []


def serve_climate(fake) -> None:
    def climate(request: httpx.Request):
        params = request.url.params
        start = date.fromisoformat(params["start_date"])
        end = date.fromisoformat(params["end_date"])
        values = {}
        for index, model in enumerate(CLIMATE_MODELS):
            values[f"temperature_2m_mean_{model}"] = 10.0 + index
            values[f"precipitation_sum_{model}"] = 1.0
            values[f"wind_speed_10m_max_{model}"] = 5.0
        payload = constant_daily(start, end, values)
        count = len(params["latitude"].split(","))
        return payload if count == 1 else [payload] * count

    fake.route_with(CLIMATE, climate)


async def test_climate_returns_yearly_mean_and_model_range_for_each_place(client, fake):
    serve_climate(fake)
    result = await client.call_tool(
        "climate",
        {
            "places": [
                {"latitude": 52.52, "longitude": 13.41},
                {"latitude": 48.14, "longitude": 11.58},
            ],
            "start_year": 2025,
            "end_year": 2026,
        },
    )
    assert not result.is_error
    places = result.structured_content["places"]
    assert len(places) == 2
    table = places[0]["table"]
    assert places[0]["kind"] == "yearly"
    assert table["time"] == ["2025", "2026"]
    assert table["columns"]["temperature_2m_mean_mean"] == [13.0, 13.0]
    assert table["columns"]["temperature_2m_mean_min"] == [10.0, 10.0]
    assert table["columns"]["temperature_2m_mean_max"] == [16.0, 16.0]
    assert table["columns"]["precipitation_sum_mean"] == [365.0, 365.0]
    params = fake.params()
    assert params["latitude"] == "52.52,48.14"
    assert params["longitude"] == "13.41,11.58"
    assert params["start_date"] == "2025-01-01"
    assert params["end_date"] == "2026-12-31"
    assert params["models"] == ",".join(CLIMATE_MODELS)


async def test_climate_handles_the_single_object_reply_for_one_place(client, fake):
    serve_climate(fake)
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 52.52, "longitude": 13.41}], "start_year": 2030, "end_year": 2030},
    )
    assert not result.is_error
    assert len(result.structured_content["places"]) == 1


async def test_climate_refuses_more_than_five_places_naming_the_argument(client, fake):
    places = [{"latitude": float(i), "longitude": float(i)} for i in range(6)]
    result = await client.call_tool("climate", {"places": places})
    assert result.is_error
    assert "places" in result.content[0].text
    assert fake.requests == []


async def test_climate_refuses_an_end_year_before_the_start_year(client, fake):
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 1.0, "longitude": 1.0}], "start_year": 2040, "end_year": 2030},
    )
    assert result.is_error
    assert "end_year" in result.content[0].text
    assert fake.requests == []


async def test_climate_refuses_a_year_outside_the_data(client, fake):
    result = await client.call_tool(
        "climate",
        {"places": [{"latitude": 1.0, "longitude": 1.0}], "start_year": 1949},
    )
    assert result.is_error
    assert "start_year" in result.content[0].text
    assert fake.requests == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_history_tools.py -v`
Expected: collection error `ModuleNotFoundError: ... tools.history`.

- [ ] **Step 3: Write the tools**

**`packages/weather-agents/src/weather_agents/server/tools/history.py`**

```python
"""Backward-looking and long-range tools: historical weather and climate projections."""

from datetime import date, timedelta
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from weather_agents.server.models import (
    ClimateResult,
    Coordinates,
    Latitude,
    Longitude,
    WeatherResult,
)
from weather_agents.server.openmeteo.client import ARCHIVE, CLIMATE
from weather_agents.server.openmeteo.tables import (
    Agg,
    by_month,
    climate_yearly,
    climatology,
    rollup,
    table_from_block,
)
from weather_agents.server.openmeteo.variables import DEFAULT_BASIC, BasicVariable, open_meteo_names
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

ARCHIVE_START = date(1940, 1, 1)
DETAIL_DAYS = 31
MONTHLY_DAYS = 730
ARCHIVE_LAG_DAYS = 5
HISTORICAL_HOW: dict[str, Agg] = {"precipitation_sum": "sum"}

CLIMATE_MODELS = (
    "CMCC_CM2_VHR4",
    "FGOALS_f3_H",
    "HiRAM_SIT_HR",
    "MRI_AGCM3_2_S",
    "EC_Earth3P_HR",
    "MPI_ESM1_2_XR",
    "NICAM16_8S",
)
CLIMATE_VARIABLES: dict[str, Agg] = {
    "temperature_2m_mean": "mean",
    "precipitation_sum": "sum",
    "wind_speed_10m_max": "mean",
}
CLIMATE_NOTE = (
    "Each value is the mean, lowest, and highest of the yearly values across the climate "
    "models. The gap between _min and _max shows how far the models disagree. "
    "precipitation_sum is the total for the year."
)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def historical(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        start_date: Annotated[date, Field(description="First day, from 1940-01-01.")],
        end_date: Annotated[date, Field(description="Last day, not after today.")],
        variables: Annotated[
            list[BasicVariable] | None,
            Field(description="What to include. Defaults to temperature, precipitation, wind."),
        ] = None,
    ) -> WeatherResult:
        """Observed weather for any period since 1940, from reanalysis data.

        Up to 31 days returns one row per day. Up to 2 years returns one row per month. Longer
        returns 12 rows, the average of each calendar month over all the years, which is a
        climate normal: for 30-year normals ask for 1991-01-01 to 2020-12-31. The last 5 days
        are often missing because the data lags.
        """
        today = state_of(ctx).today()
        if start_date < ARCHIVE_START:
            raise ToolError(
                f"Argument 'start_date': {start_date} is before {ARCHIVE_START}, "
                "when the history starts."
            )
        if end_date > today:
            raise ToolError(f"Argument 'end_date': {end_date} is after today, {today}.")
        if end_date < start_date:
            raise ToolError(f"Argument 'end_date': {end_date} is before 'start_date' {start_date}.")

        data = await state_of(ctx).openmeteo.get(
            ARCHIVE,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            timezone="auto",
            daily=open_meteo_names(variables or DEFAULT_BASIC),
        )
        daily = table_from_block(data, "daily")
        notes: list[str] = []
        if end_date > today - timedelta(days=ARCHIVE_LAG_DAYS):
            notes.append("The last 5 days are often missing because the reanalysis lags.")
        span = (end_date - start_date).days + 1
        if span <= DETAIL_DAYS:
            return WeatherResult(location=location_of(data), kind="daily", table=daily, notes=notes)
        monthly = rollup(daily, by_month, HISTORICAL_HOW)
        notes.append(
            "precipitation_sum is the total per month. Other columns are means of daily "
            "values. A partial first or last month is averaged over the days present."
        )
        if span <= MONTHLY_DAYS:
            return WeatherResult(
                location=location_of(data), kind="monthly", table=monthly, notes=notes
            )
        table, years = climatology(monthly)
        notes.append(
            f"Average of each calendar month over {years} calendar years. "
            "time is the month number, 01 to 12."
        )
        return WeatherResult(
            location=location_of(data), kind="climatology", table=table, notes=notes
        )

    @mcp.tool()
    @upstream_errors
    async def climate(
        ctx: Context[AppState],
        places: Annotated[
            list[Coordinates],
            Field(min_length=1, max_length=5, description="1 to 5 points to compare."),
        ],
        start_year: Annotated[int, Field(ge=1950, le=2049, description="First year.")] = 2025,
        end_year: Annotated[int, Field(ge=1950, le=2049, description="Last year.")] = 2049,
    ) -> ClimateResult:
        """Climate change projection to 2049, one row per year, for up to 5 places.

        Combines 7 climate models. For temperature, precipitation, and wind it returns the mean
        across models plus the lowest and highest model, so you can see how far the models
        disagree. Use it for long-term trends, not for weather on a given day.
        """
        if end_year < start_year:
            raise ToolError(f"Argument 'end_year': {end_year} is before 'start_year' {start_year}.")
        data = await state_of(ctx).openmeteo.get(
            CLIMATE,
            latitude=[place.latitude for place in places],
            longitude=[place.longitude for place in places],
            start_date=f"{start_year}-01-01",
            end_date=f"{end_year}-12-31",
            models=list(CLIMATE_MODELS),
            daily=list(CLIMATE_VARIABLES),
        )
        items = data if isinstance(data, list) else [data]
        return ClimateResult(
            places=[
                WeatherResult(
                    location=location_of(item),
                    kind="yearly",
                    table=climate_yearly(
                        table_from_block(item, "daily"), CLIMATE_VARIABLES, CLIMATE_MODELS
                    ),
                    notes=[CLIMATE_NOTE],
                )
                for item in items
            ]
        )
```

- [ ] **Step 4: Register the tools in `app.py`**

Change the tools import to `from weather_agents.server.tools import forecast, geocoding, history`. Add `history.register(server)` after `forecast.register(server)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_history_tools.py -v`
Expected: `13 passed`.

- [ ] **Step 6: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 7: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the historical and climate tools with summaries"
```

---

### Task 8: Marine, air quality, flood, and elevation tools

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/tools/environment.py`
- Modify: `packages/weather-agents/src/weather_agents/server/app.py`
- Test: `packages/weather-agents/tests/server/test_environment_tools.py`

**Interfaces:**
- Consumes: `MARINE`, `AIR_QUALITY`, `FLOOD`, `ELEVATION` (Task 4); `rollup`, `by_day`, `drop_empty`, `table_from_block`, `Table`, `Agg` (Task 2); `ElevationPoint`, `ElevationResult`, `Coordinates` (Task 5).
- Produces: tools `marine`, `air_quality`, `flood`, `elevation`.

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/server/test_environment_tools.py`**

```python
import pytest

from tests.fakes import iso_days, iso_hours, om_response
from weather_agents.server.openmeteo.client import AIR_QUALITY, ELEVATION, FLOOD, MARINE

pytestmark = pytest.mark.anyio

POINT = {"latitude": 54.5, "longitude": 8.3}
MARINE_COLUMNS = (
    "wave_height",
    "wave_period",
    "swell_wave_height",
    "ocean_current_velocity",
    "sea_surface_temperature",
    "sea_level_height_msl",
)


async def test_marine_returns_daily_maximums_and_the_mean_sea_temperature(client, fake):
    times = iso_hours("2026-10-03", 48)
    columns = {name: [1.0] * 48 for name in MARINE_COLUMNS}
    columns["wave_height"] = [float(i % 24) for i in range(48)]
    columns["sea_surface_temperature"] = [float(i % 24) for i in range(48)]
    fake.route(MARINE, om_response("hourly", times, columns))
    result = await client.call_tool("marine", {**POINT, "days": 2})
    assert not result.is_error
    table = result.structured_content["table"]
    assert table["time"] == ["2026-10-03", "2026-10-04"]
    assert table["columns"]["wave_height"] == [23.0, 23.0]
    assert table["columns"]["sea_surface_temperature"] == [11.5, 11.5]
    assert fake.params()["forecast_days"] == "2"
    assert fake.params()["hourly"] == ",".join(MARINE_COLUMNS)


async def test_marine_for_an_inland_point_returns_an_empty_table_with_a_note(client, fake):
    times = iso_hours("2026-10-03", 24)
    columns = {name: [None] * 24 for name in MARINE_COLUMNS}
    fake.route(MARINE, om_response("hourly", times, columns))
    result = await client.call_tool("marine", {"latitude": 48.14, "longitude": 11.58, "days": 1})
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["time"] == []
    assert any("inland" in note for note in data["notes"])


async def test_air_quality_returns_daily_maximums_and_drops_empty_pollen(client, fake):
    times = iso_hours("2026-10-03", 24)
    columns = {
        "pm10": [float(i) for i in range(24)],
        "european_aqi": [20] * 24,
        "alder_pollen": [None] * 24,
    }
    fake.route(AIR_QUALITY, om_response("hourly", times, columns))
    result = await client.call_tool(
        "air_quality", {"latitude": 40.7, "longitude": -74.0, "days": 1}
    )
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["time"] == ["2026-10-03"]
    assert data["table"]["columns"] == {"pm10": [23.0], "european_aqi": [20]}
    assert any("alder_pollen" in note for note in data["notes"])
    assert fake.params()["forecast_days"] == "1"


async def test_flood_returns_daily_discharge_with_a_note_about_the_river(client, fake):
    fake.route(
        FLOOD,
        om_response(
            "daily",
            iso_days("2026-10-03", 3),
            {"river_discharge": [0.46, 0.45, 0.45]},
            {"river_discharge": "m³/s"},
        ),
    )
    result = await client.call_tool("flood", {"latitude": 52.52, "longitude": 13.41})
    assert not result.is_error
    data = result.structured_content
    assert data["table"]["columns"]["river_discharge"] == [0.46, 0.45, 0.45]
    assert any("no river name" in note for note in data["notes"])
    assert fake.params()["daily"] == "river_discharge"
    assert fake.params()["forecast_days"] == "30"


async def test_flood_rejects_more_than_92_days(client, fake):
    result = await client.call_tool("flood", {"latitude": 1.0, "longitude": 1.0, "days": 93})
    assert result.is_error
    assert fake.requests == []


async def test_elevation_pairs_each_height_with_its_point(client, fake):
    fake.route(ELEVATION, {"elevation": [38.0, 524.0]})
    result = await client.call_tool(
        "elevation",
        {
            "points": [
                {"latitude": 52.52, "longitude": 13.41},
                {"latitude": 48.14, "longitude": 11.58},
            ]
        },
    )
    assert not result.is_error
    assert result.structured_content["points"] == [
        {"latitude": 52.52, "longitude": 13.41, "elevation": 38.0},
        {"latitude": 48.14, "longitude": 11.58, "elevation": 524.0},
    ]
    assert fake.params()["latitude"] == "52.52,48.14"


async def test_elevation_refuses_more_than_100_points(client, fake):
    points = [{"latitude": 1.0, "longitude": 1.0}] * 101
    result = await client.call_tool("elevation", {"points": points})
    assert result.is_error
    assert "points" in result.content[0].text
    assert fake.requests == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_environment_tools.py -v`
Expected: the tests fail because the tools are not registered (`Unknown tool`).

- [ ] **Step 3: Write the tools**

**`packages/weather-agents/src/weather_agents/server/tools/environment.py`**

```python
"""Tools for the sea, the air, rivers, and terrain."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from weather_agents.server.models import (
    Coordinates,
    ElevationPoint,
    ElevationResult,
    Latitude,
    Longitude,
    WeatherResult,
)
from weather_agents.server.openmeteo.client import AIR_QUALITY, ELEVATION, FLOOD, MARINE
from weather_agents.server.openmeteo.tables import (
    Agg,
    Table,
    by_day,
    drop_empty,
    rollup,
    table_from_block,
)
from weather_agents.server.state import AppState
from weather_agents.server.tools.common import location_of, state_of, upstream_errors

MARINE_DAILY: dict[str, Agg] = {
    "wave_height": "max",
    "wave_period": "max",
    "swell_wave_height": "max",
    "ocean_current_velocity": "max",
    "sea_surface_temperature": "mean",
    "sea_level_height_msl": "max",
}
AIR_HOURLY = [
    "pm10",
    "pm2_5",
    "ozone",
    "nitrogen_dioxide",
    "european_aqi",
    "us_aqi",
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "ragweed_pollen",
]
FLOOD_NOTE = (
    "River discharge at the nearest river grid cell, from the largest river within about "
    "5 km. Open-Meteo gives no river name or distance."
)
INLAND_NOTE = "No marine data at this point. It is inland or too far from the sea."


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    @upstream_errors
    async def marine(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=7, description="Days ahead, starting today.")] = 5,
    ) -> WeatherResult:
        """Sea conditions for up to 7 days ahead: waves, swell, currents, sea surface temperature.

        Also sea level height. One row per day: the daily maximum, except sea surface
        temperature, which is the daily mean. Only coastal and open-water points have data. An
        inland point returns an empty table with a note.
        """
        data = await state_of(ctx).openmeteo.get(
            MARINE,
            latitude=latitude,
            longitude=longitude,
            hourly=list(MARINE_DAILY),
            forecast_days=days,
            timezone="auto",
        )
        hourly = table_from_block(data, "hourly")
        kept, _ = drop_empty(hourly)
        if not kept.columns:
            return WeatherResult(
                location=location_of(data),
                kind="daily",
                table=Table(time=[], units={}, columns={}),
                notes=[INLAND_NOTE],
            )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=rollup(hourly, by_day, MARINE_DAILY),
        )

    @mcp.tool()
    @upstream_errors
    async def air_quality(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=7, description="Days ahead, starting today.")] = 3,
    ) -> WeatherResult:
        """Air quality for up to 7 days ahead: pollutants, European and US AQI, and pollen.

        One row per day, the daily maximum. Pollen exists only for Europe in season, and
        columns with no data are left out with a note.
        """
        data = await state_of(ctx).openmeteo.get(
            AIR_QUALITY,
            latitude=latitude,
            longitude=longitude,
            hourly=AIR_HOURLY,
            forecast_days=days,
            timezone="auto",
        )
        table, empty = drop_empty(rollup(table_from_block(data, "hourly"), by_day, default="max"))
        notes = [f"No data for: {', '.join(empty)}."] if empty else []
        return WeatherResult(location=location_of(data), kind="daily", table=table, notes=notes)

    @mcp.tool()
    @upstream_errors
    async def flood(
        ctx: Context[AppState],
        latitude: Latitude,
        longitude: Longitude,
        days: Annotated[int, Field(ge=1, le=92, description="Days ahead, starting today.")] = 30,
    ) -> WeatherResult:
        """River discharge in m3/s for up to 92 days ahead, one row per day."""
        data = await state_of(ctx).openmeteo.get(
            FLOOD,
            latitude=latitude,
            longitude=longitude,
            daily="river_discharge",
            forecast_days=days,
        )
        return WeatherResult(
            location=location_of(data),
            kind="daily",
            table=table_from_block(data, "daily"),
            notes=[FLOOD_NOTE],
        )

    @mcp.tool()
    @upstream_errors
    async def elevation(
        ctx: Context[AppState],
        points: Annotated[
            list[Coordinates],
            Field(min_length=1, max_length=100, description="1 to 100 points."),
        ],
    ) -> ElevationResult:
        """Terrain height in metres for one or more points. It does not change over time."""
        data = await state_of(ctx).openmeteo.get(
            ELEVATION,
            latitude=[point.latitude for point in points],
            longitude=[point.longitude for point in points],
        )
        return ElevationResult(
            points=[
                ElevationPoint(latitude=point.latitude, longitude=point.longitude, elevation=height)
                for point, height in zip(points, data["elevation"], strict=True)
            ]
        )
```

- [ ] **Step 4: Register the tools in `app.py`**

Change the tools import to `from weather_agents.server.tools import environment, forecast, geocoding, history`. Add `environment.register(server)` after `history.register(server)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_environment_tools.py -v`
Expected: `7 passed`.

- [ ] **Step 6: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 7: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the marine, air quality, flood, and elevation tools"
```

---

### Task 9: Resources and guide content

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/resources.py`
- Create: `packages/weather-agents/src/weather_agents/server/content/guide.md`
- Create: `packages/weather-agents/src/weather_agents/server/content/endpoints/{geocoding,forecast,ensemble,seasonal,historical,climate,marine,air-quality,flood,elevation}.md`
- Modify: `packages/weather-agents/src/weather_agents/server/app.py`
- Test: `packages/weather-agents/tests/server/test_resources.py`
- Test: `packages/weather-agents/tests/server/test_content.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except the `MCPServer` built in `app.py`.
- Produces: `CONTENT_DIR`, `ENDPOINTS` (the 10 names, in the scope doc's order), `ENDPOINT_TEMPLATE`, `read_content(relative_path) -> str`, `register(mcp)`. Resource `open-meteo://guide` and template `open-meteo://endpoints/{endpoint}`, with completion over `ENDPOINTS`.

The content was written from Open-Meteo's own pages (listed in each file's `Source:` lines). Two things the scope doc asks for are left out on purpose, because no Open-Meteo page backs them: routes and live observations.

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/server/test_resources.py`**

```python
import pytest
from mcp import MCPError
from mcp.types import ResourceTemplateReference

from weather_agents.server.resources import ENDPOINT_TEMPLATE, ENDPOINTS

pytestmark = pytest.mark.anyio


async def test_the_guide_is_markdown_about_the_whole_service(client):
    result = await client.read_resource("open-meteo://guide")
    content = result.contents[0]
    assert content.mime_type == "text/markdown"
    assert content.text.startswith("# Open-Meteo guide")


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_every_endpoint_has_a_guide(client, endpoint):
    result = await client.read_resource(f"open-meteo://endpoints/{endpoint}")
    assert result.contents[0].text.startswith("# ")


async def test_an_unknown_endpoint_is_an_error_that_lists_the_valid_names(client):
    with pytest.raises(MCPError) as caught:
        await client.read_resource("open-meteo://endpoints/radar")
    assert "radar" in caught.value.message
    assert "air-quality" in caught.value.message


async def complete(client, prefix: str) -> list[str]:
    result = await client.complete(
        ref=ResourceTemplateReference(uri=ENDPOINT_TEMPLATE),
        argument={"name": "endpoint", "value": prefix},
    )
    return result.completion.values


async def test_a_partial_endpoint_name_completes_from_the_ten_names(client):
    assert await complete(client, "a") == ["air-quality"]
    assert await complete(client, "") == list(ENDPOINTS)
    assert await complete(client, "zzz") == []
```

**`packages/weather-agents/tests/server/test_content.py`**

```python
import re

import pytest

from weather_agents.server.resources import CONTENT_DIR, ENDPOINTS

GUIDE_SECTIONS = [
    "Where the data comes from",
    "Refresh and trust",
    "Shared API conventions",
    "Which endpoint answers what",
    "What Open-Meteo cannot answer",
    "Attribution and terms",
]
ENDPOINT_SECTIONS = [
    "What it answers",
    "Sources and models",
    "Trust and limits",
    "Variables",
    "Argument tips",
]
SOURCE_LINE = re.compile(r"^Source: https://open-meteo\.com/\S+$", re.MULTILINE)


def sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def test_the_guide_has_the_sections_the_scope_lists():
    text = (CONTENT_DIR / "guide.md").read_text(encoding="utf-8")
    assert list(sections(text)) == GUIDE_SECTIONS


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_each_endpoint_guide_has_the_five_parts(endpoint):
    text = (CONTENT_DIR / "endpoints" / f"{endpoint}.md").read_text(encoding="utf-8")
    assert list(sections(text)) == ENDPOINT_SECTIONS


@pytest.mark.parametrize("name", ["guide", *[f"endpoints/{e}" for e in ENDPOINTS]])
def test_every_section_ends_with_an_open_meteo_source_line(name):
    text = (CONTENT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for title, body in sections(text).items():
        assert SOURCE_LINE.search(body), f"{name}: section '{title}' has no Source line"


def test_there_are_no_endpoint_files_beyond_the_ten():
    files = {path.stem for path in (CONTENT_DIR / "endpoints").glob("*.md")}
    assert files == set(ENDPOINTS)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_resources.py tests/server/test_content.py -v`
Expected: collection error `ModuleNotFoundError: ... resources`.

- [ ] **Step 3: Write the resources module**

**`packages/weather-agents/src/weather_agents/server/resources.py`**

```python
"""Resources: the Open-Meteo guide and one guide per endpoint, read from markdown files."""

import functools
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp.types import Completion, ResourceTemplateReference

CONTENT_DIR = Path(__file__).parent / "content"
ENDPOINTS = (
    "geocoding",
    "forecast",
    "ensemble",
    "seasonal",
    "historical",
    "climate",
    "marine",
    "air-quality",
    "flood",
    "elevation",
)
ENDPOINT_TEMPLATE = "open-meteo://endpoints/{endpoint}"


@functools.cache
def read_content(relative_path: str) -> str:
    return (CONTENT_DIR / relative_path).read_text(encoding="utf-8")


def register(mcp: MCPServer) -> None:
    @mcp.resource(
        "open-meteo://guide",
        name="open-meteo-guide",
        title="Open-Meteo guide",
        description="The whole service in one read: data sources, trust, conventions, horizons.",
        mime_type="text/markdown",
    )
    def guide() -> str:
        return read_content("guide.md")

    @mcp.resource(
        ENDPOINT_TEMPLATE,
        name="open-meteo-endpoint-guide",
        title="Open-Meteo endpoint guide",
        description="One endpoint in depth: sources, limits, variables, and argument tips.",
        mime_type="text/markdown",
    )
    def endpoint_guide(endpoint: str) -> str:
        if endpoint not in ENDPOINTS:
            raise ResourceNotFoundError(
                f"Unknown endpoint {endpoint!r}. Valid endpoints: {', '.join(ENDPOINTS)}."
            )
        return read_content(f"endpoints/{endpoint}.md")

    @mcp.completion()
    async def complete_endpoint(ref, argument, context):
        if isinstance(ref, ResourceTemplateReference) and argument.name == "endpoint":
            return Completion(values=[n for n in ENDPOINTS if n.startswith(argument.value)])
        return None
```

- [ ] **Step 4: Write the guide**

**`packages/weather-agents/src/weather_agents/server/content/guide.md`**

````markdown
# Open-Meteo guide

Open-Meteo serves weather data over HTTP. This server wraps 10 of its endpoints as tools. Read an endpoint guide at `open-meteo://endpoints/{endpoint}` for one endpoint in depth.

## Where the data comes from

- **Forecast:** numerical weather models. With no model chosen, Open-Meteo picks the best match for the location.
- **Ensemble:** several ensemble models, each run many times with slightly different starting conditions. Each run is a member.
- **Seasonal:** ECMWF SEAS5 (7 months) and EC46 (46 days), 51 members each, at 36 km resolution.
- **Historical weather:** reanalysis, which is past weather rebuilt from observations and a model. ERA5 covers 1940 to now, ERA5-Land 1950 to now, and ECMWF IFS 2017 to now.
- **Climate:** seven climate models, run from 1950 to 2050.
- **Marine:** wave models such as ECMWF WAM, GFS Wave, MFWAM, and DWD EWAM and GWAM. History comes from ERA5-Ocean.
- **Air quality:** CAMS Europe and CAMS Global.
- **Flood:** river discharge from a river model, at the largest river within about 5 km of the grid cell.
- **Elevation:** Copernicus DEM GLO-90, at 90 m resolution.
- **Geocoding:** GeoNames.

Source: https://open-meteo.com/en/docs

## Refresh and trust

- Every endpoint answers from a model grid, so a result describes a grid cell and not the exact point. The response gives the grid cell's own latitude and longitude.
- Historical weather from ERA5 lags real time by about 5 days.
- EC46 seasonal data updates daily at about 20:30 UTC. SEAS5 updates monthly, on the 5th.
- Seasonal data is not bias-corrected. It is a tendency against normal and not a forecast for a day.
- An ensemble shows how sure a forecast is. When the members agree, the forecast is firm. When they spread, it is not.
- Refresh cadence and limits differ per endpoint. The endpoint guides list them.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Shared API conventions

- Every weather endpoint takes `latitude` and `longitude`. Most accept several points as comma-separated lists, and then return one result per point.
- `timezone` defaults to GMT. Use `auto` to get times in the place's own timezone. It is required when `daily` variables are asked for. This server always sends `auto`.
- Data comes in blocks: `hourly`, `daily`, or `monthly`. Each block is one `time` array plus one array per variable, all the same length, plus a units object.
- Default units are degrees Celsius, km/h for wind, and mm for precipitation.
- Forecast accepts `past_days` from 0 to 92 and `forecast_days` from 0 to 16. This server's forecast tool does not expose `past_days`.
- An error is HTTP 400 with `{"error": true, "reason": "..."}`.

Source: https://open-meteo.com/en/docs

## Which endpoint answers what

| Question | Endpoint | Horizon |
|---|---|---|
| Weather in the next days | forecast | Today to 16 days |
| How sure is that forecast | ensemble | Within 15 days |
| Tendency beyond two weeks | seasonal | 16 days to 7 months |
| What the weather was | historical | 1940 to about 5 days ago |
| Long-term change | climate | 1950 to 2050 |
| Sea, air, rivers, terrain | marine, air-quality, flood, elevation | See each guide |

A forecast plus the ensemble spread for the same days tells you both the expected weather and how far to trust it. Historical weather over 30 years gives the normal that a forecast or seasonal anomaly is measured against.

Source: https://open-meteo.com/en/docs/ensemble-api

## What Open-Meteo cannot answer

- The flood endpoint returns discharge only. It gives no river name and no distance to the river.
- Marine data exists for the sea and the coast. An inland point returns only empty values.
- Pollen data exists only for Europe and only in season.
- Seasonal data is not a day-by-day forecast.

Source: https://open-meteo.com/en/docs/flood-api

## Attribution and terms

- The free tier is for non-commercial use, under 10,000 calls a day, 5,000 an hour, and 600 a minute. Long date ranges, many points, and many variables count as more than one call.
- Data is licensed CC BY 4.0. Credit Open-Meteo when you show it.
- Geocoding data is based on GeoNames.

Source: https://open-meteo.com/en/terms
````

- [ ] **Step 5: Write the endpoint guides**

**`packages/weather-agents/src/weather_agents/server/content/endpoints/geocoding.md`**

````markdown
# Geocoding

## What it answers

A place name to coordinates, elevation, timezone, country, region, and population. `/v1/search` finds places by name. `/v1/get` returns one place by its id. It has no time horizon.

Source: https://open-meteo.com/en/docs/geocoding-api

## Sources and models

Location data is based on GeoNames.

Source: https://open-meteo.com/en/docs/geocoding-api

## Trust and limits

- Search matches names by prefix from 3 characters. With 2 characters it matches the exact name. Shorter searches return nothing.
- `count` runs from 1 to 100.
- When geocoding finds several places with the same name, the name is ambiguous. Check country, region, and population to tell them apart.
- Empty fields are left out of a result.

Source: https://open-meteo.com/en/docs/geocoding-api

## Variables

Each result has `id`, `name`, `latitude`, `longitude`, `elevation`, `timezone`, `feature_code`, `country_code`, `country`, `population`, and `admin1` to `admin4` for the regions above the place. The tools return the fields `id`, `name`, `latitude`, `longitude`, `elevation`, `timezone`, `country`, `country_code`, `admin1`, and `population`.

Source: https://open-meteo.com/en/docs/geocoding-api

## Argument tips

- Add `country_code` (two letters, such as `US`) to narrow an ambiguous name.
- The name can carry a qualifier after a comma, such as `Paris, France`. It must match exactly.
- `geocode_get` takes the `id` from a `geocode_search` result.

Source: https://open-meteo.com/en/docs/geocoding-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/forecast.md`**

````markdown
# Forecast

## What it answers

Weather from today out to 16 days, hourly or daily, for one point. Time horizon: `forecast_days` runs from 0 to 16, default 7.

Source: https://open-meteo.com/en/docs

## Sources and models

With no model chosen, Open-Meteo combines the best available models for the location. The default output starts at 00:00 local time today.

Source: https://open-meteo.com/en/docs

## Trust and limits

- For how sure a forecast is, use the ensemble endpoint.
- The `weather_code` is a WMO code number. The API returns the number only.
- Beyond 16 days, use the seasonal endpoint.

Source: https://open-meteo.com/en/docs

## Variables

The `forecast` tool takes logical names and maps them. Daily rows use the first name, hourly rows the second.

| `variables` name | Daily | Hourly | Unit |
|---|---|---|---|
| `temperature` | `temperature_2m_max`, `temperature_2m_min` | `temperature_2m` | °C |
| `precipitation` | `precipitation_sum` | `precipitation` | mm |
| `wind` | `wind_speed_10m_max` | `wind_speed_10m` | km/h |
| `gusts` | `wind_gusts_10m_max` | `wind_gusts_10m` | km/h |
| `precipitation_probability` | `precipitation_probability_max` | `precipitation_probability` | % |
| `uv_index` | `uv_index_max` | `uv_index` | none |
| `weather_code` | `weather_code` | `weather_code` | WMO code |

The API offers many more variables, such as humidity, pressure, cloud cover, visibility, and soil values.

Source: https://open-meteo.com/en/docs

## Argument tips

- `days` runs from 1 to 16. Hourly rows are limited to 3 days to keep the result small.
- Daily rows carry a `weekday` for each date in the place's timezone. Use it to find a weekend.
- Default variables are temperature, precipitation, wind, and weather_code.

Source: https://open-meteo.com/en/docs
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/ensemble.md`**

````markdown
# Ensemble

## What it answers

How sure a forecast is. An ensemble runs a weather model many times from slightly different starting points. Each run is a member. When members agree the forecast is firm, and when they spread it is not. Time horizon: this server uses a model that runs 15 days.

Source: https://open-meteo.com/en/docs/ensemble-api

## Sources and models

Open-Meteo offers many ensemble models, for example ECMWF IFS 0.25° (51 members, 15 days), GFS 0.25° (31 members, 10 days), ICON-EPS (40 members, 7.5 days), and GEM (21 members, 16 days). This server uses ECMWF IFS 0.25°. Data is interpolated to hourly, and some models are 6-hourly later in their range.

Source: https://open-meteo.com/en/docs/ensemble-api

## Trust and limits

- The API returns every member as its own variable, such as `temperature_2m_max_member01`. This server never returns members. It returns the mean and the standard deviation across members for each day.
- On the last day of a model's range, values can be null.
- A larger standard deviation means a less certain forecast.

Source: https://open-meteo.com/en/docs/ensemble-api

## Variables

Daily variables offered by this server: `temperature` (`temperature_2m_max`, `temperature_2m_min`, °C), `precipitation` (`precipitation_sum`, mm), and `wind` (`wind_speed_10m_max`, km/h). Each comes back as `<name>_mean` and `<name>_std`. The API offers more variables, such as cloud cover, snow, and soil values.

Source: https://open-meteo.com/en/docs/ensemble-api

## Argument tips

- `days` runs from 1 to 15.
- Call it with the same `days` as `forecast`, and compare the `_std` of the days you care about.
- Daily rows carry a `weekday` for each date.

Source: https://open-meteo.com/en/docs/ensemble-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/seasonal.md`**

````markdown
# Seasonal

## What it answers

The tendency of the coming months against normal. Time horizon: beyond the 16-day forecast, up to 7 months ahead. It is a tendency, not a forecast for a day.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Sources and models

ECMWF SEAS5 reaches 7 months. ECMWF EC46 reaches 46 days. Both have 51 members at 36 km resolution. EC46 updates daily at about 20:30 UTC and SEAS5 monthly on the 5th.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Trust and limits

- Low confidence. The data is not bias-corrected.
- An anomaly is the forecast minus the model's own climate for that period.
- Individual member data is kept for one month. Means and spread are kept longer.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Variables

This server returns monthly anomalies: `temperature_2m_anomaly` in K (degrees above or below normal) and `precipitation_anomaly` in mm. The API also offers daily, weekly, and 6-hourly variables.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api

## Argument tips

- `months` runs from 1 to 7 and counts the current month.
- Present the result as a tendency against normal, and label it low-confidence.
- To compare with the normal itself, call `historical` for 1991-01-01 to 2020-12-31.

Source: https://open-meteo.com/en/docs/seasonal-forecast-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/historical.md`**

````markdown
# Historical weather

## What it answers

What the weather was at a point, for any period since 1940. Time horizon: 1940-01-01 up to about 5 days before today.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Sources and models

Reanalysis datasets: ERA5 (1940 to now), ERA5-Land (1950 to now), and ECMWF IFS (2017 to now). With no model chosen, Open-Meteo blends them.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Trust and limits

- ERA5 is delivered with a 5-day delay, so the last days can be missing.
- Different models carry different variables. For example, ERA5-Land has no precipitation, solar radiation, or wind.
- This server summarises long spans: up to 31 days one row per day, up to 2 years one row per month, and longer 12 rows with the average of each calendar month.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Variables

The `historical` tool takes `temperature` (`temperature_2m_max`, `temperature_2m_min`, °C), `precipitation` (`precipitation_sum`, mm), and `wind` (`wind_speed_10m_max`, km/h). The API offers more, such as radiation sums, evapotranspiration, and sunshine duration.

Source: https://open-meteo.com/en/docs/historical-weather-api

## Argument tips

- `start_date` and `end_date` are dates like `2024-01-31`.
- For a 30-year normal, ask for 1991-01-01 to 2020-12-31. The result has one row per calendar month. For precipitation, the value is the average monthly total.
- Compare a recent period with a normal by calling the tool twice.

Source: https://open-meteo.com/en/docs/historical-weather-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/climate.md`**

````markdown
# Climate

## What it answers

How the climate is projected to change. Time horizon: 1950-01-01 to 2050-01-01. This server returns one row per year, up to 2049, for up to 5 places.

Source: https://open-meteo.com/en/docs/climate-api

## Sources and models

Seven climate models: `CMCC_CM2_VHR4`, `FGOALS_f3_H`, `HiRAM_SIT_HR`, `MRI_AGCM3_2_S`, `EC_Earth3P_HR`, `MPI_ESM1_2_XR`, and `NICAM16_8S`. Values are bias-corrected onto ERA5-Land by default.

Source: https://open-meteo.com/en/docs/climate-api

## Trust and limits

- Models disagree. This server returns the mean across models plus the lowest and highest, so the gap shows the disagreement.
- Not every model carries every variable. For example, soil moisture exists for only two models. Models without a variable are skipped.
- Only daily data exists. A call over many years, places, and models counts as many calls against the free-tier limit.

Source: https://open-meteo.com/en/docs/climate-api

## Variables

The `climate` tool returns `temperature_2m_mean` (°C), `precipitation_sum` (mm per year), and `wind_speed_10m_max` (km/h, the yearly mean of the daily maximum). Each comes back as `_mean`, `_min`, and `_max` across models. The API offers more, such as humidity, cloud cover, and radiation.

Source: https://open-meteo.com/en/docs/climate-api

## Argument tips

- `places` takes 1 to 5 latitude and longitude pairs.
- `start_year` and `end_year` run from 1950 to 2049. The defaults are 2025 and 2049.
- Use it for long-term trends. For weather on a given day, use `forecast` or `historical`.

Source: https://open-meteo.com/en/docs/climate-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/marine.md`**

````markdown
# Marine

## What it answers

Sea conditions: waves, swell, ocean currents, sea surface temperature, and sea level height. Time horizon: this server asks for up to 7 days ahead. History from ERA5-Ocean runs from 1940.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Sources and models

Wave models: ECMWF WAM, GFS Wave, MFWAM, and DWD EWAM and GWAM. ERA5-Ocean covers history, with a 5-day delay.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Trust and limits

- Only the sea and the coast have data. An inland point returns a valid response whose values are all null. This server returns an empty table with a note for it.
- Sea level height may be unreliable further inland.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Variables

`wave_height` (m), `wave_period` (s), `swell_wave_height` (m), `ocean_current_velocity` (km/h), `sea_surface_temperature` (°C), and `sea_level_height_msl` (m). The API offers more, such as wave and swell directions, wind waves, and secondary swells. This server returns one row per day: the daily maximum, except sea surface temperature, which is the daily mean.

Source: https://open-meteo.com/en/docs/marine-weather-api

## Argument tips

- `days` runs from 1 to 7.
- Use a point on the coast or in open water. If the result is empty, the point is inland.

Source: https://open-meteo.com/en/docs/marine-weather-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/air-quality.md`**

````markdown
# Air quality

## What it answers

Pollutant levels, the European and US air quality indexes, and pollen. Time horizon: a forecast of about 4 days for Europe and 5 days for the world. This server asks for up to 7.

Source: https://open-meteo.com/en/docs/air-quality-api

## Sources and models

CAMS Europe (forecast from October 2023, reanalysis from 2013) and CAMS Global (from August 2022). With the default `domains=auto`, Open-Meteo picks the one that fits the location.

Source: https://open-meteo.com/en/docs/air-quality-api

## Trust and limits

- Pollen exists only for Europe and only in season. Elsewhere those values are null, and this server leaves those columns out with a note.
- The API has hourly data only. This server returns the daily maximum.

Source: https://open-meteo.com/en/docs/air-quality-api

## Variables

`pm10`, `pm2_5`, `ozone`, `nitrogen_dioxide` (µg/m³), `european_aqi`, `us_aqi`, and the pollen types `alder_pollen`, `birch_pollen`, `grass_pollen`, and `ragweed_pollen` (grains/m³). The API offers more, such as carbon monoxide, dust, and UV index.

Source: https://open-meteo.com/en/docs/air-quality-api

## Argument tips

- `days` runs from 1 to 7.
- For hay fever questions, read the pollen columns, and expect them to be missing outside Europe.

Source: https://open-meteo.com/en/docs/air-quality-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/flood.md`**

````markdown
# Flood

## What it answers

River discharge, the volume of water flowing past a point, in m³/s. Time horizon: up to 210 days ahead in the API, and data back to 1984. This server asks for up to 92 days.

Source: https://open-meteo.com/en/docs/flood-api

## Sources and models

Discharge is computed for a grid of river cells. For a point, it uses the largest river within about 5 km.

Source: https://open-meteo.com/en/docs/flood-api

## Trust and limits

- The result gives no river name and no distance to the river.

Source: https://open-meteo.com/en/docs/flood-api

## Variables

`river_discharge` (m³/s), one value per day. The API also offers mean, median, maximum, minimum, and quartile values across ensemble members for forecasts.

Source: https://open-meteo.com/en/docs/flood-api

## Argument tips

- `days` runs from 1 to 92. The default is 30.
- Choose a point on or near the river you care about, because the result follows the largest river within about 5 km.

Source: https://open-meteo.com/en/docs/flood-api
````

**`packages/weather-agents/src/weather_agents/server/content/endpoints/elevation.md`**

````markdown
# Elevation

## What it answers

Terrain height in metres for one or more points. It has no time horizon, because terrain does not change.

Source: https://open-meteo.com/en/docs/elevation-api

## Sources and models

Copernicus DEM GLO-90, a digital elevation model at 90 m resolution.

Source: https://open-meteo.com/en/docs/elevation-api

## Trust and limits

- At most 100 points per call.

Source: https://open-meteo.com/en/docs/elevation-api

## Variables

`elevation` in metres, one value per point, in the order the points were given.

Source: https://open-meteo.com/en/docs/elevation-api

## Argument tips

- Pass several points in one call. A ring of nearby points around a place shows how hilly it is: compare the highest and lowest value.

Source: https://open-meteo.com/en/docs/elevation-api
````

- [ ] **Step 6: Register the resources in `app.py`**

Add `from weather_agents.server import resources` above the `from weather_agents.server.openmeteo.client import OpenMeteoClient` line. Add `resources.register(server)` after `environment.register(server)`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_resources.py tests/server/test_content.py -v`
Expected: `36 passed` (resources 13, content 23).

- [ ] **Step 8: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 9: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the Open-Meteo guide and endpoint resources with completion"
```

---

### Task 10: Prompts

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/prompts.py`
- Modify: `packages/weather-agents/src/weather_agents/server/app.py`
- Test: `packages/weather-agents/tests/server/test_prompts.py`

**Interfaces:**
- Consumes: the `today` clock passed through `create_server`.
- Produces: `register(mcp: MCPServer, today: Callable[[], date]) -> None`, prompts `weekend_check` (no arguments) and `compare_places(places: str, month: str)`, and the helpers `parse_month(value) -> int` and `check_places(value) -> None`. Both helpers raise `MCPError(INVALID_PARAMS, "Invalid argument '<name>': ...")`.

The prompt text follows the repo's `writing-llm-prompts` standard: XML-tagged blocks, calm wording, and runtime values last. Code, not the model, does the mechanical steps: it counts the places, resolves the month, and works out how many months ahead the seasonal outlook must reach.

- [ ] **Step 1: Write the failing tests**

**`packages/weather-agents/tests/server/test_prompts.py`**

```python
import pytest
from mcp import MCPError
from mcp.types import INVALID_PARAMS

pytestmark = pytest.mark.anyio

# The fixture clock is 2026-10-03, so October is month 0 ahead and March is 5 ahead.


async def test_weekend_check_takes_no_arguments_and_tells_the_model_what_to_do(client):
    result = await client.get_prompt("weekend_check")
    text = result.messages[0].content.text
    assert result.messages[0].role == "user"
    for expected in ("geocode_search", "forecast", "ensemble", "weekday", "Saturday", "Sunday"):
        assert expected in text


async def compare(client, places: str, month: str) -> str:
    result = await client.get_prompt("compare_places", {"places": places, "month": month})
    return result.messages[0].content.text


async def test_compare_places_gives_the_model_the_places_the_month_and_the_seasonal_reach(client):
    text = await compare(client, "Lisbon, Athens", "March")
    assert "<places>Lisbon, Athens</places>" in text
    assert "<month>March</month>" in text
    assert "<month_number>03</month_number>" in text
    assert "<seasonal_months>6</seasonal_months>" in text
    assert "historical" in text
    assert "low-confidence" in text


async def test_compare_places_skips_the_seasonal_outlook_for_a_far_month(client):
    text = await compare(client, "Lisbon", "august")
    assert "<seasonal_months>none</seasonal_months>" in text


async def test_compare_places_accepts_numbers_and_three_letter_names(client):
    assert "<month>October</month>" in await compare(client, "Lisbon", "10")
    assert "<seasonal_months>1</seasonal_months>" in await compare(client, "Lisbon", "oct")


async def test_compare_places_refuses_more_than_five_places(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, "a, b, c, d, e, f", "March")
    assert caught.value.code == INVALID_PARAMS
    assert "places" in caught.value.message


async def test_compare_places_refuses_an_empty_list(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, " , ", "March")
    assert "places" in caught.value.message


async def test_compare_places_refuses_a_month_that_is_not_a_month(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, "Lisbon", "Smarch")
    assert caught.value.code == INVALID_PARAMS
    assert "month" in caught.value.message
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_prompts.py -v`
Expected: the tests fail because the prompts are not registered (`Unknown prompt`).

- [ ] **Step 3: Write the prompts**

**`packages/weather-agents/src/weather_agents/server/prompts.py`**

```python
"""Prompts: the weekend check and the trip comparison."""

from collections.abc import Callable
from datetime import date
from typing import Annotated

from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS
from pydantic import Field

MAX_PLACES = 5
SEASONAL_REACH_MONTHS = 6
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

WEEKEND_CHECK = """\
<role>
You help the user decide which day of the coming weekend is better for time outdoors.
</role>

<instructions>
1. Ask the user where they are. Wait for the answer.
2. Call `geocode_search` with the place name. If it returns several places, show them with \
country and region and ask which one the user means.
3. Call `forecast` for the chosen place with `days` set to 10 and the default variables.
4. In the forecast table, find the rows whose `weekday` is Saturday and Sunday. The table is \
already in the place's local timezone. Use the first Saturday and the first Sunday in it. \
Today counts if it falls on the weekend.
5. Call `ensemble` for the same place with `days` set to 10. Read the `_std` columns for the \
same two dates.
6. Decide which of the two days is better for being outside, and say how sure the forecast is.
</instructions>

<rules>
- Take every number from tool results. Do not estimate weather from memory.
- A larger `_std` means the ensemble members disagree, so the forecast is less certain. \
Say so when the two days differ in certainty.
- If a tool returns an error, tell the user what failed and stop.
</rules>

<quality_criteria>
- The answer names both dates with their weekdays.
- It says which day is better and gives the temperature, precipitation, and wind that decide it.
- It states how sure the forecast is and why.
</quality_criteria>
"""

COMPARE_PLACES = """\
<role>
You help the user choose where to travel in a given month by comparing the climate of up to \
five places.
</role>

<instructions>
1. Split the text in `<places>` on commas to get the individual place names.
2. For each place, call `geocode_search` and use the first result. If the name is ambiguous, \
choose the most populous result and tell the user which one you chose.
3. For each place, call `historical` with `start_date` 1991-01-01, `end_date` 2020-12-31, and \
the default variables. It returns 12 rows, one per calendar month, that are the 30-year \
normals. Read the row whose `time` equals `<month_number>`.
4. If `<seasonal_months>` is a number, also call `seasonal` for each place with `months` set \
to that number. Read the row for the month in `<month>`, and report it as a low-confidence \
tendency against normal. If `<seasonal_months>` is none, skip this step.
5. Say which place suits the trip best and why.
</instructions>

<rules>
- Take every number from tool results. Do not estimate climate from memory.
- Label the seasonal part low-confidence every time you mention it, because it is a tendency \
and not a forecast for specific days.
- If a tool returns an error for one place, say so and continue with the others.
</rules>

<quality_criteria>
- Every place appears in the comparison with its temperature and precipitation normals.
- The answer picks one place and gives the figures behind the choice.
- Seasonal information, when present, is kept apart from the normals and labelled low-confidence.
</quality_criteria>
"""


def parse_month(value: str) -> int:
    """Accept 1 to 12 or an English month name, in full or in three letters."""
    text = value.strip().lower()
    if text.isdigit() and 1 <= int(text) <= 12:
        return int(text)
    for number, name in enumerate(MONTHS, start=1):
        if text in (name.lower(), name[:3].lower()):
            return number
    raise MCPError(
        code=INVALID_PARAMS,
        message=f"Invalid argument 'month': {value!r} is not a month. "
        "Use 1 to 12 or an English month name.",
    )


def check_places(value: str) -> None:
    names = [name for name in value.split(",") if name.strip()]
    if not names:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid argument 'places': give 1 to 5 place names separated by commas.",
        )
    if len(names) > MAX_PLACES:
        raise MCPError(
            code=INVALID_PARAMS,
            message=f"Invalid argument 'places': got {len(names)} places, the maximum is "
            f"{MAX_PLACES}.",
        )


def register(mcp: MCPServer, today: Callable[[], date]) -> None:
    @mcp.prompt(title="Weekend check")
    def weekend_check() -> str:
        """Ask where the user is, then say which day of this weekend is better outside."""
        return WEEKEND_CHECK

    @mcp.prompt(title="Compare places for a trip")
    def compare_places(
        places: Annotated[str, Field(description="Up to 5 place names separated by commas.")],
        month: Annotated[
            str, Field(description="Month of the trip: 1 to 12 or an English month name.")
        ],
    ) -> str:
        """Compare the climate of up to 5 places for one month of the year."""
        check_places(places)
        number = parse_month(month)
        months_ahead = (number - today().month) % 12
        seasonal_months = str(months_ahead + 1) if months_ahead <= SEASONAL_REACH_MONTHS else "none"
        return (
            f"{COMPARE_PLACES}\n"
            "<context>\n"
            f"<places>{places}</places>\n"
            f"<month>{MONTHS[number - 1]}</month>\n"
            f"<month_number>{number:02d}</month_number>\n"
            f"<seasonal_months>{seasonal_months}</seasonal_months>\n"
            "</context>\n"
        )
```

- [ ] **Step 4: Register the prompts in `app.py`**

Change the first import to `from weather_agents.server import prompts, resources`. Add `prompts.register(server, today)` after `resources.register(server)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_prompts.py -v`
Expected: `7 passed`.

- [ ] **Step 6: Lint, format, and type-check**

Run from the repo root: `uv run ruff check --fix . && uv run ruff format . && uv run ty check`
Expected: all checks pass.

- [ ] **Step 7: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the weekend check and compare places prompts"
```

---

### Task 11: Entry point, surface tests, stdio, and live test

**Files:**
- Create: `packages/weather-agents/src/weather_agents/server/__main__.py`
- Test: `packages/weather-agents/tests/server/test_surface.py`
- Test: `packages/weather-agents/tests/server/test_stdio.py`
- Test: `packages/weather-agents/tests/live/test_live_stdio.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `python -m weather_agents.server`, which runs the server over stdio.

- [ ] **Step 1: Write the failing tests**

`test_surface.py` checks all 11 tool names, that each description states its horizon, and that each tool has an output schema. `test_stdio.py` spawns the real server as a child process and calls no tool, so it needs no network.

**`packages/weather-agents/tests/server/test_surface.py`**

```python
import pytest

pytestmark = pytest.mark.anyio

HORIZONS = {
    "geocode_search": "Place name to coordinates",
    "geocode_get": "Look up one place",
    "forecast": "from today out to 16 days",
    "ensemble": "within 15 days",
    "seasonal": "from 16 days to 7 months",
    "historical": "any period since 1940",
    "climate": "to 2049",
    "marine": "up to 7 days ahead",
    "air_quality": "up to 7 days ahead",
    "flood": "up to 92 days ahead",
    "elevation": "does not change over time",
}


async def test_the_server_exposes_the_eleven_endpoint_tools(client):
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == set(HORIZONS)


async def test_every_tool_states_its_horizon_and_has_an_output_schema(client):
    for tool in (await client.list_tools()).tools:
        assert HORIZONS[tool.name] in tool.description, tool.name
        assert tool.output_schema is not None, tool.name


async def test_the_server_exposes_two_prompts(client):
    prompts = (await client.list_prompts()).prompts
    assert {prompt.name for prompt in prompts} == {"weekend_check", "compare_places"}


async def test_the_server_exposes_the_guide_and_the_endpoint_template(client):
    resources = (await client.list_resources()).resources
    templates = (await client.list_resource_templates()).resource_templates
    assert [str(resource.uri) for resource in resources] == ["open-meteo://guide"]
    assert [template.uri_template for template in templates] == [
        "open-meteo://endpoints/{endpoint}"
    ]
```

**`packages/weather-agents/tests/server/test_stdio.py`**

```python
"""Spawns the real server as a child process. No tool is called, so no network is needed."""

import sys

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import TextContent, TextResourceContents

pytestmark = pytest.mark.anyio


async def test_the_stdio_server_lists_everything_and_serves_a_resource_and_a_prompt():
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        prompts = {prompt.name for prompt in (await client.list_prompts()).prompts}
        guide = await client.read_resource("open-meteo://guide")
        prompt = await client.get_prompt("weekend_check")
    guide_part = guide.contents[0]
    prompt_part = prompt.messages[0].content
    assert isinstance(guide_part, TextResourceContents)
    assert isinstance(prompt_part, TextContent)
    assert len(tools) == 11
    assert prompts == {"weekend_check", "compare_places"}
    assert guide_part.text.startswith("# Open-Meteo guide")
    assert "geocode_search" in prompt_part.text
```

**`packages/weather-agents/tests/live/test_live_stdio.py`**

```python
"""Spawns the real server and calls the real Open-Meteo. Run with `make test-live`."""

import sys

import pytest
from mcp import Client, StdioServerParameters

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_geocode_then_forecast_against_the_real_open_meteo():
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_agents.server"])
    async with Client(params) as client:
        geocoded = await client.call_tool(
            "geocode_search", {"name": "Berlin", "country_code": "DE"}
        )
        assert not geocoded.is_error
        place = geocoded.structured_content["results"][0]
        forecast = await client.call_tool(
            "forecast",
            {"latitude": place["latitude"], "longitude": place["longitude"], "days": 3},
        )
        assert not forecast.is_error
        assert len(forecast.structured_content["table"]["time"]) == 3
```

- [ ] **Step 2: Run the new tests to see where they stand**

Run: `cd packages/weather-agents && uv run --package weather-agents --group dev pytest tests/server/test_surface.py tests/server/test_stdio.py -v`
Expected: `test_surface.py` passes (4 passed). `test_stdio.py` fails because the child process exits at once: `python -m weather_agents.server` has no `__main__.py` yet.

- [ ] **Step 3: Write the entry point**

**`packages/weather-agents/src/weather_agents/server/__main__.py`**

```python
"""Run the server over stdio: `python -m weather_agents.server`."""

from weather_agents.server.app import mcp

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Check `app.py` against the final version**

After Tasks 5 to 10, `app.py` must read exactly like this. Fix any difference.

**`packages/weather-agents/src/weather_agents/server/app.py`**

```python
"""Builds the Open-Meteo MCP server. `mcp` at module level is what `mcp dev` imports."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

import httpx
from mcp.server import MCPServer

from weather_agents.server import prompts, resources
from weather_agents.server.openmeteo.client import OpenMeteoClient
from weather_agents.server.state import AppState
from weather_agents.server.tools import environment, forecast, geocoding, history

HTTP_TIMEOUT_SECONDS = 30
INSTRUCTIONS = (
    "Weather data from Open-Meteo (https://open-meteo.com), licensed CC BY 4.0. "
    "Pick the tool by the time horizon of the question: forecast for the next 16 days, "
    "ensemble for how sure that forecast is, seasonal beyond 16 days, historical for the past, "
    "climate for long-term change. Call geocode_search to turn a place name into coordinates. "
    "Read the open-meteo://guide resource for how the data behaves."
)


def create_server(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    today: Callable[[], date] = date.today,
) -> MCPServer:
    """Build a server. Tests pass a mock `transport` and a fixed `today`."""

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[AppState]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, transport=transport) as http:
            yield AppState(openmeteo=OpenMeteoClient(http), today=today)

    server = MCPServer("weather", instructions=INSTRUCTIONS, lifespan=lifespan)
    geocoding.register(server)
    forecast.register(server)
    history.register(server)
    environment.register(server)
    resources.register(server)
    prompts.register(server, today)
    return server


mcp = create_server()
```

- [ ] **Step 5: Run the whole default suite**

Run: `cd packages/weather-agents && make test`
Expected: `113 passed, 1 deselected`.

- [ ] **Step 6: Run the live test against the real Open-Meteo**

Run: `cd packages/weather-agents && make test-live`
Expected: `1 passed, 113 deselected`. This call needs network access.

- [ ] **Step 7: Lint, format, and type-check the whole repo**

Run from the repo root: `make pre-commit`
Expected: `All checks passed!` from ruff, no files reformatted, and `ty` reports no diagnostics.

- [ ] **Step 8: Check Inspector by hand**

Run: `cd packages/weather-agents && make inspect`
Expected: the SDK downloads MCP Inspector on first use (needs `npx`), then prints a local URL. Open it, connect, and check these by hand, since automated tests cannot drive the browser UI:

1. **Tools** lists 11 tools. Run `geocode_search` with `name` = `Springfield` and see several candidates.
2. Run `forecast` with the coordinates of one candidate and `days` = 3. The result has a `weekday` list.
3. Run `historical` with `start_date` = `1991-01-01` and `end_date` = `2020-12-31`. The result has 12 rows.
4. **Resources** reads `open-meteo://guide`. **Resource templates** shows `open-meteo://endpoints/{endpoint}`, and typing `a` in the argument offers `air-quality`.
5. **Prompts** shows `weekend_check` and `compare_places`. Run `compare_places` with `places` = `a,b,c,d,e,f` and see an error naming `places`.

Stop the server with Ctrl+C.

- [ ] **Step 9: Commit**

```bash
git add packages/weather-agents
git commit -m "[feature] (weather-agents) Add the stdio entry point, surface tests, and the live test"
```

---

### Task 12: Docs check

**Files:**
- Modify: `packages/weather-agents/docs/architecture.md` (through `writing-architecture`)

- [ ] **Step 1: Update the architecture doc**

Use `writing-architecture` in update mode. Read `packages/weather-agents/docs/architecture.md` against the code that now exists and fix every line where the doc and the code disagree. The code wins for anything marked Built. Check at least:

- The components table: the `server` module row and the MCP server row. The `openmeteo` layer, tools, resources, and prompts now exist. The `serve` command, HTTP, sampling, elicitation, and the local-time and dossier tools do not, so their rows stay Planned.
- The Cross-cutting concerns logging row: level 1 logs to stderr only, and `.logs/mcp-server.log` does not exist yet.
- The Data stores row for `.logs/mcp-server.log`: still Planned.
- The Interfaces table: the MCP server surface row now lists 11 tools, 2 resources, and 2 prompts.
- The Deployment section: the server starts with `python -m weather_agents.server` and `make inspect`. The `weather-agents` CLI commands stay Planned.
- The Protocol facts block says `mcp` 2.2.0. The code pins `mcp>=2,<3` and was verified on 2.3.0. Update the version note and the lookup date only if you re-checked the claims.

- [ ] **Step 2: Report the scope doc deviations, without editing it**

`packages/weather-agents/docs/open-meteo-mcp-scope.md` is not in the ownership table, and the PRD calls it the source of truth. Do not edit it. Tell the user these four differences from what was built, and ask whether to update the scope doc:

1. Ensemble covers 15 days, not 16, because the chosen model (`ecmwf_ifs025`) runs 15 days and returns null on day 16.
2. Climate runs to 2049, not 2050, because Open-Meteo's data ends on 2050-01-01.
3. Ensemble "spread" is the population standard deviation across members.
4. Raw daily tables carry a `weekday` list, so the weekend check does not rely on the model's date math.

The guide also leaves out "routes" and "live observations" from the scope doc's "cannot answer" list, since no Open-Meteo page backs them.

- [ ] **Step 3: Confirm the PRD status**

Check that `packages/weather-agents/docs/prd/0001-open-meteo-mcp-server-and-client.md` says `**Status:** Building`. It stays there until every use case is built, including the client and level 2. Do not change any other line.

- [ ] **Step 4: Commit**

```bash
git add packages/weather-agents/docs/architecture.md
git commit -m "[docs] (weather-agents) Update the architecture doc for the level 1 server"
```

---

## Finishing

After Task 12, use `finishing-a-development-branch` to open the pull request for `weather-agents/mcp-server-level-1`. The branch holds only `packages/weather-agents/` files plus `uv.lock`. Leave every change in other homes, including the study workspace and the `AGENTS.md` edit, out of this PR.
