"""Unit tests for :class:`app.tools.aml_patterns.AMLPatternDetector` (Phase 2).

Each rule gets a planted-positive fixture (a customer engineered to trip it) and
a negative/near-miss fixture (a customer that stays just under the threshold, to
guard against off-by-one errors in the windowing). Also covers: empty working_df
(D11), pattern-subset selection via params, and multi-hit aggregation.
"""

from __future__ import annotations

import pandas as pd

from app.config import AML
from app.enums import AMLPattern, ExecutionStatus, ToolName
from app.schemas import Context
from app.tools.aml_patterns import AMLPatternDetector

REQUIRED_COLS = [
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
    df = pd.DataFrame(rows)
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = None
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["amount"] = df["amount"].astype(float)
    return df


def _context(df: pd.DataFrame) -> Context:
    ctx = Context(query="find suspicious activity")
    ctx.raw_df = df
    ctx.working_df = df.copy()
    return ctx


def _run(df: pd.DataFrame, params: dict | None = None):
    detector = AMLPatternDetector()
    return detector.run(_context(df), params or {})


def _hits_for(context: Context, pattern: AMLPattern) -> list[dict]:
    return [h for h in context.artifacts["aml_hits"] if h["pattern"] is pattern]


class TestToolIdentity:
    def test_name(self) -> None:
        assert AMLPatternDetector().name == ToolName.AML_PATTERN_DETECTOR


class TestEmptyInput:
    def test_none_working_df_is_success_with_no_hits(self) -> None:
        ctx = Context(query="x")
        ctx.working_df = None
        context, result, trace = AMLPatternDetector().run(ctx, {})

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 0
        assert trace.rows_out == 0
        assert context.artifacts["aml_hits"] == []
        assert result.output["hit_count"] == 0

    def test_empty_working_df_is_success_with_no_hits(self) -> None:
        df = _df([])
        context, _result, trace = _run(df)

        assert trace.status == ExecutionStatus.SUCCESS
        assert context.artifacts["aml_hits"] == []


class TestMissingColumns:
    def test_missing_required_column_is_error(self) -> None:
        df = pd.DataFrame({"customer_id": ["C1"], "amount": [100.0]})
        _context, result, trace = _run(df)

        assert trace.status == ExecutionStatus.ERROR
        assert "missing required columns" in (result.message or "").lower()


class TestStructuring:
    def test_flags_three_subthreshold_deposits_within_7_days(self) -> None:
        cfg = AML.structuring
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + 2 * i:02d}T10:00:00",
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            }
            for i in range(cfg.min_count)
        ]
        context, _result, trace = _run(_df(rows))

        assert trace.status == ExecutionStatus.SUCCESS
        hits = _hits_for(context, AMLPattern.STRUCTURING)
        assert len(hits) == 1
        hit = hits[0]
        assert hit["entity_id"] == "C1"
        assert hit["entity_type"] == "customer"
        assert hit["rule_id"] == "structuring"
        assert set(hit["evidence"]["txn_ids"]) == {"T0", "T1", "T2"}
        assert hit["evidence"]["count"] == cfg.min_count

    def test_does_not_flag_below_min_count(self) -> None:
        rows = [
            {
                "customer_id": "C1",
                "txn_id": "T0",
                "timestamp": "2023-01-01T10:00:00",
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            },
            {
                "customer_id": "C1",
                "txn_id": "T1",
                "timestamp": "2023-01-02T10:00:00",
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.STRUCTURING) == []

    def test_does_not_flag_when_outside_window(self) -> None:
        """Three qualifying deposits, but spread further apart than window_days."""
        cfg = AML.structuring
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-0{1 + i}-01T10:00:00",  # ~1 month apart
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            }
            for i in range(cfg.min_count)
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.STRUCTURING) == []

    def test_ignores_amounts_outside_band(self) -> None:
        """Deposits above/below the $8k-$9,999 band, even 3+ of them, don't trigger."""
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 10_500.0,  # over CTR line, not "just under" it
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            }
            for i in range(3)
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.STRUCTURING) == []

    def test_ignores_non_deposit_direction(self) -> None:
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 9_000.0,
                "direction": "withdrawal",
                "counterparty_id": "BRANCH1",
            }
            for i in range(3)
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.STRUCTURING) == []


