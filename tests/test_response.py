"""Unit tests for :class:`app.response.ResponseFormatter` (Phase 2, Developer B).

Verifies pure assembly (every field copied through untouched, nothing computed)
and that empty results/charts/trace are a valid, non-crashing state (D11).
"""

from __future__ import annotations

from app.enums import (
    EscalationAction,
    ExecutionStatus,
    IntentType,
    RiskLevel,
    ToolName,
)
from app.response import ResponseFormatter
from app.schemas import (
    ChartSpec,
    Context,
    ExecutionPlan,
    ExecutionStep,
    RiskResult,
    TraceEntry,
    Understanding,
)


def _flag() -> RiskResult:
    return RiskResult(
        entity_id="C1",
        entity_type="customer",
        risk=RiskLevel.HIGH,
        score=0.9,
        explanation="Some explanation.",
        action=EscalationAction.REPORT,
        evidence={"rule_severity": 1.0},
    )


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[
            ExecutionStep(tool=ToolName.DATA_LOADER, reason="always runs", confidence=1.0),
            ExecutionStep(
                tool=ToolName.AML_PATTERN_DETECTOR, reason="pattern requested", confidence=1.0
            ),
        ],
        skipped=[ToolName.ANOMALY_DETECTOR],
    )


class TestPureAssembly:
    def test_all_fields_copied_through_unchanged(self) -> None:
        ctx = Context(query="find structuring for customer C1")
        ctx.understanding = Understanding(intent=IntentType.DETECT_PATTERN)
        ctx.flags = [_flag()]
        ctx.charts = [ChartSpec(type="timeline", title="Flagged txns", spec={})]
        ctx.trace = [
            TraceEntry(
                tool=ToolName.DATA_LOADER,
                status=ExecutionStatus.SUCCESS,
                rows_in=100,
                rows_out=98,
                duration_ms=12,
            )
        ]
        plan = _plan()

        response = ResponseFormatter().format(ctx, plan)

        assert response.query == ctx.query
        assert response.understanding == ctx.understanding
        assert response.plan == plan.steps
        assert response.skipped == plan.skipped
        assert response.results == ctx.flags
        assert response.charts == ctx.charts
        assert response.trace == ctx.trace

    def test_does_not_mutate_context_or_plan(self) -> None:
        ctx = Context(query="q")
        ctx.flags = [_flag()]
        plan = _plan()
        flags_before = list(ctx.flags)
        steps_before = list(plan.steps)

        ResponseFormatter().format(ctx, plan)

        assert ctx.flags == flags_before
        assert plan.steps == steps_before

    def test_internal_dataframes_never_leak_into_response(self) -> None:
        """raw_df/working_df/features are internal-only; APIResponse's fixed
        field set structurally excludes them — this just documents that intent."""
        import pandas as pd

        ctx = Context(query="q")
        ctx.raw_df = pd.DataFrame({"a": [1, 2]})
        ctx.working_df = pd.DataFrame({"a": [1]})
        plan = _plan()

        response = ResponseFormatter().format(ctx, plan)

        assert not hasattr(response, "raw_df")
        assert not hasattr(response, "working_df")


class TestEmptyState:
    def test_empty_results_charts_trace_do_not_raise(self) -> None:
        ctx = Context(query="transactions in the last 30 days")
        ctx.understanding = Understanding(intent=IntentType.EDA)
        plan = ExecutionPlan(
            steps=[ExecutionStep(tool=ToolName.FILTER, reason="date filter", confidence=1.0)],
            skipped=[ToolName.AML_PATTERN_DETECTOR],
        )

        response = ResponseFormatter().format(ctx, plan)

        assert response.results == []
        assert response.charts == []
        assert response.trace == []
        assert response.skipped == [ToolName.AML_PATTERN_DETECTOR]

    def test_empty_state_still_carries_the_why_via_trace_and_understanding(self) -> None:
        """D11: the 'why' for an empty result set is reconstructable from trace
        rows_in/rows_out + understanding.filters — this formatter must pass both
        through intact rather than dropping them because results are empty."""
        ctx = Context(query="transactions in the last 30 days")
        ctx.understanding = Understanding(
            intent=IntentType.EDA,
            filters={"date_range": {"last_days": 30}},
        )
        ctx.trace = [
            TraceEntry(
                tool=ToolName.FILTER,
                status=ExecutionStatus.SUCCESS,
                rows_in=1000,
                rows_out=0,
                duration_ms=5,
            )
        ]
        plan = ExecutionPlan(steps=[], skipped=[])

        response = ResponseFormatter().format(ctx, plan)

        assert response.trace[0].rows_in == 1000
        assert response.trace[0].rows_out == 0
        assert response.understanding.filters.date_range.last_days == 30

    def test_understanding_none_does_not_raise(self) -> None:
        ctx = Context(query="q")
        ctx.understanding = None
        plan = _plan()

        response = ResponseFormatter().format(ctx, plan)
        assert response.understanding is None


class TestDeterminism:
    def test_same_input_yields_equal_response(self) -> None:
        ctx1 = Context(query="q")
        ctx1.flags = [_flag()]
        ctx2 = Context(query="q")
        ctx2.flags = [_flag()]
        plan = _plan()

        r1 = ResponseFormatter().format(ctx1, plan)
        r2 = ResponseFormatter().format(ctx2, plan)

        assert r1 == r2
