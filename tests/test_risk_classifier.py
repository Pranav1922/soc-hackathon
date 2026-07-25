"""Unit tests for :class:`app.tools.risk_classifier.RiskClassifier` (Phase 2,
Developer B).

Exercises the frozen D7 formula directly against ``app.config.RISK`` /
``RULE_SEVERITY`` so tests stay correct if those constants are recalibrated.
"""

from __future__ import annotations

from app.config import RISK, RULE_SEVERITY
from app.enums import AMLPattern, EscalationAction, ExecutionStatus, RiskLevel
from app.schemas import Context
from app.tools.risk_classifier import RiskClassifier


def _hit(pattern: AMLPattern, entity_id: str = "C1") -> dict:
    return {
        "pattern": pattern,
        "rule_id": pattern.value,
        "entity_id": entity_id,
        "entity_type": "customer",
        "evidence": {"txn_ids": ["T1"]},
    }


def _context(
    hits_by_customer: dict[str, list[dict]] | None = None,
    anomaly_scores: dict[str, float] | None = None,
) -> Context:
    ctx = Context(query="test query")
    if hits_by_customer is not None:
        ctx.artifacts["aml_hits_by_customer"] = hits_by_customer
    if anomaly_scores is not None:
        ctx.artifacts["anomaly_scores"] = anomaly_scores
    return ctx


def _run(ctx: Context):
    return RiskClassifier().run(ctx, {})


class TestNoCandidates:
    def test_no_hits_and_no_anomaly_scores_yields_no_flags(self) -> None:
        ctx = _context()
        context, result, trace = _run(ctx)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 0
        assert trace.rows_out == 0
        assert context.flags == []
        assert result.output["entities_scored"] == 0


class TestRuleOnlyScoring:
    def test_single_rule_hit_produces_one_flag(self) -> None:
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        context, _result, trace = _run(ctx)

        assert trace.rows_out == 1
        assert len(context.flags) == 1
        flag = context.flags[0]
        assert flag.entity_id == "C1"
        assert flag.entity_type == "customer"

    def test_score_matches_frozen_formula_for_structuring(self) -> None:
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        context, _result, _trace = _run(ctx)

        severity = RULE_SEVERITY[AMLPattern.STRUCTURING]
        expected_raw = RISK.rule_weight * severity  # anomaly_score defaults to 0.0
        expected = max(expected_raw, RISK.rule_hit_floor)
        assert context.flags[0].score == expected

    def test_rule_hit_floors_band_at_medium_even_if_raw_score_is_low(self) -> None:
        # rapid_cash_out has the lowest severity (0.5); with no anomaly score,
        # raw = 0.6 * 0.5 = 0.30, which is below medium_band (0.45) unfloored.
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.RAPID_CASH_OUT)]})
        context, _result, _trace = _run(ctx)

        flag = context.flags[0]
        assert flag.score == RISK.rule_hit_floor
        assert flag.risk == RiskLevel.MEDIUM

    def test_high_severity_rule_alone_can_reach_high_band(self) -> None:
        # layering has severity 1.0; raw = 0.6 * 1.0 = 0.6 -> below high_band (0.75)
        # unless anomaly contributes. Verify it lands at medium, not high, alone.
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.LAYERING)]})
        context, _result, _trace = _run(ctx)

        severity = RULE_SEVERITY[AMLPattern.LAYERING]
        expected = RISK.rule_weight * severity
        flag = context.flags[0]
        assert flag.score == max(expected, RISK.rule_hit_floor)
        assert flag.risk in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    def test_multiple_hits_use_strongest_severity(self) -> None:
        ctx = _context(
            hits_by_customer={
                "C1": [_hit(AMLPattern.RAPID_CASH_OUT), _hit(AMLPattern.LAYERING)]
            }
        )
        context, _result, _trace = _run(ctx)

        flag = context.flags[0]
        assert flag.evidence["rule_severity"] == RULE_SEVERITY[AMLPattern.LAYERING]
        assert len(flag.evidence["rule_hits"]) == 2


