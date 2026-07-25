"""AML rule tests (D18).

Config-contract checks guard against threshold drift; rule fixtures exercise every
P0 deterministic rule (structuring, smurfing, rapid cash-out) plus data-safety and
contract edge cases. Fixtures are small, hand-crafted DataFrames — no dependency on
the real dataset or DataLoader.
"""

from __future__ import annotations

import pandas as pd

from app.config import AML, CTR_THRESHOLD
from app.enums import ExecutionStatus, ToolName
from app.schemas import Context, ToolResult, TraceEntry
from app.tools.aml_patterns import AMLPatternDetector

# ── config-contract guards ───────────────────────────────────────────────────


def test_structuring_thresholds_match_frozen_decision() -> None:
    assert AML.structuring.min_count == 3
    assert AML.structuring.amount_min == 8_000.0
    assert AML.structuring.amount_max == 9_999.0
    assert AML.structuring.window_days == 7
    assert AML.structuring.amount_max < CTR_THRESHOLD == 10_000.0


def test_smurfing_and_rapid_cash_out_thresholds() -> None:
    assert AML.smurfing.min_distinct_sources == 5
    assert AML.smurfing.max_amount == 3_000.0
    assert AML.rapid_cash_out.min_ratio == 0.90
    assert AML.rapid_cash_out.window_hours == 24


# ── fixtures ─────────────────────────────────────────────────────────────────

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


def _row(cid, tid, ts, amount, direction="deposit", src="X") -> dict:
    return {
        "customer_id": cid,
        "txn_id": tid,
        "timestamp": ts,
        "amount": amount,
        "direction": direction,
        "counterparty_id": src,
        "country": "US",
        "channel": "online",
    }


def _run(df: pd.DataFrame | None, params: dict | None = None):
    return AMLPatternDetector().run(Context(query="q", working_df=df), params or {})


def _hits(context: Context) -> list[dict]:
    return context.artifacts["rule_hits"]


# ── structuring ──────────────────────────────────────────────────────────────

STRUCTURING = _df(
    [
        _row("C1", "T1", "2023-01-01T10:00:00", 9000.0, "deposit"),
        _row("C1", "T2", "2023-01-02T10:00:00", 9200.0, "deposit"),
        _row("C1", "T3", "2023-01-03T10:00:00", 9500.0, "deposit"),
        # C2: only 2 in-band deposits -> below min_count.
        _row("C2", "T4", "2023-01-01T10:00:00", 9100.0, "deposit"),
        _row("C2", "T5", "2023-01-02T10:00:00", 9300.0, "deposit"),
        # C3: 3 deposits but below the band -> not structuring.
        _row("C3", "T6", "2023-01-01T10:00:00", 5000.0, "deposit"),
        _row("C3", "T7", "2023-01-02T10:00:00", 5000.0, "deposit"),
        _row("C3", "T8", "2023-01-03T10:00:00", 5000.0, "deposit"),
    ]
)


def test_structuring_flags_planted_customer() -> None:
    context, _result, trace = _run(STRUCTURING, {"patterns": ["structuring"]})
    assert trace.status is ExecutionStatus.SUCCESS
    hits = _hits(context)
    assert [h["entity_id"] for h in hits] == ["C1"]  # only C1
    hit = hits[0]
    assert hit["pattern"] == "structuring"
    assert hit["rule_id"] == "structuring_sub_threshold_clustering"
    assert sorted(hit["evidence"]["txn_ids"]) == ["T1", "T2", "T3"]
    assert hit["evidence"]["count"] == 3


def test_structuring_outside_window_not_flagged() -> None:
    df = _df(
        [
            _row("C1", "T1", "2023-01-01T10:00:00", 9000.0, "deposit"),
            _row("C1", "T2", "2023-01-05T10:00:00", 9200.0, "deposit"),
            _row("C1", "T3", "2023-01-20T10:00:00", 9500.0, "deposit"),  # >7d apart
        ]
    )
    context, _, _ = _run(df, {"patterns": ["structuring"]})
    assert _hits(context) == []


# ── smurfing ─────────────────────────────────────────────────────────────────


def test_smurfing_flags_multi_source_account() -> None:
    rows = [
        _row("C1", f"T{i}", f"2023-01-0{i}T10:00:00", 1000.0, "deposit", src=f"S{i}")
        for i in range(1, 6)  # 5 distinct sources, all < $3000, within 7 days
    ]
    context, _, trace = _run(_df(rows), {"patterns": ["smurfing"]})
    assert trace.status is ExecutionStatus.SUCCESS
    hits = _hits(context)
    assert len(hits) == 1
    assert hits[0]["pattern"] == "smurfing"
    assert hits[0]["evidence"]["distinct_sources"] == 5
    assert hits[0]["evidence"]["sources"] == ["S1", "S2", "S3", "S4", "S5"]


def test_smurfing_below_source_threshold_not_flagged() -> None:
    rows = [
        _row("C1", f"T{i}", f"2023-01-0{i}T10:00:00", 1000.0, "deposit", src=f"S{i}")
        for i in range(1, 5)  # only 4 distinct sources
    ]
    context, _, _ = _run(_df(rows), {"patterns": ["smurfing"]})
    assert _hits(context) == []


# ── rapid cash-out ───────────────────────────────────────────────────────────


def test_rapid_cash_out_flagged() -> None:
    df = _df(
        [
            _row("C1", "D1", "2023-01-01T10:00:00", 1000.0, "deposit"),
            _row("C1", "W1", "2023-01-01T12:00:00", 950.0, "withdrawal"),  # 95%, 2h
        ]
    )
    context, _, _ = _run(df, {"patterns": ["rapid_cash_out"]})
    hits = _hits(context)
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "rapid_cash_out_deposit_withdrawal"
    assert hits[0]["evidence"]["deposit_txn_id"] == "D1"
    assert hits[0]["evidence"]["withdrawal_txn_id"] == "W1"
    assert hits[0]["evidence"]["ratio"] == 0.95


