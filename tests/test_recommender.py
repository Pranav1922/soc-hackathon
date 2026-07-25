"""Unit tests for :class:`app.tools.recommender.Recommender` (Phase 2, Developer B).

Verifies the frozen band -> action mapping and that the justification is
evidence-tied (names the actual triggering rule/severity, not just the band).
"""

from __future__ import annotations

from app.config import RULE_SEVERITY
from app.enums import AMLPattern, EscalationAction, ExecutionStatus, RiskLevel
from app.schemas import Context, RiskResult
from app.tools.recommender import Recommender


def _hit(pattern: AMLPattern) -> dict:
    return {
        "pattern": pattern,
        "rule_id": pattern.value,
        "entity_id": "C1",
        "entity_type": "customer",
        "evidence": {},
    }


def _flag(
    risk: RiskLevel,
    rule_hits: list[dict] | None = None,
    anomaly_score: float = 0.0,
) -> RiskResult:
    return RiskResult(
        entity_id="C1",
        entity_type="customer",
        risk=risk,
        score=0.5,
        explanation="Some explanation already set by Explainer.",
        action=EscalationAction.MONITOR,  # RiskClassifier's placeholder
        evidence={"rule_hits": rule_hits or [], "anomaly_score": anomaly_score},
    )


class TestBandMapping:
    def test_low_maps_to_monitor(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.LOW)]
        context, _result, trace = Recommender().run(ctx, {})

        assert context.flags[0].action == EscalationAction.MONITOR
        assert trace.status == ExecutionStatus.SUCCESS

    def test_medium_maps_to_review(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.MEDIUM, rule_hits=[_hit(AMLPattern.STRUCTURING)])]
        context, _result, _trace = Recommender().run(ctx, {})

        assert context.flags[0].action == EscalationAction.REVIEW

    def test_high_maps_to_report(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.HIGH, rule_hits=[_hit(AMLPattern.LAYERING)])]
        context, _result, _trace = Recommender().run(ctx, {})

        assert context.flags[0].action == EscalationAction.REPORT


class TestJustification:
    def test_justification_names_the_triggering_rule_not_just_band(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.HIGH, rule_hits=[_hit(AMLPattern.LAYERING)])]
        context, _result, _trace = Recommender().run(ctx, {})

        reason = context.flags[0].evidence["escalation_reason"]
        assert "layering" in reason
        severity = RULE_SEVERITY[AMLPattern.LAYERING]
        assert f"{severity:.1f}" in reason
        assert "Suspicious Activity Report" in reason

    def test_justification_uses_strongest_hit_when_multiple(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [
            _flag(
                RiskLevel.HIGH,
                rule_hits=[_hit(AMLPattern.RAPID_CASH_OUT), _hit(AMLPattern.LAYERING)],
            )
        ]
        context, _result, _trace = Recommender().run(ctx, {})

        reason = context.flags[0].evidence["escalation_reason"]
        assert "layering" in reason
        assert "rapid cash out" not in reason

    def test_justification_falls_back_to_anomaly_score_when_no_rule_hit(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.MEDIUM, rule_hits=[], anomaly_score=0.6)]
        context, _result, _trace = Recommender().run(ctx, {})

        reason = context.flags[0].evidence["escalation_reason"]
        assert "0.60" in reason
        assert "no confirmed rule match" in reason

    def test_does_not_overwrite_explanation_set_by_explainer(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag(RiskLevel.LOW)]
        context, _result, _trace = Recommender().run(ctx, {})

        assert context.flags[0].explanation == "Some explanation already set by Explainer."


class TestRunMethod:
    def test_recommends_for_every_flag(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [
            _flag(RiskLevel.LOW),
            _flag(RiskLevel.MEDIUM, rule_hits=[_hit(AMLPattern.SMURFING)]),
            _flag(RiskLevel.HIGH, rule_hits=[_hit(AMLPattern.LAYERING)]),
        ]
        context, result, trace = Recommender().run(ctx, {})

        assert trace.rows_in == 3
        assert trace.rows_out == 3
        assert result.output["recommended"] == 3
        assert result.output["action_counts"] == {
            "monitor": 1,
            "review": 1,
            "report": 1,
        }

    def test_empty_flags_list_is_success(self) -> None:
        ctx = Context(query="q")
        context, result, trace = Recommender().run(ctx, {})

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 0
        assert result.output["recommended"] == 0


class TestDeterminism:
    def test_same_input_yields_same_action_and_reason(self) -> None:
        ctx1 = Context(query="q")
        ctx1.flags = [_flag(RiskLevel.HIGH, rule_hits=[_hit(AMLPattern.LAYERING)])]
        ctx2 = Context(query="q")
        ctx2.flags = [_flag(RiskLevel.HIGH, rule_hits=[_hit(AMLPattern.LAYERING)])]

        context1, _, _ = Recommender().run(ctx1, {})
        context2, _, _ = Recommender().run(ctx2, {})

        assert context1.flags[0].action == context2.flags[0].action
        assert (
            context1.flags[0].evidence["escalation_reason"]
            == context2.flags[0].evidence["escalation_reason"]
        )
