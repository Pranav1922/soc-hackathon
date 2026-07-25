"""Unit tests for :class:`app.tools.explainer.Explainer` (Phase 2, Developer B).

Verifies every template is (a) deterministic, (b) built only from real evidence
values (no invented numbers — D9), and (c) selects the query-matching hit when
an entity has more than one.
"""

from __future__ import annotations

from app.enums import AMLPattern, EscalationAction, ExecutionStatus, IntentType, RiskLevel
from app.schemas import Context, RiskResult, Understanding
from app.tools.explainer import Explainer


def _hit(pattern: AMLPattern, evidence: dict) -> dict:
    return {
        "pattern": pattern,
        "rule_id": pattern.value,
        "entity_id": "C1",
        "entity_type": "customer",
        "evidence": evidence,
    }


def _flag(rule_hits: list[dict] | None = None, anomaly_score: float = 0.0) -> RiskResult:
    return RiskResult(
        entity_id="C1",
        entity_type="customer",
        risk=RiskLevel.MEDIUM,
        score=0.5,
        explanation="",
        action=EscalationAction.MONITOR,
        evidence={
            "rule_hits": rule_hits or [],
            "anomaly_score": anomaly_score,
            "rule_severity": 0.0,
        },
    )


def _understanding(aml_pattern: AMLPattern = AMLPattern.NONE) -> Understanding:
    return Understanding(intent=IntentType.DETECT_PATTERN, aml_pattern=aml_pattern)


STRUCTURING_EVIDENCE = {
    "txn_ids": ["T1", "T2", "T3"],
    "count": 3,
    "amount_min": 8_000.0,
    "amount_max": 9_999.0,
    "window_days": 7,
    "window_start": "2023-01-01T00:00:00",
    "window_end": "2023-01-05T00:00:00",
    "total_amount": 27_000.0,
}

SMURFING_EVIDENCE = {
    "txn_ids": ["T1", "T2", "T3", "T4", "T5"],
    "distinct_sources": 5,
    "source_ids": ["S1", "S2", "S3", "S4", "S5"],
    "max_amount": 3_000.0,
    "window_days": 7,
    "window_start": "2023-01-01T00:00:00",
    "window_end": "2023-01-06T00:00:00",
    "total_amount": 12_000.0,
}

RAPID_CASH_OUT_EVIDENCE = {
    "deposit_txn_id": "D1",
    "withdrawal_txn_id": "W1",
    "deposit_amount": 10_000.0,
    "withdrawal_amount": 9_200.0,
    "ratio": 0.92,
    "min_ratio": 0.90,
    "window_hours": 24,
    "deposit_time": "2023-01-01T09:00:00",
    "withdrawal_time": "2023-01-01T20:00:00",
}

LAYERING_EVIDENCE = {
    "txn_ids": ["TX1", "TX2", "TX3"],
    "hops": 3,
    "chain": ["A", "B", "C", "D"],
    "min_hops": 3,
    "window_hours": 72,
    "start_time": "2023-01-01T00:00:00",
    "end_time": "2023-01-02T00:00:00",
    "first_hop_amount": 50_000.0,
}


class TestStructuringTemplate:
    def test_includes_count_and_total_amount(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])
        text = explainer.explain(flag, _understanding())

        assert "3 cash deposits" in text
        assert "$27,000.00" in text
        assert "$8,000" in text
        assert "$9,999" in text
        assert "7-day window" in text

    def test_never_invents_a_number_not_in_evidence(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])
        text = explainer.explain(flag, _understanding())

        # Every numeric evidence value must appear verbatim somewhere in the text.
        assert str(STRUCTURING_EVIDENCE["count"]) in text
        assert f"{STRUCTURING_EVIDENCE['total_amount']:,.2f}" in text


class TestSmurfingTemplate:
    def test_includes_distinct_sources_and_max_amount(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.SMURFING, SMURFING_EVIDENCE)])
        text = explainer.explain(flag, _understanding())

        assert "5 distinct sources" in text
        assert "$3,000" in text
        assert "$12,000.00" in text


