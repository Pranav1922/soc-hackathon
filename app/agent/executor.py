"""Executor — runs the plan, threads Context, records the trace (EX).

Iterates an :class:`ExecutionPlan` step by step, resolving each tool from an injected
registry, threading a single mutable :class:`Context` through them, and appending a
:class:`TraceEntry` per step. Tool errors are isolated: a failing tool is recorded as
an ``ERROR`` trace entry (and logged) and execution continues, so one failing tool
never poisons the whole run (ARCHITECTURE §7; MODULE_BREAKDOWN EX).

Scope (hard boundaries): the Executor ONLY executes a plan. It never plans, parses
language, computes features/rules/anomaly scores, classifies risk, explains, or calls
an LLM — those live in the tools it invokes.

Notes on the frozen contracts:
    * There is no separate ``ExecutionResult`` type and no ``Executor`` ABC; the
      executor's output is the enriched :class:`Context` (its ``flags``, ``charts``,
      and ``trace`` populated), which the ResponseFormatter later turns into the
      response. This method keeps the established ``run_plan(...) -> Context`` shape.
    * :class:`TraceEntry` has no ``error`` field (D12, runtime-info only); a failure
      is recorded via ``status == ERROR`` and the exception is emitted to the log.
    * :meth:`app.interfaces.Tool.run` returns its own ``TraceEntry``; the Executor
      owns timing, so it stamps the measured ``duration_ms`` onto that entry.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from time import perf_counter

from app.agent.tool_set import TOOLS
from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ExecutionPlan, ExecutionStep, TraceEntry

logger = logging.getLogger(__name__)

#: Key under which per-step ``ToolResult`` payloads are collected on the context.
_TOOL_RESULTS_KEY = "tool_results"


class Executor:
    """Deterministically executes an :class:`ExecutionPlan` against a context."""

    def __init__(self, tools: Mapping[ToolName, Tool] | None = None) -> None:
        """Create an executor.

        Args:
            tools: Registry mapping each :class:`ToolName` to a concrete
                :class:`Tool`. Injected for testability; defaults to the project
                tool set. The executor never instantiates tools itself.
        """
        self._tools: Mapping[ToolName, Tool] = tools if tools is not None else TOOLS

    # ── public API ────────────────────────────────────────────────────────────

    def run_plan(self, context: Context, plan: ExecutionPlan) -> Context:
        """Run every planned step in order, threading and returning the context.

        Each step produces exactly one :class:`TraceEntry` appended to
        ``context.trace``. Tool failures are isolated (recorded as ``ERROR`` and
        logged) and never propagate out of this method.

        Args:
            context: Initial shared state (query + understanding already set).
            plan: The plan produced by the deterministic planner.

        Returns:
            The same context, enriched by the tools that ran (``flags``, ``charts``)
            and with one trace entry per executed step.
        """
        logger.info("Executor start: %d step(s) planned", len(plan.steps))
        for step in plan.steps:
            context = self._run_step(context, step)
        logger.info(
            "Executor done: %d trace entr(y/ies) recorded", len(context.trace)
        )
        return context

    # ── per-step execution ────────────────────────────────────────────────────

    def _run_step(self, context: Context, step: ExecutionStep) -> Context:
        """Execute a single step, recording its trace; never raises."""
        tool = self._tools.get(step.tool)
        if tool is None:
            # Planner only emits registered tools; guard defensively regardless.
            logger.error("tool=%s status=ERROR reason=unregistered", step.tool.value)
            context.trace.append(
                TraceEntry(
                    tool=step.tool,
                    status=ExecutionStatus.ERROR,
                    rows_in=_current_rows(context),
                    rows_out=0,
                    duration_ms=0,
                )
            )
            return context

        rows_in = _current_rows(context)
        start = perf_counter()
        try:
            context, result, trace_entry = tool.run(context, step.inputs)
        except Exception as exc:  # noqa: BLE001 - isolate tool failures (execution policy)
            elapsed_ms = _elapsed_ms(start)
            logger.error(
                "tool=%s status=ERROR duration_ms=%d error=%s: %s",
                step.tool.value,
                elapsed_ms,
                type(exc).__name__,
                exc,
            )
            context.trace.append(
                TraceEntry(
                    tool=step.tool,
                    status=ExecutionStatus.ERROR,
                    rows_in=rows_in,
                    rows_out=0,
                    duration_ms=elapsed_ms,
                )
            )
            return context

        elapsed_ms = _elapsed_ms(start)
        # The Executor owns the clock; stamp the measured duration onto the tool's
        # trace entry (which carries status + row counts from the tool's view).
        trace_entry = trace_entry.model_copy(update={"duration_ms": elapsed_ms})
        context.trace.append(trace_entry)
        context.artifacts.setdefault(_TOOL_RESULTS_KEY, []).append(result)
        logger.info(
            "tool=%s status=%s rows_in=%d rows_out=%d duration_ms=%d",
            trace_entry.tool.value,
            trace_entry.status.value,
            trace_entry.rows_in,
            trace_entry.rows_out,
            trace_entry.duration_ms,
        )
        return context


# ── helpers ───────────────────────────────────────────────────────────────────


def _elapsed_ms(start: float) -> int:
    """Whole milliseconds elapsed since ``start`` (``perf_counter`` reference)."""
    return int((perf_counter() - start) * 1000)


def _current_rows(context: Context) -> int:
    """Best-effort current row count (working subset, else full dataset, else 0)."""
    for frame in (context.working_df, context.raw_df):
        if frame is not None:
            return len(frame)
    return 0
