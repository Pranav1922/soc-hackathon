"""Unit tests for :class:`app.tools.visualizer.Visualizer` (Phase 2, Developer B).

Each chart builder is tested for its happy path and its graceful-skip path
(missing/empty required data returns ``None``, never raises — D11).
"""

from __future__ import annotations

import pandas as pd

from app.config import AML
from app.enums import (
    AMLPattern,
    EscalationAction,
    ExecutionStatus,
    RiskLevel,
)
from app.schemas import Context, RiskResult
from app.tools.visualizer import Visualizer


def _hit(pattern: AMLPattern, evidence: dict) -> dict:
    return {
        "pattern": pattern,
        "rule_id": pattern.value,
        "entity_id": "C1",
        "entity_type": "customer",
        "evidence": evidence,
    }


def _flag(
    entity_id: str = "C1",
    risk: RiskLevel = RiskLevel.HIGH,
    score: float = 0.9,
    rule_hits: list[dict] | None = None,
    rule_severity: float = 1.0,
    anomaly_score: float = 0.0,
) -> RiskResult:
    return RiskResult(
        entity_id=entity_id,
        entity_type="customer",
        risk=risk,
        score=score,
        explanation="x",
        action=EscalationAction.REPORT,
        evidence={
            "rule_hits": rule_hits or [],
            "rule_severity": rule_severity,
            "anomaly_score": anomaly_score,
        },
    )


def _txn_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _run(context: Context):
    return Visualizer().run(context, {})


class TestEmptyContext:
    def test_no_flags_and_no_working_df_produces_no_charts(self) -> None:
        ctx = Context(query="q")
        context, result, trace = _run(ctx)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_out == 0
        assert context.charts == []
        assert result.output["charts_produced"] == 0


class TestTimelineChart:
    def test_produces_timeline_when_flagged_txns_present(self) -> None:
        ctx = Context(query="q")
        ctx.working_df = _txn_df(
            [
                {
                    "customer_id": "C1",
                    "txn_id": "T1",
                    "timestamp": "2023-01-01T10:00:00",
                    "amount": 9000.0,
                    "direction": "deposit",
                }
            ]
        )
        ctx.flags = [
            _flag(
                rule_hits=[
                    _hit(AMLPattern.STRUCTURING, {"txn_ids": ["T1"]}),
                ]
            )
        ]
        context, _result, _trace = _run(ctx)

        timeline = next(c for c in context.charts if c.type == "timeline")
        assert timeline.spec["data"][0]["x"] == ["2023-01-01 10:00:00"]
        assert timeline.spec["data"][0]["y"] == [9000.0]

    def test_handles_rapid_cash_out_deposit_withdrawal_ids(self) -> None:
        ctx = Context(query="q")
        ctx.working_df = _txn_df(
            [
                {
                    "customer_id": "C1",
                    "txn_id": "D1",
                    "timestamp": "2023-01-01T09:00:00",
                    "amount": 10000.0,
                    "direction": "deposit",
                },
                {
                    "customer_id": "C1",
                    "txn_id": "W1",
                    "timestamp": "2023-01-01T20:00:00",
                    "amount": 9200.0,
                    "direction": "withdrawal",
                },
            ]
        )
        ctx.flags = [
            _flag(
                rule_hits=[
                    _hit(
                        AMLPattern.RAPID_CASH_OUT,
                        {"deposit_txn_id": "D1", "withdrawal_txn_id": "W1"},
                    )
                ]
            )
        ]
        context, _result, _trace = _run(ctx)

        timeline = next(c for c in context.charts if c.type == "timeline")
        assert len(timeline.spec["data"][0]["x"]) == 2

    def test_skipped_when_no_working_df(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(rule_hits=[_hit(AMLPattern.STRUCTURING, {"txn_ids": ["T1"]})])]
        context, _result, _trace = _run(ctx)

        assert not any(c.type == "timeline" for c in context.charts)

    def test_skipped_when_no_flags(self) -> None:
        ctx = Context(query="q")
        ctx.working_df = _txn_df(
            [
                {
                    "customer_id": "C1",
                    "txn_id": "T1",
                    "timestamp": "2023-01-01T10:00:00",
                    "amount": 100.0,
                    "direction": "deposit",
                }
            ]
        )
        context, _result, _trace = _run(ctx)
        assert not any(c.type == "timeline" for c in context.charts)


