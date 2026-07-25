"""Unit tests for :class:`app.tools.filter_tool.Filter`.

Covers entity, date-range (relative + absolute), country, transaction-type, amount
filters; graceful skipping of absent columns; empty subsets; determinism; and the
Tool contract. Small hand-crafted DataFrames — no DataLoader dependency.
"""

from __future__ import annotations

import pandas as pd

from app.enums import ExecutionStatus, IntentType, ToolName
from app.schemas import (
    Context,
    DateRange,
    Filters,
    ToolResult,
    TraceEntry,
    Understanding,
)
from app.tools.filter_tool import Filter

COLS = ["customer_id", "txn_id", "timestamp", "amount", "direction", "counterparty_id", "country", "channel"]


def _df() -> pd.DataFrame:
    rows = [
        ("C1", "T1", "2023-01-01", 100.0, "deposit", "X", "US", "online"),
        ("C1", "T2", "2023-01-20", 9000.0, "deposit", "Y", "US", "branch"),
        ("C2", "T3", "2023-01-25", 500.0, "withdrawal", "Z", "IN", "atm"),
        ("C3", "T4", "2023-01-30", 20000.0, "transfer", "W", "GB", "online"),
    ]
    df = pd.DataFrame(rows, columns=COLS)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _ctx(understanding: Understanding, df: pd.DataFrame | None = None) -> Context:
    frame = _df() if df is None else df
    ctx = Context(query="q", understanding=understanding)
    if frame is not None:
        ctx.working_df = frame
        ctx.dataset_max_timestamp = frame["timestamp"].max()
    return ctx


def _u(**kw) -> Understanding:
    kw.setdefault("intent", IntentType.DETECT_PATTERN)
    return Understanding(**kw)


def _run(understanding: Understanding, df: pd.DataFrame | None = None):
    return Filter().run(_ctx(understanding, df), {})


# ── entity filter ────────────────────────────────────────────────────────────


def test_entity_filter_narrows_to_customer() -> None:
    context, result, trace = _run(_u(intent=IntentType.SINGLE_ENTITY, entities=["C1"]))
    assert trace.status is ExecutionStatus.SUCCESS
    assert set(context.working_df["customer_id"]) == {"C1"}
    assert trace.rows_in == 4
    assert trace.rows_out == 2
    assert "entities" in result.output["applied_filters"]


# ── date range ───────────────────────────────────────────────────────────────


def test_relative_date_resolves_against_dataset_max() -> None:
    # dataset max = 2023-01-30; last 7 days -> keep >= 2023-01-23 (T3, T4).
    context, _, _ = _run(_u(filters=Filters(date_range=DateRange(last_days=7))))
    assert set(context.working_df["txn_id"]) == {"T3", "T4"}


def test_absolute_date_range() -> None:
    context, _, _ = _run(
        _u(filters=Filters(date_range=DateRange(start=pd.Timestamp("2023-01-19"), end=pd.Timestamp("2023-01-26"))))
    )
    assert set(context.working_df["txn_id"]) == {"T2", "T3"}


# ── equality + amount filters ────────────────────────────────────────────────


def test_country_filter() -> None:
    context, _, _ = _run(_u(filters=Filters(country="IN")))
    assert set(context.working_df["txn_id"]) == {"T3"}


def test_transaction_type_maps_to_direction_column() -> None:
    context, result, _ = _run(_u(filters=Filters(transaction_type="withdrawal")))
    assert set(context.working_df["direction"]) == {"withdrawal"}
    assert "transaction_type" in result.output["applied_filters"]


def test_amount_bounds() -> None:
    context, _, _ = _run(_u(filters=Filters(min_amount=400.0, max_amount=10000.0)))
    assert set(context.working_df["txn_id"]) == {"T2", "T3"}


def test_combined_filters_are_anded() -> None:
    context, _, _ = _run(
        _u(entities=["C1"], filters=Filters(min_amount=1000.0))
    )
    assert set(context.working_df["txn_id"]) == {"T2"}  # C1 AND amount>=1000


# ── data safety ──────────────────────────────────────────────────────────────


def test_missing_column_is_skipped_not_crashed() -> None:
    df = _df().drop(columns=["country"])
    _context, result, trace = _run(_u(filters=Filters(country="US")), df)
    assert trace.status is ExecutionStatus.SUCCESS
    assert "country" not in result.output["applied_filters"]
    assert trace.rows_out == 4  # no filter applied -> unchanged


def test_no_filters_leaves_data_unchanged() -> None:
    _context, _, trace = _run(_u())
    assert trace.rows_in == trace.rows_out == 4


def test_empty_result_is_success() -> None:
    context, _, trace = _run(_u(entities=["NOPE"]))
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_out == 0
    assert context.working_df.empty


def test_no_dataframe_is_graceful() -> None:
    ctx = Context(query="q", understanding=_u(entities=["C1"]))
    _, _, trace = Filter().run(ctx, {})
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_in == 0


def test_no_understanding_leaves_data_unchanged() -> None:
    ctx = Context(query="q", working_df=_df())
    _context, _, trace = Filter().run(ctx, {})
    assert trace.rows_out == 4


# ── contract & determinism ───────────────────────────────────────────────────


def test_returns_tool_triple() -> None:
    context, result, trace = _run(_u(entities=["C1"]))
    assert isinstance(context, Context)
    assert isinstance(result, ToolResult)
    assert isinstance(trace, TraceEntry)
    assert result.tool is ToolName.FILTER
    assert trace.tool is ToolName.FILTER


def test_deterministic() -> None:
    u = _u(entities=["C1"], filters=Filters(min_amount=1000.0))
    first = list(_run(u)[0].working_df["txn_id"])
    second = list(_run(u)[0].working_df["txn_id"])
    assert first == second