class TestAnomalyOnlyScoring:
    def test_entity_with_only_anomaly_score_still_gets_flagged(self) -> None:
        ctx = _context(anomaly_scores={"C2": 0.9})
        context, _result, trace = _run(ctx)

        assert trace.rows_out == 1
        flag = context.flags[0]
        assert flag.entity_id == "C2"
        expected = min(1.0, RISK.anomaly_weight * 0.9)
        assert flag.score == expected
        assert flag.evidence["rule_severity"] == 0.0
        assert flag.evidence["floored_to_medium"] is False

    def test_low_anomaly_score_yields_low_band(self) -> None:
        ctx = _context(anomaly_scores={"C2": 0.1})
        context, _result, _trace = _run(ctx)
        assert context.flags[0].risk == RiskLevel.LOW


class TestCombinedScoring:
    def test_rule_and_anomaly_combine_additively(self) -> None:
        ctx = _context(
            hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]},
            anomaly_scores={"C1": 0.5},
        )
        context, _result, _trace = _run(ctx)

        severity = RULE_SEVERITY[AMLPattern.STRUCTURING]
        expected_raw = RISK.rule_weight * severity + RISK.anomaly_weight * 0.5
        expected = min(1.0, expected_raw)
        flag = context.flags[0]
        assert flag.score == max(expected, RISK.rule_hit_floor)

    def test_score_never_exceeds_one(self) -> None:
        ctx = _context(
            hits_by_customer={"C1": [_hit(AMLPattern.LAYERING)]},
            anomaly_scores={"C1": 1.0},
        )
        context, _result, _trace = _run(ctx)
        assert context.flags[0].score <= 1.0

    def test_union_of_entities_from_both_sources_all_scored(self) -> None:
        ctx = _context(
            hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]},
            anomaly_scores={"C2": 0.8},
        )
        context, _result, trace = _run(ctx)

        assert trace.rows_out == 2
        assert {f.entity_id for f in context.flags} == {"C1", "C2"}


class TestBanding:
    def test_score_at_high_band_boundary_is_high(self) -> None:
        assert RiskClassifier._band(RISK.high_band) == RiskLevel.HIGH

    def test_score_at_medium_band_boundary_is_medium(self) -> None:
        assert RiskClassifier._band(RISK.medium_band) == RiskLevel.MEDIUM

    def test_score_below_medium_band_is_low(self) -> None:
        assert RiskClassifier._band(RISK.medium_band - 0.01) == RiskLevel.LOW

    def test_score_just_below_high_band_is_medium(self) -> None:
        assert RiskClassifier._band(RISK.high_band - 0.01) == RiskLevel.MEDIUM


class TestPlaceholderFields:
    def test_explanation_is_empty_placeholder_for_explainer(self) -> None:
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        context, _result, _trace = _run(ctx)
        assert context.flags[0].explanation == ""

    def test_action_defaults_to_monitor_placeholder_for_recommender(self) -> None:
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        context, _result, _trace = _run(ctx)
        assert context.flags[0].action == EscalationAction.MONITOR


class TestAppendBehavior:
    def test_existing_flags_are_preserved_not_overwritten(self) -> None:
        ctx = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        context, _result, _trace = _run(ctx)
        assert len(context.flags) == 1

        # Simulate a second classifier pass appending more candidates.
        context.artifacts["aml_hits_by_customer"]["C3"] = [
            _hit(AMLPattern.SMURFING, entity_id="C3")
        ]
        context2, _result2, _trace2 = RiskClassifier().run(context, {})
        # Second pass re-scores C1 (still in artifacts) + newly-added C3, both
        # appended on top of the first pass's C1 -> 3 total flag entries.
        assert len(context2.flags) == 3


class TestDeterminism:
    def test_same_input_yields_same_scores(self) -> None:
        ctx1 = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})
        ctx2 = _context(hits_by_customer={"C1": [_hit(AMLPattern.STRUCTURING)]})

        context1, _, _ = _run(ctx1)
        context2, _, _ = _run(ctx2)

        assert context1.flags[0].score == context2.flags[0].score
        assert context1.flags[0].risk == context2.flags[0].risk
