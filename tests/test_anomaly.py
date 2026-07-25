"""Unit tests for :class:`app.tools.anomaly.AnomalyDetector` (Isolation Forest, D8).

Covers successful scoring, determinism / fixed-seed repeatability, the minimum-
sample gate, missing/empty/invalid feature tables, score persistence, the Tool
contract (ToolResult / TraceEntry), logging, and error handling. Feature tables are
built directly (the tool reads ``context.features`` — no dependency on FE/DataLoader).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from app.config import ISOLATION_FOREST
from app.enums import ExecutionStatus, ToolName
from app.schemas import Context, ToolResult, TraceEntry
from app.tools.anomaly import AnomalyDetector

FEATURE_COLS = [
    "txn_count",
    "rolling_sum_max",
    "amount_zscore_max",
    "velocity_per_day",
    "rapid_cash_out_count",
    "sub_threshold_count",
]


def _features(n: int, seed: int = 0) -> pd.DataFrame:
    """Deterministic numeric feature table with ``n`` customers."""
    rng = np.random.default_rng(seed)
    data = {
        "txn_count": rng.integers(1, 50, n).astype(float),
        "rolling_sum_max": rng.uniform(0, 50_000, n),
        "amount_zscore_max": rng.uniform(0, 4, n),
        "velocity_per_day": rng.uniform(0, 10, n),
        "rapid_cash_out_count": rng.integers(0, 5, n).astype(float),
        "sub_threshold_count": rng.integers(0, 6, n).astype(float),
    }
    return pd.DataFrame(data, index=pd.Index([f"C{i}" for i in range(n)], name="customer_id"))


def _run(features: pd.DataFrame | None, params: dict | None = None):
    return AnomalyDetector().run(Context(query="q", features=features), params or {})


def _scores(context: Context) -> dict:
    return context.artifacts["anomaly_scores"]


# ── successful execution ─────────────────────────────────────────────────────


def test_successful_execution_scores_every_entity() -> None:
    context, result, trace = _run(_features(ISOLATION_FOREST.min_samples))
    assert trace.status is ExecutionStatus.SUCCESS
    scores = _scores(context)
    assert len(scores) == ISOLATION_FOREST.min_samples
    assert set(scores) == {f"C{i}" for i in range(ISOLATION_FOREST.min_samples)}
    assert result.output["n_scored"] == ISOLATION_FOREST.min_samples


def test_scores_are_in_unit_interval() -> None:
    context, _, _ = _run(_features(600))
    assert all(0.0 <= s <= 1.0 for s in _scores(context).values())


def test_attribution_is_written() -> None:
    context, _, _ = _run(_features(500))
    attribution = context.artifacts["anomaly_attribution"]
    assert len(attribution) == 500
    sample = next(iter(attribution.values()))
    assert sample["top_feature"] in FEATURE_COLS
    assert sample["deviation"] >= 0.0


# ── determinism / fixed random_state ─────────────────────────────────────────


def test_deterministic_same_input() -> None:
    features = _features(500)
    first, _, _ = _run(features)
    second, _, _ = _run(features)
    assert _scores(first) == _scores(second)


def test_repeatable_across_fresh_instances() -> None:
    features = _features(500, seed=7)
    a, _, _ = AnomalyDetector().run(Context(query="q", features=features), {})
    b, _, _ = AnomalyDetector().run(Context(query="q", features=features), {})
    assert a.artifacts["anomaly_scores"] == b.artifacts["anomaly_scores"]


# ── minimum-sample gate ──────────────────────────────────────────────────────


def test_below_minimum_samples_is_skipped() -> None:
    context, result, trace = _run(_features(ISOLATION_FOREST.min_samples - 1))
    assert trace.status is ExecutionStatus.SKIPPED
    assert trace.rows_out == 0
    assert _scores(context) == {}
    assert "minimum samples" in (result.message or "")


def test_min_rows_param_overrides_gate() -> None:
    # 100 rows < config min (500) but >= the plan-provided min_rows (50) -> runs.
    context, _, trace = _run(_features(100), {"min_rows": 50})
    assert trace.status is ExecutionStatus.SUCCESS
    assert len(_scores(context)) == 100


def test_default_gate_uses_config_min_samples() -> None:
    context, _, trace = _run(_features(100))  # no param -> config min (500)
    assert trace.status is ExecutionStatus.SKIPPED
    assert _scores(context) == {}


@pytest.mark.parametrize("bad", [None, "abc", object()])
def test_malformed_min_rows_falls_back_to_config_without_raising(bad: object) -> None:
    # A bad min_rows param must not raise out of the tool; it falls back to the
    # config gate (500), so 10 rows are skipped.
    context, _, trace = _run(_features(10), {"min_rows": bad})
    assert trace.status is ExecutionStatus.SKIPPED
    assert _scores(context) == {}


# ── missing / empty / invalid features ───────────────────────────────────────


def test_missing_feature_table_is_skipped() -> None:
    context, _, trace = _run(None)
    assert trace.status is ExecutionStatus.SKIPPED
    assert context.artifacts["anomaly_scores"] == {}


def test_empty_feature_table_is_skipped() -> None:
    context, _, trace = _run(pd.DataFrame(columns=FEATURE_COLS))
    assert trace.status is ExecutionStatus.SKIPPED
    assert _scores(context) == {}


def test_non_numeric_only_features_are_skipped() -> None:
    df = pd.DataFrame({"label": ["a"] * 500}, index=[f"C{i}" for i in range(500)])
    _context, result, trace = _run(df)
    assert trace.status is ExecutionStatus.SKIPPED
    assert "numeric" in (result.message or "")


def test_non_numeric_columns_are_ignored() -> None:
    features = _features(500)
    features["segment"] = "retail"  # non-numeric column must be dropped
    _context, result, trace = _run(features)
    assert trace.status is ExecutionStatus.SUCCESS
    assert result.output["n_features"] == len(FEATURE_COLS)
    assert "segment" not in result.output["feature_columns"]


def test_nan_values_do_not_break_scoring() -> None:
    features = _features(500)
    features.iloc[0, 0] = np.nan
    features.iloc[5, 2] = np.inf
    context, _, trace = _run(features)
    assert trace.status is ExecutionStatus.SUCCESS
    assert all(np.isfinite(s) for s in _scores(context).values())


def test_identical_rows_score_zero() -> None:
    features = pd.DataFrame(
        {c: [1.0] * 500 for c in FEATURE_COLS},
        index=[f"C{i}" for i in range(500)],
    )
    context, _, trace = _run(features)
    assert trace.status is ExecutionStatus.SUCCESS
    assert all(s == 0.0 for s in _scores(context).values())


# ── persistence / contract / boundaries ──────────────────────────────────────


def test_score_persistence_in_artifacts() -> None:
    context, _, _ = _run(_features(500))
    assert "anomaly_scores" in context.artifacts
    assert "anomaly_attribution" in context.artifacts


def test_returns_tool_interface_triple() -> None:
    context, result, trace = _run(_features(500))
    assert isinstance(context, Context)
    assert isinstance(result, ToolResult)
    assert isinstance(trace, TraceEntry)
    assert result.tool is ToolName.ANOMALY_DETECTOR
    assert trace.tool is ToolName.ANOMALY_DETECTOR


def test_trace_metadata() -> None:
    _, result, trace = _run(_features(500))
    assert trace.rows_in == 500
    assert trace.rows_out == result.output["n_scored"] == 500
    assert result.output["random_state"] == ISOLATION_FOREST.random_state


def test_does_not_touch_flags() -> None:
    context, _, _ = _run(_features(500))
    assert context.flags == []  # scoring only; classification is the RiskClassifier's job


# ── logging / error handling ─────────────────────────────────────────────────


def test_skip_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.tools.anomaly"):
        _run(_features(10))
    assert any("skipped" in r.message.lower() for r in caplog.records)


def test_model_failure_yields_error_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def __init__(self, *args: object, **kwargs: object) -> None: ...

        def fit(self, matrix: object) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr("app.tools.anomaly.IsolationForest", _Boom)
    _context, result, trace = _run(_features(500))
    assert trace.status is ExecutionStatus.ERROR
    assert trace.rows_out == 0
    assert "boom" in (result.message or "")
