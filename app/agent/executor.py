"""Executor — runs the plan, threads Context, records the trace (EX).

Iterates an :class:`ExecutionPlan` step by step, looking each tool up in the
:data:`app.agent.tool_set.TOOLS` registry, threading a single mutable
:class:`Context` through them, and appending a :class:`TraceEntry` per step. Tool
errors are isolated (recorded as ``ERROR`` and execution continues) so one failing
tool never poisons the whole run.
"""

from __future__ import annotations

from app.agent.tool_set import TOOLS
from app.schemas import Context, ExecutionPlan


class Executor:
    """Deterministically executes an :class:`ExecutionPlan` against a context."""

    def __init__(self, tools=TOOLS) -> None:
        self._tools = tools

    def run_plan(self, context: Context, plan: ExecutionPlan) -> Context:
        """Run every step in order, mutating and returning the context.

        Args:
            context: The initial shared state (query + understanding set).
            plan: The plan produced by the deterministic planner.

        Returns:
            The context after all steps have run, with ``flags``, ``charts``, and
            ``trace`` populated.
        """
        # TODO(Phase 1): for each step -> get_tool -> time it -> run -> append
        # TraceEntry; wrap each tool call in try/except to isolate failures (record
        # ExecutionStatus.ERROR and continue). Never raise out of the loop.
        raise NotImplementedError("Executor.run_plan — implemented in Phase 1")