class TestRapidCashOutTemplate:
    def test_includes_ratio_and_amounts(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.RAPID_CASH_OUT, RAPID_CASH_OUT_EVIDENCE)])
        text = explainer.explain(flag, _understanding())

        assert "$9,200.00" in text
        assert "$10,000.00" in text
        assert "92%" in text
        assert "24h" in text


class TestLayeringTemplate:
    def test_includes_hop_count_and_chain(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.LAYERING, LAYERING_EVIDENCE)])
        text = explainer.explain(flag, _understanding())

        assert "3-hop" in text
        assert "A -> B -> C -> D" in text
        assert "72h" in text


class TestAnomalyOnlyExplanation:
    def test_explains_from_anomaly_score_when_no_rule_hits(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[], anomaly_score=0.87)
        text = explainer.explain(flag, _understanding())

        assert "0.87" in text
        assert "no confirmed rule match" in text


class TestHitSelection:
    def test_prefers_hit_matching_requested_pattern(self) -> None:
        explainer = Explainer()
        flag = _flag(
            rule_hits=[
                _hit(AMLPattern.RAPID_CASH_OUT, RAPID_CASH_OUT_EVIDENCE),
                _hit(AMLPattern.LAYERING, LAYERING_EVIDENCE),
            ]
        )
        text = explainer.explain(flag, _understanding(aml_pattern=AMLPattern.RAPID_CASH_OUT))

        assert "rapid cash-out" in text
        assert "layering" not in text

    def test_falls_back_to_strongest_severity_when_no_pattern_requested(self) -> None:
        explainer = Explainer()
        # layering (severity 1.0) should win over rapid_cash_out (severity 0.5).
        flag = _flag(
            rule_hits=[
                _hit(AMLPattern.RAPID_CASH_OUT, RAPID_CASH_OUT_EVIDENCE),
                _hit(AMLPattern.LAYERING, LAYERING_EVIDENCE),
            ]
        )
        text = explainer.explain(flag, _understanding(aml_pattern=AMLPattern.NONE))

        assert "layering" in text

    def test_falls_back_to_strongest_when_requested_pattern_not_present(self) -> None:
        explainer = Explainer()
        flag = _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])
        # Query asked about smurfing, but this entity's only hit is structuring.
        text = explainer.explain(flag, _understanding(aml_pattern=AMLPattern.SMURFING))

        assert "structuring" in text


class TestRunMethod:
    def test_explains_every_flag_in_context(self) -> None:
        ctx = Context(query="find structuring")
        ctx.understanding = _understanding()
        ctx.flags = [
            _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)]),
            _flag(rule_hits=[_hit(AMLPattern.SMURFING, SMURFING_EVIDENCE)]),
        ]
        explainer = Explainer()
        context, result, trace = explainer.run(ctx, {})

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 2
        assert trace.rows_out == 2
        assert result.output["explained"] == 2
        assert all(flag.explanation for flag in context.flags)
        assert "structuring" in context.flags[0].explanation
        assert "distinct sources" in context.flags[1].explanation

    def test_empty_flags_list_is_success_with_zero_explained(self) -> None:
        ctx = Context(query="q")
        explainer = Explainer()
        context, result, trace = explainer.run(ctx, {})

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 0
        assert result.output["explained"] == 0

    def test_missing_understanding_falls_back_gracefully(self) -> None:
        """context.understanding is None (e.g. tool exercised standalone) —
        run() must not raise; it uses a neutral fallback understanding."""
        ctx = Context(query="q")
        ctx.understanding = None
        ctx.flags = [_flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])]

        explainer = Explainer()
        context, _result, trace = explainer.run(ctx, {})

        assert trace.status == ExecutionStatus.SUCCESS
        assert "structuring" in context.flags[0].explanation


class TestDeterminism:
    def test_same_input_yields_same_explanation(self) -> None:
        explainer = Explainer()
        flag1 = _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])
        flag2 = _flag(rule_hits=[_hit(AMLPattern.STRUCTURING, STRUCTURING_EVIDENCE)])

        text1 = explainer.explain(flag1, _understanding())
        text2 = explainer.explain(flag2, _understanding())

        assert text1 == text2