class TestSmurfing:
    def test_flags_five_distinct_sources_within_7_days(self) -> None:
        cfg = AML.smurfing
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 500.0,
                "direction": "deposit",
                "counterparty_id": f"SRC{i}",
            }
            for i in range(cfg.min_distinct_sources)
        ]
        context, _result, trace = _run(_df(rows))

        assert trace.status == ExecutionStatus.SUCCESS
        hits = _hits_for(context, AMLPattern.SMURFING)
        assert len(hits) == 1
        assert hits[0]["evidence"]["distinct_sources"] == cfg.min_distinct_sources
        assert len(hits[0]["evidence"]["source_ids"]) == cfg.min_distinct_sources

    def test_does_not_flag_repeated_single_source(self) -> None:
        """Many deposits, but all from the same one source -> not smurfing."""
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 500.0,
                "direction": "deposit",
                "counterparty_id": "SRC_SAME",
            }
            for i in range(10)
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.SMURFING) == []

    def test_ignores_amounts_at_or_above_max(self) -> None:
        cfg = AML.smurfing
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": cfg.max_amount,  # boundary: must be strictly less than max
                "direction": "deposit",
                "counterparty_id": f"SRC{i}",
            }
            for i in range(cfg.min_distinct_sources)
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.SMURFING) == []


