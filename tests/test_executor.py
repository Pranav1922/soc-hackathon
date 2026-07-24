"""Tests for the Executor (Dev A - Phase 3).

Every tool is mocked — no real Tool implementation runs. Covers successful
execution, multi-step ordering, failure isolation, the non-propagation policy,
TraceEntry generation, dependency injection, determinism, and result correctness.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest

from app.agent.executor import Executor
from app.agent.tool_set import TOOLS
from app.enums import EscalationAction, ExecutionStatus, RiskLevel, ToolName
from app.interfaces import Tool
from app.schemas import (
    Context,
    ExecutionPlan,
    ExecutionStep,
    RiskResult,
    ToolResult,
    TraceEntry,
)

# ── mock tools (all subclass the frozen Tool abstraction) ────────────────────


class RecordingTool(Tool):
    """A tool that records that it ran and returns a canned result + trace."""

    def __init__(
        self,
        name: ToolName,
        calls: list[ToolName],
        *,
        rows_in: int = 7,
        rows_out: int = 5,
        status: ExecutionStatus = ExecutionStatus.SUCCESS,
        mutate: Callable[[Context, dict], None] | None = None,
    ) -> None:
        self._name = name
        self._calls = calls
        self._rows_in = rows_in
        self._rows_out = rows_out
        self._status = status
        self._mutate = mutate

    @property
    def name(self) -> ToolName:
        return self._name

    def run(self, context: Context, params: dict) -> tuple[Context, ToolResult, TraceEntry]:
        self._calls.append(self._name)
        if self._mutate is not None:
            self._mutate(context, params)
        result = ToolResult(tool=self._name, output={"params": params})
        # duration_ms=999 lets tests confirm the executor overrides it with its own.
        trace = TraceEntry(
            tool=self._name,
            status=self._status,
            rows_in=self._rows_in,
            rows_out=self._rows_out,
            duration_ms=999,
        )
        return context, result, trace


class FailingTool(Tool):
    """A tool that raises when run."""

    def __init__(self, name: ToolName, calls: list[ToolName], exc: Exception) -> None:
        self._name = name
        self._calls = calls
        self._exc = exc

    @property
    def name(self) -> ToolName:
        return self._name

    def run(self, context: Context, params: dict) -> tuple[Context, ToolResult, TraceEntry]:
        self._calls.append(self._name)
        raise self._exc


# ── helpers ──────────────────────────────────────────────────────────────────


def _plan(*tools: ToolName) -> ExecutionPlan:
    return ExecutionPlan(
        steps=[ExecutionStep(tool=t, reason="test", confidence=1.0, inputs={}) for t in tools]
    )


def _ctx() -> Context:
    return Context(query="test query")


# ── successful execution ─────────────────────────────────────────────────────


def test_successful_single_step() -> None:
    calls: list[ToolName] = []
    registry = {ToolName.DATA_LOADER: RecordingTool(ToolName.DATA_LOADER, calls)}
    result = Executor(tools=registry).run_plan(_ctx(), _plan(ToolName.DATA_LOADER))

    assert calls == [ToolName.DATA_LOADER]
    assert len(result.trace) == 1
    assert result.trace[0].tool is ToolName.DATA_LOADER
    assert result.trace[0].status is ExecutionStatus.SUCCESS


def test_multiple_steps_execute_in_plan_order() -> None:
    calls: list[ToolName] = []
    order = [ToolName.DATA_LOADER, ToolName.FILTER, ToolName.FEATURE_ENGINEERING]
    registry = {t: RecordingTool(t, calls) for t in order}
    result = Executor(tools=registry).run_plan(_ctx(), _plan(*order))

    assert calls == order  # invoked in exactly the planned order
    assert [e.tool for e in result.trace] == order


def test_tool_result_payloads_are_collected() -> None:
    calls: list[ToolName] = []
    registry = {ToolName.FILTER: RecordingTool(ToolName.FILTER, calls)}
    result = Executor(tools=registry).run_plan(
        _ctx(), ExecutionPlan(steps=[ExecutionStep(tool=ToolName.FILTER, reason="r", inputs={"k": 1})])
    )
    collected = result.artifacts["tool_results"]
    assert len(collected) == 1
    assert isinstance(collected[0], ToolResult)
    assert collected[0].output == {"params": {"k": 1}}


# ── TraceEntry generation ────────────────────────────────────────────────────


def test_trace_entry_matches_frozen_schema_and_preserves_rows() -> None:
    calls: list[ToolName] = []
    registry = {ToolName.FILTER: RecordingTool(ToolName.FILTER, calls, rows_in=100, rows_out=42)}
    result = Executor(tools=registry).run_plan(_ctx(), _plan(ToolName.FILTER))
    entry = result.trace[0]
    assert set(entry.model_dump()) == {"tool", "status", "rows_in", "rows_out", "duration_ms"}
    assert entry.rows_in == 100
    assert entry.rows_out == 42


def test_executor_stamps_its_own_duration() -> None:
    calls: list[ToolName] = []
    # Tool reports duration_ms=999; the executor must override with measured time.
    registry = {ToolName.EDA: RecordingTool(ToolName.EDA, calls)}
    result = Executor(tools=registry).run_plan(_ctx(), _plan(ToolName.EDA))
    assert result.trace[0].duration_ms != 999
    assert result.trace[0].duration_ms >= 0


# ── failure isolation & non-propagation ──────────────────────────────────────


def test_tool_failure_records_error_and_does_not_raise() -> None:
    calls: list[ToolName] = []
    registry = {ToolName.AML_PATTERN_DETECTOR: FailingTool(
        ToolName.AML_PATTERN_DETECTOR, calls, ValueError("boom")
    )}
    # Must not raise.
    result = Executor(tools=registry).run_plan(_ctx(), _plan(ToolName.AML_PATTERN_DETECTOR))
    assert len(result.trace) == 1
    assert result.trace[0].status is ExecutionStatus.ERROR
    assert result.trace[0].tool is ToolName.AML_PATTERN_DETECTOR


def test_failure_isolation_continues_subsequent_steps() -> None:
    calls: list[ToolName] = []
    registry = {
        ToolName.DATA_LOADER: RecordingTool(ToolName.DATA_LOADER, calls),
        ToolName.FILTER: FailingTool(ToolName.FILTER, calls, RuntimeError("x")),
        ToolName.RISK_CLASSIFIER: RecordingTool(ToolName.RISK_CLASSIFIER, calls),
    }
    plan = _plan(ToolName.DATA_LOADER, ToolName.FILTER, ToolName.RISK_CLASSIFIER)
    result = Executor(tools=registry).run_plan(_ctx(), plan)

    # All three were attempted; the middle one failed but did not stop the run.
    assert calls == [ToolName.DATA_LOADER, ToolName.FILTER, ToolName.RISK_CLASSIFIER]
    statuses = [(e.tool, e.status) for e in result.trace]
    assert statuses == [
        (ToolName.DATA_LOADER, ExecutionStatus.SUCCESS),
        (ToolName.FILTER, ExecutionStatus.ERROR),
        (ToolName.RISK_CLASSIFIER, ExecutionStatus.SUCCESS),
    ]


def test_error_trace_captures_input_rows() -> None:
    calls: list[ToolName] = []
    ctx = Context(query="q", working_df=pd.DataFrame({"a": [1, 2, 3]}))
    registry = {ToolName.FILTER: FailingTool(ToolName.FILTER, calls, ValueError())}
    result = Executor(tools=registry).run_plan(ctx, _plan(ToolName.FILTER))
    assert result.trace[0].rows_in == 3
    assert result.trace[0].rows_out == 0


def test_unregistered_tool_records_error_and_continues() -> None:
    calls: list[ToolName] = []
    # Registry is missing FILTER; plan references it.
    registry = {ToolName.DATA_LOADER: RecordingTool(ToolName.DATA_LOADER, calls)}
    plan = _plan(ToolName.DATA_LOADER, ToolName.FILTER)
    result = Executor(tools=registry).run_plan(_ctx(), plan)
    assert [(e.tool, e.status) for e in result.trace] == [
        (ToolName.DATA_LOADER, ExecutionStatus.SUCCESS),
        (ToolName.FILTER, ExecutionStatus.ERROR),
    ]


# ── dependency injection ─────────────────────────────────────────────────────


def test_default_registry_is_the_project_tool_set() -> None:
    assert Executor()._tools is TOOLS


def test_injected_registry_is_used_not_the_real_tools() -> None:
    calls: list[ToolName] = []
    registry = {ToolName.DATA_LOADER: RecordingTool(ToolName.DATA_LOADER, calls)}
    ex = Executor(tools=registry)
    assert ex._tools is registry
    ex.run_plan(_ctx(), _plan(ToolName.DATA_LOADER))
    assert calls == [ToolName.DATA_LOADER]  # the mock ran, not the real DataLoader


# ── result correctness & determinism ─────────────────────────────────────────


def test_context_is_threaded_and_enriched() -> None:
    calls: list[ToolName] = []

    def add_flag(context: Context, _params: dict) -> None:
        context.flags.append(
            RiskResult(
                entity_id="C1",
                risk=RiskLevel.HIGH,
                score=0.9,
                explanation="e",
                action=EscalationAction.REPORT,
            )
        )

    registry = {ToolName.RISK_CLASSIFIER: RecordingTool(ToolName.RISK_CLASSIFIER, calls, mutate=add_flag)}
    ctx = _ctx()
    result = Executor(tools=registry).run_plan(ctx, _plan(ToolName.RISK_CLASSIFIER))
    assert result is ctx  # same context object, enriched in place
    assert len(result.flags) == 1
    assert result.flags[0].entity_id == "C1"


def test_empty_plan_produces_empty_trace() -> None:
    result = Executor(tools={}).run_plan(_ctx(), ExecutionPlan(steps=[]))
    assert result.trace == []


def test_execution_is_deterministic() -> None:
    order = [ToolName.DATA_LOADER, ToolName.FILTER, ToolName.RISK_CLASSIFIER]

    def run_once() -> list[tuple[ToolName, ExecutionStatus]]:
        calls: list[ToolName] = []
        registry = {t: RecordingTool(t, calls) for t in order}
        result = Executor(tools=registry).run_plan(_ctx(), _plan(*order))
        return [(e.tool, e.status) for e in result.trace]

    assert run_once() == run_once()


@pytest.mark.parametrize("exc", [ValueError("v"), KeyError("k"), RuntimeError("r")])
def test_various_tool_exceptions_are_isolated(exc: Exception) -> None:
    calls: list[ToolName] = []
    registry = {ToolName.EDA: FailingTool(ToolName.EDA, calls, exc)}
    result = Executor(tools=registry).run_plan(_ctx(), _plan(ToolName.EDA))
    assert result.trace[0].status is ExecutionStatus.ERROR
