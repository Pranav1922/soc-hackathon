"""Unit tests for :class:`app.tools.feature_engineering.FeatureEngineering`.

Covers the six architecture-defined feature families, family selection, unknown-
family skipping, empty/absent/missing-value data, determinism, and the Tool contract
(updated Context, ToolResult, TraceEntry). Feature values are asserted on small,
hand-crafted DataFrames — no dependency on the real dataset or DataLoader.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.config import AML
from app.enums import ExecutionStatus, ToolName
from app.schemas import Context, ToolResult, TraceEntry
from app.tools.feature_engineering import FeatureEngineering

COLS = [
    "customer_id",
    "txn_id",
    "timestamp",
    "amount",
    "direction",
    "counterparty_id",
    "country",
    "channel",
]


def _df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLS)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["amount"] = df["amount"].astype(float)
    return df


def _row(cid, tid, ts, amount, direction="deposit") -> dict:
    return {
        "customer_id": cid,
        "txn_id": tid,
        "timestamp": ts,
        "amount": amount,
        "direction": direction,
        "counterparty_id": "X",
        "country": "US",
        "channel": "online",
    }


# C1: 2 deposits (one in the structuring band) + 1 withdrawal within 24h.
# C2: a single withdrawal, no deposits.
SAMPLE = _df(
    [
        _row("C1", "T1", "2023-01-01T10:00:00", 100.0, "deposit"),
        _row("C1", "T2", "2023-01-01T12:00:00", 9000.0, "deposit"),
        _row("C1", "T3", "2023-01-01T13:00:00", 50.0, "withdrawal"),
        _row("C2", "T4", "2023-02-01T09:00:00", 200.0, "withdrawal"),
    ]
)


def _ctx(df: pd.DataFrame | None) -> Context:
    return Context(query="q", working_df=df)


def _run(df: pd.DataFrame | None, params: dict | None = None):
    return FeatureEngineering().run(_ctx(df), params or {})


# ── successful generation ────────────────────────────────────────────────────


def test_all_families_computed_by_default() -> None:
    context, _result, trace = _run(SAMPLE)
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    features = context.features
    assert list(features.index) == ["C1", "C2"]  # sorted customers
    assert list(features.columns) == [
        "txn_count",
        "rolling_sum_max",
        "amount_zscore_max",
        "velocity_per_day",
        "rapid_cash_out_count",
        "sub_threshold_count",
    ]


def test_feature_values_are_correct() -> None:
    context, _, _ = _run(SAMPLE)
    f = context.features
    assert f is not None
    assert f.loc["C1", "txn_count"] == 3
    assert f.loc["C2", "txn_count"] == 1
    # 9000 is inside the structuring band [8000, 9999]; nothing else is.
    assert f.loc["C1", "sub_threshold_count"] == 1
    assert f.loc["C2", "sub_threshold_count"] == 0
    # One withdrawal (T3) within 24h of a preceding deposit for C1; none for C2.
    assert f.loc["C1", "rapid_cash_out_count"] == 1
    assert f.loc["C2", "rapid_cash_out_count"] == 0
    # All C1 txns on one day -> rolling sum = 100+9000+50.
    assert f.loc["C1", "rolling_sum_max"] == pytest.approx(9150.0)
    assert f.loc["C2", "rolling_sum_max"] == pytest.approx(200.0)
    # C1 spans <1 day -> velocity = 3 txns / 1 day.
    assert f.loc["C1", "velocity_per_day"] == pytest.approx(3.0)
    # Single-transaction customer has undefined std -> deviation 0.0.
    assert f.loc["C2", "amount_zscore_max"] == pytest.approx(0.0)
    assert f.loc["C1", "amount_zscore_max"] > 0.0


def test_config_drives_sub_threshold_band() -> None:
    # A value just below the band's lower bound must NOT count.
    df = _df([_row("C1", "T1", "2023-01-01T10:00:00", AML.structuring.amount_min - 1)])
    context, _, _ = _run(df, {"families": ["sub_threshold"]})
    assert context.features is not None
    assert context.features.loc["C1", "sub_threshold_count"] == 0


# ── family selection ─────────────────────────────────────────────────────────


def test_only_requested_families_are_computed() -> None:
    context, result, _ = _run(SAMPLE, {"families": ["sub_threshold", "frequency"]})
    assert context.features is not None
    assert list(context.features.columns) == ["txn_count", "sub_threshold_count"]
    assert result.output["computed_families"] == ["frequency", "sub_threshold"]


def test_unknown_families_are_skipped_not_invented() -> None:
    context, result, trace = _run(
        SAMPLE, {"families": ["distinct_sources", "transfer_chain", "frequency"]}
    )
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    assert list(context.features.columns) == ["txn_count"]
    assert "distinct_sources" in result.output["skipped_families"]
    assert "transfer_chain" in result.output["skipped_families"]


# ── data safety ──────────────────────────────────────────────────────────────


def test_empty_dataset_yields_empty_features_success() -> None:
    context, _result, trace = _run(pd.DataFrame(columns=COLS))
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_out == 0
    assert context.features is not None
    assert context.features.empty


def test_no_dataframe_in_context_is_graceful() -> None:
    context = Context(query="q")  # neither working_df nor raw_df
    _, _result, trace = FeatureEngineering().run(context, {})
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_in == 0
    assert context.features is not None
    assert context.features.empty


def test_falls_back_to_raw_df_when_working_df_absent() -> None:
    context = Context(query="q", raw_df=SAMPLE)
    _, _, trace = FeatureEngineering().run(context, {})
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    assert list(context.features.index) == ["C1", "C2"]


def test_missing_values_do_not_crash_or_corrupt() -> None:
    df = _df(
        [
            _row("C1", "T1", "2023-01-01T10:00:00", 9000.0, "deposit"),
            _row("C1", "T2", "2023-01-02T10:00:00", float("nan"), "deposit"),
        ]
    )
    context, _, trace = _run(df)
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    f = context.features
    # NaN amount is excluded from the band; the finite 9000 still counts.
    assert f.loc["C1", "sub_threshold_count"] == 1
    assert pd.notna(f.loc["C1", "amount_zscore_max"])


def test_no_feature_column_ever_contains_nan() -> None:
    # A customer whose amounts are all NaN must still yield finite features
    # (rolling_sum in particular must not leak NaN).
    df = _df(
        [
            _row("C1", "T1", "2023-01-01T10:00:00", float("nan"), "deposit"),
            _row("C1", "T2", "2023-01-02T10:00:00", float("nan"), "deposit"),
        ]
    )
    context, _, trace = _run(df)
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    assert not context.features.isna().any().any()
    assert context.features.loc["C1", "rolling_sum_max"] == 0.0


def test_missing_required_column_skips_only_that_family() -> None:
    # Drop 'direction' -> rapid_cash_out cannot be computed; others still can.
    df = SAMPLE.drop(columns=["direction"])
    context, result, trace = _run(df, {"families": ["frequency", "rapid_cash_out"]})
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    assert list(context.features.columns) == ["txn_count"]
    assert "rapid_cash_out" in result.output["skipped_families"]


def test_missing_customer_id_on_nonempty_data_is_error() -> None:
    df = SAMPLE.drop(columns=["customer_id"])
    context, result, trace = _run(df)
    assert trace.status is ExecutionStatus.ERROR
    assert trace.rows_out == 0
    assert context.features is None  # not corrupted
    assert "customer_id" in (result.message or "")


def test_unexpected_column_order_is_handled() -> None:
    shuffled = SAMPLE[list(reversed(COLS))]
    context, _, trace = _run(shuffled)
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.features is not None
    assert list(context.features.index) == ["C1", "C2"]


# ── determinism & contract ───────────────────────────────────────────────────


def test_deterministic_output() -> None:
    first, _, _ = _run(SAMPLE)
    second, _, _ = _run(SAMPLE)
    assert first.features is not None
    assert second.features is not None
    pd.testing.assert_frame_equal(first.features, second.features)


def test_returns_tool_interface_triple() -> None:
    context, result, trace = _run(SAMPLE)
    assert isinstance(context, Context)
    assert isinstance(result, ToolResult)
    assert isinstance(trace, TraceEntry)
    assert result.tool is ToolName.FEATURE_ENGINEERING
    assert trace.tool is ToolName.FEATURE_ENGINEERING


def test_trace_and_result_metadata() -> None:
    _, result, trace = _run(SAMPLE)
    assert trace.rows_in == 4
    assert trace.rows_out == 2
    assert result.output["n_customers"] == 2
    assert set(result.output) == {
        "n_customers",
        "feature_columns",
        "computed_families",
        "skipped_families",
    }


def test_does_not_touch_flags_or_charts() -> None:
    context, _, _ = _run(SAMPLE)
    # Feature Engineering only prepares features; it must not detect/score/explain.
    assert context.flags == []
    assert context.charts == []