def test_rapid_cash_out_below_ratio_or_outside_window_not_flagged() -> None:
    df = _df(
        [
            _row("C1", "D1", "2023-01-01T10:00:00", 1000.0, "deposit"),
            _row("C1", "W1", "2023-01-01T12:00:00", 500.0, "withdrawal"),  # 50% ratio
            _row("C2", "D2", "2023-01-01T10:00:00", 1000.0, "deposit"),
            _row("C2", "W2", "2023-01-05T10:00:00", 950.0, "withdrawal"),  # >24h later
        ]
    )
    context, _, _ = _run(df, {"patterns": ["rapid_cash_out"]})
    assert _hits(context) == []


# ── pattern selection ────────────────────────────────────────────────────────


def test_only_requested_patterns_are_evaluated() -> None:
    _, result, _ = _run(STRUCTURING, {"patterns": ["structuring"]})
    assert result.output["patterns_evaluated"] == ["structuring"]
    assert "smurfing" not in result.output["patterns_evaluated"]


def test_all_p0_rules_evaluated_when_patterns_absent() -> None:
    _, result, _ = _run(STRUCTURING, {})
    assert result.output["patterns_evaluated"] == [
        "structuring",
        "smurfing",
        "rapid_cash_out",
    ]


def test_layering_is_skipped_as_p2_not_crashed() -> None:
    context, result, trace = _run(STRUCTURING, {"patterns": ["layering"]})
    assert trace.status is ExecutionStatus.SUCCESS
    assert "layering" in result.output["patterns_skipped"]
    assert _hits(context) == []


def test_unknown_pattern_is_skipped() -> None:
    _, result, _ = _run(STRUCTURING, {"patterns": ["transfer_chain"]})
    assert "transfer_chain" in result.output["patterns_skipped"]


# ── data safety ──────────────────────────────────────────────────────────────


def test_empty_dataset_yields_no_hits_success() -> None:
    context, _result, trace = _run(pd.DataFrame(columns=COLS))
    assert trace.status is ExecutionStatus.SUCCESS
    assert trace.rows_out == 0
    assert _hits(context) == []


def test_no_dataframe_is_graceful() -> None:
    context = Context(query="q")
    _, _, trace = AMLPatternDetector().run(context, {})
    assert trace.status is ExecutionStatus.SUCCESS
    assert context.artifacts["rule_hits"] == []


def test_missing_customer_id_is_error_without_corrupting_context() -> None:
    df = STRUCTURING.drop(columns=["customer_id"])
    context, result, trace = _run(df)
    assert trace.status is ExecutionStatus.ERROR
    assert trace.rows_out == 0
    assert "rule_hits" not in context.artifacts  # not corrupted
    assert "customer_id" in (result.message or "")


def test_missing_optional_column_skips_only_that_rule() -> None:
    # Drop counterparty_id -> smurfing cannot run; structuring/rapid still can.
    df = STRUCTURING.drop(columns=["counterparty_id"])
    _, result, trace = _run(df)
    assert trace.status is ExecutionStatus.SUCCESS
    assert "smurfing" in result.output["patterns_skipped"]
    assert "structuring" in result.output["patterns_evaluated"]


# ── contract & determinism ───────────────────────────────────────────────────


def test_returns_tool_interface_triple() -> None:
    context, result, trace = _run(STRUCTURING)
    assert isinstance(context, Context)
    assert isinstance(result, ToolResult)
    assert isinstance(trace, TraceEntry)
    assert result.tool is ToolName.AML_PATTERN_DETECTOR
    assert trace.tool is ToolName.AML_PATTERN_DETECTOR


def test_does_not_touch_flags() -> None:
    context, _, _ = _run(STRUCTURING)
    assert context.flags == []  # scoring/flagging is the RiskClassifier's job


def test_trace_and_result_metadata() -> None:
    _, result, trace = _run(STRUCTURING, {"patterns": ["structuring"]})
    assert trace.rows_in == len(STRUCTURING)
    assert trace.rows_out == result.output["n_hits"] == 1
    assert set(result.output) == {
        "n_hits",
        "patterns_evaluated",
        "patterns_skipped",
        "hits_by_pattern",
    }


def test_deterministic_output() -> None:
    first, _, _ = _run(STRUCTURING)
    second, _, _ = _run(STRUCTURING)
    assert _hits(first) == _hits(second)


def test_works_when_feature_table_absent() -> None:
    # Detection reads working_df, not context.features; a missing feature table
    # (features=None) must not prevent rule hits.
    context = Context(query="q", working_df=STRUCTURING)
    assert context.features is None
    out, _, trace = AMLPatternDetector().run(context, {"patterns": ["structuring"]})
    assert trace.status is ExecutionStatus.SUCCESS
    assert [h["entity_id"] for h in _hits(out)] == ["C1"]


def test_nan_amounts_are_excluded_from_rules() -> None:
    # A NaN amount must be ignored (not counted in the sub-threshold band), so a
    # customer with only 2 valid in-band deposits is not flagged.
    df = _df(
        [
            _row("C1", "T1", "2023-01-01T10:00:00", float("nan"), "deposit"),
            _row("C1", "T2", "2023-01-02T10:00:00", 9000.0, "deposit"),
            _row("C1", "T3", "2023-01-03T10:00:00", 9200.0, "deposit"),
        ]
    )
    context, _, trace = _run(df, {"patterns": ["structuring"]})
    assert trace.status is ExecutionStatus.SUCCESS
    assert _hits(context) == []
