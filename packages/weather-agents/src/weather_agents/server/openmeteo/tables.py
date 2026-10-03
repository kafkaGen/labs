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