class TestRapidCashOut:
    def test_flags_withdrawal_within_24h_at_or_above_ratio(self) -> None:
        cfg = AML.rapid_cash_out
        rows = [
            {
                "customer_id": "C1",
                "txn_id": "DEP1",
                "timestamp": "2023-01-01T09:00:00",
                "amount": 10_000.0,
                "direction": "deposit",
                "counterparty_id": "X1",
            },
            {
                "customer_id": "C1",
                "txn_id": "WD1",
                "timestamp": "2023-01-01T20:00:00",  # 11h later, within 24h
                "amount": 9_200.0,  # 92% of deposit, above 90% min_ratio
                "direction": "withdrawal",
                "counterparty_id": "X2",
            },
        ]
        context, _result, trace = _run(_df(rows))

        assert trace.status == ExecutionStatus.SUCCESS
        hits = _hits_for(context, AMLPattern.RAPID_CASH_OUT)
        assert len(hits) == 1
        ev = hits[0]["evidence"]
        assert ev["deposit_txn_id"] == "DEP1"
        assert ev["withdrawal_txn_id"] == "WD1"
        assert ev["ratio"] >= cfg.min_ratio

    def test_does_not_flag_when_ratio_too_low(self) -> None:
        rows = [
            {
                "customer_id": "C1",
                "txn_id": "DEP1",
                "timestamp": "2023-01-01T09:00:00",
                "amount": 10_000.0,
                "direction": "deposit",
                "counterparty_id": "X1",
            },
            {
                "customer_id": "C1",
                "txn_id": "WD1",
                "timestamp": "2023-01-01T20:00:00",
                "amount": 5_000.0,  # only 50% of the deposit
                "direction": "withdrawal",
                "counterparty_id": "X2",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.RAPID_CASH_OUT) == []

    def test_does_not_flag_when_outside_window(self) -> None:
        rows = [
            {
                "customer_id": "C1",
                "txn_id": "DEP1",
                "timestamp": "2023-01-01T09:00:00",
                "amount": 10_000.0,
                "direction": "deposit",
                "counterparty_id": "X1",
            },
            {
                "customer_id": "C1",
                "txn_id": "WD1",
                "timestamp": "2023-01-03T09:00:01",  # >24h later
                "amount": 9_500.0,
                "direction": "withdrawal",
                "counterparty_id": "X2",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.RAPID_CASH_OUT) == []

    def test_does_not_flag_withdrawal_before_deposit(self) -> None:
        rows = [
            {
                "customer_id": "C1",
                "txn_id": "WD1",
                "timestamp": "2023-01-01T09:00:00",
                "amount": 9_500.0,
                "direction": "withdrawal",
                "counterparty_id": "X2",
            },
            {
                "customer_id": "C1",
                "txn_id": "DEP1",
                "timestamp": "2023-01-01T20:00:00",
                "amount": 10_000.0,
                "direction": "deposit",
                "counterparty_id": "X1",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.RAPID_CASH_OUT) == []


class TestLayering:
    def test_flags_three_hop_chain_within_72h(self) -> None:
        cfg = AML.layering
        rows = [
            {
                "customer_id": "A",
                "txn_id": "TX1",
                "timestamp": "2023-01-01T00:00:00",
                "amount": 50_000.0,
                "direction": "transfer",
                "counterparty_id": "B",
            },
            {
                "customer_id": "B",
                "txn_id": "TX2",
                "timestamp": "2023-01-01T12:00:00",
                "amount": 49_000.0,
                "direction": "transfer",
                "counterparty_id": "C",
            },
            {
                "customer_id": "C",
                "txn_id": "TX3",
                "timestamp": "2023-01-02T00:00:00",
                "amount": 48_000.0,
                "direction": "transfer",
                "counterparty_id": "D",
            },
        ]
        context, _result, trace = _run(_df(rows))

        assert trace.status == ExecutionStatus.SUCCESS
        hits = _hits_for(context, AMLPattern.LAYERING)
        assert len(hits) == 1
        hit = hits[0]
        assert hit["entity_id"] == "A"
        assert hit["evidence"]["hops"] == cfg.min_hops
        assert hit["evidence"]["chain"] == ["A", "B", "C", "D"]
        assert set(hit["evidence"]["txn_ids"]) == {"TX1", "TX2", "TX3"}

    def test_does_not_flag_short_chain(self) -> None:
        rows = [
            {
                "customer_id": "A",
                "txn_id": "TX1",
                "timestamp": "2023-01-01T00:00:00",
                "amount": 50_000.0,
                "direction": "transfer",
                "counterparty_id": "B",
            },
            {
                "customer_id": "B",
                "txn_id": "TX2",
                "timestamp": "2023-01-01T12:00:00",
                "amount": 49_000.0,
                "direction": "transfer",
                "counterparty_id": "C",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.LAYERING) == []

    def test_does_not_flag_when_chain_exceeds_window(self) -> None:
        rows = [
            {
                "customer_id": "A",
                "txn_id": "TX1",
                "timestamp": "2023-01-01T00:00:00",
                "amount": 50_000.0,
                "direction": "transfer",
                "counterparty_id": "B",
            },
            {
                "customer_id": "B",
                "txn_id": "TX2",
                "timestamp": "2023-01-04T00:00:00",  # 72h later
                "amount": 49_000.0,
                "direction": "transfer",
                "counterparty_id": "C",
            },
            {
                "customer_id": "C",
                "txn_id": "TX3",
                "timestamp": "2023-01-06T00:00:00",  # well past 72h from TX1
                "amount": 48_000.0,
                "direction": "transfer",
                "counterparty_id": "D",
            },
        ]
        context, _, _ = _run(_df(rows))
        assert _hits_for(context, AMLPattern.LAYERING) == []

    def test_cycle_does_not_cause_infinite_loop(self) -> None:
        """A -> B -> A must not hang the DFS (cycle guard) and shouldn't trigger a hit."""
        rows = [
            {
                "customer_id": "A",
                "txn_id": "TX1",
                "timestamp": "2023-01-01T00:00:00",
                "amount": 50_000.0,
                "direction": "transfer",
                "counterparty_id": "B",
            },
            {
                "customer_id": "B",
                "txn_id": "TX2",
                "timestamp": "2023-01-01T12:00:00",
                "amount": 49_000.0,
                "direction": "transfer",
                "counterparty_id": "A",
            },
        ]
        context, _, trace = _run(_df(rows))
        assert trace.status == ExecutionStatus.SUCCESS
        assert _hits_for(context, AMLPattern.LAYERING) == []


class TestPatternSelection:
    def test_params_patterns_narrows_evaluation(self) -> None:
        cfg = AML.structuring
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            }
            for i in range(cfg.min_count)
        ]
        context, result, _trace = _run(
            _df(rows), params={"patterns": [AMLPattern.SMURFING]}
        )

        assert result.output["patterns_evaluated"] == ["smurfing"]
        assert _hits_for(context, AMLPattern.STRUCTURING) == []

    def test_string_pattern_values_accepted(self) -> None:
        _context, result, _ = _run(_df([]), params={"patterns": ["structuring"]})
        assert result.output["patterns_evaluated"] == ["structuring"]

    def test_no_patterns_param_runs_everything(self) -> None:
        _context, result, _trace = _run(_df([]))
        assert set(result.output["patterns_evaluated"]) == {
            AMLPattern.STRUCTURING.value,
            AMLPattern.SMURFING.value,
            AMLPattern.RAPID_CASH_OUT.value,
            AMLPattern.LAYERING.value,
        }


class TestAggregation:
    def test_multiple_customers_each_get_their_own_hit(self) -> None:
        cfg = AML.structuring
        rows: list[dict[str, object]] = []
        for cust in ("C1", "C2"):
            rows.extend(
                {
                    "customer_id": cust,
                    "txn_id": f"{cust}_T{i}",
                    "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                    "amount": 9_000.0,
                    "direction": "deposit",
                    "counterparty_id": "BRANCH1",
                }
                for i in range(cfg.min_count)
            )
        context, _, _ = _run(_df(rows))

        by_customer = context.artifacts["aml_hits_by_customer"]
        assert set(by_customer.keys()) == {"C1", "C2"}
        assert len(by_customer["C1"]) == 1
        assert len(by_customer["C2"]) == 1

    def test_hits_accumulate_across_multiple_runs_on_same_context(self) -> None:
        """A second detector pass on the same context appends, not replaces."""
        cfg = AML.structuring
        rows = [
            {
                "customer_id": "C1",
                "txn_id": f"T{i}",
                "timestamp": f"2023-01-{1 + i:02d}T10:00:00",
                "amount": 9_000.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH1",
            }
            for i in range(cfg.min_count)
        ]
        ctx = _context(_df(rows))
        detector = AMLPatternDetector()
        ctx, _, _ = detector.run(ctx, {"patterns": [AMLPattern.STRUCTURING]})
        ctx, _, _ = detector.run(ctx, {"patterns": [AMLPattern.STRUCTURING]})

        assert len(ctx.artifacts["aml_hits"]) == 2
