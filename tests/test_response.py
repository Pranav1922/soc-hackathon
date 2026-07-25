"""Unit tests for :class:`app.response.ResponseFormatter` (D12).

The formatter is a pure field-mapper: Context + ExecutionPlan -> APIResponse, with
no computation and no mutation. Tests cover full mapping, the empty-results path,
``understanding=None``, per-field propagation, determinism, no-mutation, and the
architectural guarantee that it is not a runnable Tool.
"""

from __future__ import annotations

import copy

from app.agent.tool_set import TOOLS
from app.enums import (
    AMLPattern,
    EscalationAction,
    ExecutionStatus,
    IntentType,
    RiskLevel,
    ToolName,
)
from app.interfaces import Tool
from app.response import ResponseFormatter
from app.schemas import (
    APIResponse,
    ChartSpec,
    Context,
    ExecutionPlan,
    ExecutionStep,
    RiskResult,
    TraceEntry,
    Understanding,
)


def _understanding() -> Understanding:
    return Understanding(
        intent=IntentType.DETECT_PATTERN,
        aml_pattern=AMLPattern.STRUCTURING,
        confidence=0.9,
    )


def _risk_result(entity_id: str = "C1") -> RiskResult:
    return RiskResult(
        entity_id=entity_id,
        risk=RiskLevel.HIGH,
        score=0.91,
        explanation="6 sub-$10k deposits in 4 days.",
        action=EscalationAction.REPORT,
        evidence={"rule": "structuring"},
    )


def _context(*, understanding: Understanding | None = None, with_data: bool = True) -> Context:
    ctx = Context(query="Find structuring in the last 30 days", understanding=understanding)
    if with_data:
        ctx.flags = [_risk_result("C1"), _risk_result("C2")]
        ctx.charts = [ChartSpec(type="timeline", title="Flagged", spec={"x": [1, 2]})]
        ctx.trace = [
            TraceEntry(
                tool=ToolName.FILTER,
                status=ExecutionStatus.SUCCESS,
                rows_in=100,
                rows_out=40,
                duration_ms=5,
            )
        ]
    return ctx


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[
            ExecutionStep(tool=ToolName.DATA_LOADER, reason="load", confidence=1.0),
            ExecutionStep(tool=ToolName.FILTER, reason="last 30 days", confidence=0.9),
        ],
        skipped=[ToolName.EDA, ToolName.ANOMALY_DETECTOR],
    )


# ── full mapping ─────────────────────────────────────────────────────────────


def test_full_populated_response_maps_every_field() -> None:
    ctx = _context(understanding=_understanding())
    plan = _plan()
    response = ResponseFormatter().format(ctx, plan)

    assert isinstance(response, APIResponse)
    assert response.query == ctx.query
    assert response.understanding == ctx.understanding
    assert [s.tool for s in response.plan] == [s.tool for s in plan.steps]
    assert response.skipped == plan.skipped
    assert [r.entity_id for r in response.results] == ["C1", "C2"]
    assert response.charts == ctx.charts
    assert response.trace == ctx.trace


def test_response_has_exactly_the_seven_frozen_fields() -> None:
    response = ResponseFormatter().format(_context(), _plan())
    assert set(response.model_dump()) == {
        "query",
        "understanding",
        "plan",
        "skipped",
        "results",
        "charts",
        "trace",
    }


# ── edge cases ───────────────────────────────────────────────────────────────


def test_empty_results_is_a_valid_response() -> None:
    ctx = _context(understanding=_understanding(), with_data=False)  # no flags/charts
    response = ResponseFormatter().format(ctx, _plan())
    assert response.results == []
    assert response.charts == []
    # The plan is still reported even with no results.
    assert len(response.plan) == 2


def test_understanding_none_passes_through() -> None:
    ctx = _context(understanding=None)
    response = ResponseFormatter().format(ctx, _plan())
    assert response.understanding is None


# ── per-field propagation ────────────────────────────────────────────────────


def test_skipped_propagation() -> None:
    plan = ExecutionPlan(steps=[], skipped=[ToolName.EDA, ToolName.VISUALIZER])
    response = ResponseFormatter().format(_context(with_data=False), plan)
    assert response.skipped == [ToolName.EDA, ToolName.VISUALIZER]


def test_charts_propagation() -> None:
    ctx = _context(with_data=False)
    ctx.charts = [ChartSpec(type="histogram", title="Amounts", spec={})]
    response = ResponseFormatter().format(ctx, _plan())
    assert len(response.charts) == 1
    assert response.charts[0].type == "histogram"


def test_trace_propagation() -> None:
    ctx = _context(with_data=False)
    ctx.trace = [
        TraceEntry(tool=ToolName.DATA_LOADER, status=ExecutionStatus.SUCCESS, rows_in=0, rows_out=100, duration_ms=3),
        TraceEntry(tool=ToolName.FILTER, status=ExecutionStatus.SKIPPED, rows_in=100, rows_out=100, duration_ms=0),
    ]
    response = ResponseFormatter().format(ctx, _plan())
    assert [t.tool for t in response.trace] == [ToolName.DATA_LOADER, ToolName.FILTER]
    assert response.trace[1].status is ExecutionStatus.SKIPPED


# ── determinism & purity ─────────────────────────────────────────────────────


def test_deterministic_output() -> None:
    ctx = _context(understanding=_understanding())
    plan = _plan()
    first = ResponseFormatter().format(ctx, plan)
    second = ResponseFormatter().format(ctx, plan)
    assert first.model_dump() == second.model_dump()


def test_pure_assembly_does_not_mutate_inputs() -> None:
    ctx = _context(understanding=_understanding())
    plan = _plan()
    ctx_before = copy.deepcopy(ctx.model_dump())
    plan_before = copy.deepcopy(plan.model_dump())

    ResponseFormatter().format(ctx, plan)

    assert ctx.model_dump() == ctx_before
    assert plan.model_dump() == plan_before
    # Identity of the underlying containers is untouched (nothing reassigned).
    assert isinstance(ctx.flags, list)
    assert len(ctx.flags) == 2


# ── architectural guarantees ─────────────────────────────────────────────────


def test_is_not_a_tool_and_not_in_registry() -> None:
    assert not issubclass(ResponseFormatter, Tool)
    assert not hasattr(ResponseFormatter, "run")
    assert ToolName.RESPONSE_FORMATTER not in TOOLS
    assert ResponseFormatter().name is ToolName.RESPONSE_FORMATTER