class TestAmountHistogramChart:
    def test_produces_histogram_with_ctr_line(self) -> None:
        ctx = Context(query="q")
        ctx.working_df = _txn_df(
            [
                {
                    "customer_id": "C1",
                    "txn_id": "T1",
                    "timestamp": "2023-01-01T10:00:00",
                    "amount": 5000.0,
                    "direction": "deposit",
                },
                {
                    "customer_id": "C1",
                    "txn_id": "T2",
                    "timestamp": "2023-01-02T10:00:00",
                    "amount": 200.0,
                    "direction": "withdrawal",
                },
            ]
        )
        context, _result, _trace = _run(ctx)

        hist = next(c for c in context.charts if c.type == "histogram")
        assert hist.spec["data"][0]["x"] == [5000.0]  # withdrawal excluded
        assert hist.spec["layout"]["shapes"][0]["x0"] == AML.ctr_threshold

    def test_skipped_when_no_deposits(self) -> None:
        ctx = Context(query="q")
        ctx.working_df = _txn_df(
            [
                {
                    "customer_id": "C1",
                    "txn_id": "T1",
                    "timestamp": "2023-01-01T10:00:00",
                    "amount": 200.0,
                    "direction": "withdrawal",
                }
            ]
        )
        context, _result, _trace = _run(ctx)
        assert not any(c.type == "histogram" for c in context.charts)

    def test_skipped_when_no_working_df(self) -> None:
        ctx = Context(query="q")
        context, _result, _trace = _run(ctx)
        assert not any(c.type == "histogram" for c in context.charts)


class TestEntitySignalChart:
    def test_produces_grouped_bars_per_entity(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [
            _flag(entity_id="C1", score=0.9, rule_severity=1.0, anomaly_score=0.2),
            _flag(entity_id="C2", score=0.5, rule_severity=0.5, anomaly_score=0.1),
        ]
        context, _result, _trace = _run(ctx)

        chart = next(c for c in context.charts if c.type == "entity_signals")
        assert chart.spec["data"][0]["x"] == ["C1", "C2"]  # sorted by score desc
        assert chart.spec["data"][2]["y"] == [0.9, 0.5]  # final score trace

    def test_caps_at_max_entity_bars(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(entity_id=f"C{i}", score=i / 100) for i in range(20)]
        context, _result, _trace = _run(ctx)

        chart = next(c for c in context.charts if c.type == "entity_signals")
        assert len(chart.spec["data"][0]["x"]) == 10

    def test_skipped_when_no_flags(self) -> None:
        ctx = Context(query="q")
        context, _result, _trace = _run(ctx)
        assert not any(c.type == "entity_signals" for c in context.charts)


class TestRiskDistributionChart:
    def test_counts_each_band(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [
            _flag(entity_id="C1", risk=RiskLevel.LOW),
            _flag(entity_id="C2", risk=RiskLevel.MEDIUM),
            _flag(entity_id="C3", risk=RiskLevel.HIGH),
            _flag(entity_id="C4", risk=RiskLevel.HIGH),
        ]
        context, _result, _trace = _run(ctx)

        chart = next(c for c in context.charts if c.type == "risk_distribution")
        assert chart.spec["data"][0]["x"] == ["Low", "Medium", "High"]
        assert chart.spec["data"][0]["y"] == [1, 1, 2]

    def test_skipped_when_no_flags(self) -> None:
        ctx = Context(query="q")
        context, _result, _trace = _run(ctx)
        assert not any(c.type == "risk_distribution" for c in context.charts)


class TestRunMethod:
    def test_charts_accumulate_not_overwrite(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag()]
        ctx.charts = []  # start clean
        context, _result, trace = _run(ctx)
        first_count = len(context.charts)
        assert first_count > 0

        context2, _result2, _trace2 = Visualizer().run(context, {})
        assert len(context2.charts) == first_count * 2

    def test_trace_rows_in_is_flag_count(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(entity_id="C1"), _flag(entity_id="C2")]
        _context, _result, trace = _run(ctx)
        assert trace.rows_in == 2


class TestDeterminism:
    def test_same_input_yields_same_charts(self) -> None:
        ctx1 = Context(query="q")
        ctx1.flags = [_flag()]
        ctx2 = Context(query="q")
        ctx2.flags = [_flag()]

        context1, _, _ = _run(ctx1)
        context2, _, _ = _run(ctx2)

        assert [c.type for c in context1.charts] == [c.type for c in context2.charts]
        assert context1.charts == context2.charts
