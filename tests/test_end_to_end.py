"""Response-contract structural tests (D18): the frozen APIResponse shape, the
ExecutionStep/TraceEntry split, and the runnable-tool registry. A full
query→APIResponse integration test is a recommended post-merge follow-up."""

from __future__ import annotations

from app.agent.tool_set import TOOLS
from app.enums import (
    AMLPattern,
    EscalationAction,
    ExecutionStatus,
    IntentType,
    RiskLevel,
    ToolName,
)
from app.response import ResponseFormatter
from app.schemas import (
    APIResponse,
    ExecutionStep,
    RiskResult,
    TraceEntry,
    Understanding,
)

EXPECTED_RESPONSE_KEYS = {
    "query",
    "understanding",
    "plan",
    "skipped",
    "results",
    "charts",
    "trace",
}


def test_response_contract_shape_is_frozen() -> None:
    """APIResponse must expose exactly the D12 fields — no more, no less."""
    resp = APIResponse(
        query="Find structuring patterns in the last 30 days",
        understanding=Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.STRUCTURING,
            confidence=0.98,
        ),
        plan=[ExecutionStep(tool=ToolName.FILTER, reason="last 30 days", confidence=0.98)],
        skipped=[ToolName.EDA, ToolName.ANOMALY_DETECTOR],
        results=[
            RiskResult(
                entity_id="C4521",
                risk=RiskLevel.HIGH,
                score=0.91,
                explanation="6 sub-$10k deposits in 4 days (structuring).",
                action=EscalationAction.REPORT,
            )
        ],
        trace=[
            TraceEntry(
                tool=ToolName.FILTER,
                status=ExecutionStatus.SUCCESS,
                rows_in=100_000,
                rows_out=8_421,
                duration_ms=12,
            )
        ],
    )
    assert set(resp.model_dump().keys()) == EXPECTED_RESPONSE_KEYS


def test_execution_step_and_trace_entry_are_separate_models() -> None:
    """ExecutionStep (planned) and TraceEntry (actual) must not share fields (D12)."""
    step_fields = set(ExecutionStep.model_fields)
    trace_fields = set(TraceEntry.model_fields)
    assert step_fields == {"tool", "reason", "confidence", "inputs"}
    assert trace_fields == {"tool", "status", "rows_in", "rows_out", "duration_ms"}
    # Only the shared identity field 'tool' overlaps.
    assert step_fields & trace_fields == {"tool"}


def test_runnable_registry_excludes_response_formatter() -> None:
    """The 10 planner-selectable tools are runnable; ResponseFormatter is post-exec."""
    assert len(TOOLS) == 10
    assert ToolName.RESPONSE_FORMATTER not in TOOLS
    assert ResponseFormatter().name == ToolName.RESPONSE_FORMATTER
