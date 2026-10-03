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
