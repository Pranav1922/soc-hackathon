"""Integration tests for :class:`app.agent.pipeline.Pipeline`.

Verify the orchestrator only coordinates the completed modules: correct execution
order, a valid APIResponse, graceful behaviour with a missing dataset, isolation of a
failing tool, and deterministic output. No production module is modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agent.executor import Executor
from app.agent.pipeline import Pipeline
from app.agent.planner import DeterministicPlanner
from app.enums import AMLPattern, ExecutionStatus, IntentType, ToolName
from app.interfaces import Planner, QueryUnderstanding, Tool
from app.response import ResponseFormatter
from app.schemas import (
    APIResponse,
    Context,
    ExecutionPlan,
    ExecutionStep,
    ToolResult,
    TraceEntry,
    Understanding,
)

QUERY = "Find structuring patterns in the last 30 days"


# ── spies for the execution-order / delegation test ──────────────────────────


class SpyUnderstanding(QueryUnderstanding):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def understand(self, query: str, schema_map: dict[str, str]) -> Understanding:
        self.calls.append("understand")
        return Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.STRUCTURING,
            confidence=0.5,
        )


class SpyPlanner(Planner):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def build_plan(self, understanding: Understanding) -> ExecutionPlan:
        self.calls.append("build_plan")
        return ExecutionPlan(
            steps=[ExecutionStep(tool=ToolName.DATA_LOADER, reason="r", confidence=1.0)],
            skipped=[],
        )


class SpyExecutor(Executor):
    def __init__(self, calls: list[str]) -> None:
        super().__init__(tools={})
        self.calls = calls

    def run_plan(self, context: Context, plan: ExecutionPlan) -> Context:
        self.calls.append("run_plan")
        return context


class SpyFormatter(ResponseFormatter):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def format(self, context: Context, plan: ExecutionPlan) -> APIResponse:
        self.calls.append("format")
        return APIResponse(query=context.query)


def _normalize(response: APIResponse) -> dict[str, Any]:
    """Response as a dict with non-deterministic trace timing stripped."""
    data = response.model_dump()
    for entry in data["trace"]:
        entry.pop("duration_ms", None)
    return data


# ── execution order / delegation ─────────────────────────────────────────────


def test_analyze_delegates_in_the_correct_order() -> None:
    calls: list[str] = []
    pipeline = Pipeline(
        understanding=SpyUnderstanding(calls),
        planner=SpyPlanner(calls),
        executor=SpyExecutor(calls),
        formatter=SpyFormatter(calls),
    )
    response = pipeline.analyze(QUERY)
    assert calls == ["understand", "build_plan", "run_plan", "format"]
    assert isinstance(response, APIResponse)
    assert response.query == QUERY


# ── real components: returns a valid response, no raise ──────────────────────


def test_analyze_returns_apiresponse_end_to_end() -> None:
    response = Pipeline().analyze(QUERY)
    assert isinstance(response, APIResponse)
    assert response.query == QUERY
    # The plan reflects the (fallback) understanding of a structuring query.
    assert ToolName.AML_PATTERN_DETECTOR in [s.tool for s in response.plan]


def test_missing_dataset_is_handled_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicitly simulate a missing dataset (independent of any on-disk sample):
    # the startup schema load fails softly, construction succeeds, analyze still runs.
    from app.config import settings

    monkeypatch.setattr(settings, "dataset_path", Path("/nonexistent/no_such_dataset.parquet"))
    pipeline = Pipeline()
    assert pipeline.schema_map == {}
    response = pipeline.analyze(QUERY)  # must still return a response
    assert isinstance(response, APIResponse)


def test_tool_failure_is_isolated_and_pipeline_still_returns() -> None:
    # A failing tool must be isolated as an ERROR trace; the pipeline still completes
    # and returns a valid APIResponse (executor failure-isolation, end to end).
    from app.agent.tool_set import TOOLS

    class _BoomTool(Tool):
        @property
        def name(self) -> ToolName:
            return ToolName.DATA_LOADER

        def run(
            self, context: Context, params: dict[str, Any]
        ) -> tuple[Context, ToolResult, TraceEntry]:
            raise RuntimeError("boom")

    registry = dict(TOOLS)
    registry[ToolName.DATA_LOADER] = _BoomTool()
    response = Pipeline(executor=Executor(tools=registry)).analyze(QUERY)
    assert ExecutionStatus.ERROR in [t.status for t in response.trace]  # isolated
    assert isinstance(response, APIResponse)  # analyze() did not raise


# ── determinism / purity ─────────────────────────────────────────────────────


def test_deterministic_output_across_instances() -> None:
    first = Pipeline().analyze(QUERY)
    second = Pipeline().analyze(QUERY)
    assert _normalize(first) == _normalize(second)


def test_uses_real_defaults_when_not_injected() -> None:
    pipeline = Pipeline()
    # Confirms the orchestrator coordinates the real completed modules.
    assert isinstance(pipeline._planner, DeterministicPlanner)
    assert isinstance(pipeline._executor, Executor)
    assert isinstance(pipeline._formatter, ResponseFormatter)
