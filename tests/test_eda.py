"""Unit tests for :class:`app.tools.eda.EDA`.

Covers profiling stats, baseline chart production, empty/missing data, missing
columns, determinism, and the Tool contract. Hand-crafted DataFrames only.
"""

from __future__ import annotations

import pandas as pd

from app.enums import ExecutionStatus, ToolName
from app.schemas import ChartSpec, Context, ToolResult, TraceEntry
from app.tools.eda import EDA

COLS = ["customer_id", "txn_id", "timestamp", "amount", "direction", "counterparty_id", "country", "channel"]


def _df() -> pd.DataFrame:
    rows = [
        ("C1", "T1", "2023-01-01", 100.0, "deposit", "X", "US", "online"),
        ("C1", "T2", "2023-01-01", 9000.0, "deposit", "Y", "US", "branch"),
        ("C2", "T3", "2023-01-02", 500.0, "withdrawal", "Z", "IN", "atm"),
    ]
    df = pd.DataFrame(rows, columns=COLS)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _run(df: pd.DataFrame | None):
    ctx = Context(query="q")
    if df is not None:
        ctx.working_df = df
    return EDA().run(ctx, {})


def _stats(context: Context) -> dict:
    return context.artifacts["eda"]


# ── profiling ────────────────────────────────────────────────────────────────


def test_profiles_basic_stats() -> None:
    context, result, trace = _run(_df())
    assert trace.status is ExecutionStatus.SUCCESS
    stats = _stats(context)
    assert stats["n_rows"] == 3
    assert stats["n_customers"] == 2
    assert stats["amount"]["max"] == 9000.0
    assert stats["amount"]["min"] == 100.0
    assert stats["top_countries"] == {"US": 2, "IN": 1}
    assert result.output["n_rows"] == 3


def test_null_counts_reported() -> None:
    df = _df()
    df.loc[0, "amount"] = None
    context, _, _ = _run(df)
    assert _stats(context)["null_counts"]["amount"] == 1


# ── charts ───────────────────────────────────────────────────────────────────


def test_produces_baseline_charts() -> None:
    context, _, trace = _run(_df())
    types = {c.type for c in context.charts}
    assert {"histogram", "timeseries", "bar"} <= types
    assert trace.rows_out == len(context.charts)
    for chart in context.charts:
        assert isinstance(chart, ChartSpec)
        assert "data" in chart.spec and "layout" in chart.spec  # native Plotly


def test_charts_appended_not_overwritten() -> None:
    ctx = Context(query="q", working_df=_df())
    ctx.charts.append(ChartSpec(type="pre-existing", title="x"))
    out, _, _ = EDA().run(ctx, {})
    assert out.charts[0].type == "pre-existing"
    assert len(out.charts) > 1


# ── data safety ──────────────────────────────────────────────────────────────


def test_empty_dataframe_is_success_with_no_charts() -> None:
    context, _, trace = _run(pd.DataFrame(columns=COLS))
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.charts == []
    assert _stats(context)["n_rows"] == 0


def test_no_dataframe_is_graceful() -> None:
    context, _, trace = _run(None)
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_in == 0
    assert _stats(context)["n_rows"] == 0


def test_missing_columns_are_skipped() -> None:
    df = _df().drop(columns=["country", "amount"])
    context, _, trace = _run(df)
    assert trace.status is ExecutionStatus.SUCCESS
    stats = _stats(context)
    assert "amount" not in stats
    assert "top_countries" not in stats
    assert stats["n_rows"] == 3  # profiling still succeeds


# ── contract & determinism ───────────────────────────────────────────────────


def test_returns_tool_triple() -> None:
    context, result, trace = _run(_df())
    assert isinstance(context, Context)
    assert isinstance(result, ToolResult)
    assert isinstance(trace, TraceEntry)
    assert result.tool is ToolName.EDA
    assert trace.tool is ToolName.EDA


def test_does_not_touch_flags() -> None:
    context, _, _ = _run(_df())
    assert context.flags == []  # EDA only profiles


def test_deterministic() -> None:
    first, _, _ = _run(_df())
    second, _, _ = _run(_df())
    assert _stats(first) == _stats(second)
    assert [c.type for c in first.charts] == [c.type for c in second.charts]
