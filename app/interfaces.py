"""Abstract base classes — the contracts every implementation must honour.

These define *signatures only*; no business logic lives here. Concrete
implementations arrive in later phases (see ``docs/IMPLEMENTATION_PLAN.md``).

Boundaries (from ``docs/FOLDER_STRUCTURE.md``):
* ``agent/`` decides the plan and never computes numbers.
* ``tools/`` compute numbers and never decide the plan.
* The LLM lives in exactly one implementation of :class:`QueryUnderstanding`
  (and optionally :class:`Explainer` for phrasing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.enums import ToolName
from app.schemas import (
    Context,
    ExecutionPlan,
    RiskResult,
    ToolResult,
    TraceEntry,
    Understanding,
)


class Tool(ABC):
    """A single analysis capability the executor can run.

    Every tool has a stable :attr:`name` (a :class:`ToolName`) and a uniform
    ``run`` signature so the executor can iterate a plan without special-casing
    any tool (D4). Tools must tolerate an empty ``working_df`` (D11).
    """

    @property
    @abstractmethod
    def name(self) -> ToolName:
        """The tool's identity — must match its key in the tool-set registry."""
        raise NotImplementedError

    @abstractmethod
    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Execute the tool against the shared context.

        Args:
            context: Mutable shared state threaded through the plan.
            params: The step's ``inputs`` (from :class:`ExecutionStep`).

        Returns:
            The (mutated) context, a :class:`ToolResult` payload, and a
            :class:`TraceEntry` recording what actually happened at runtime.

        Notes:
            Implementations must handle an empty subset gracefully and record an
            honest :class:`ExecutionStatus` in the returned trace entry.
        """
        # TODO(Phase 1+): implement per-tool logic in app/tools/*.py.
        raise NotImplementedError


class QueryUnderstanding(ABC):
    """Turns a natural-language query into a structured :class:`Understanding`.

    The single LLM call on the critical path lives behind this interface (D2).
    Implementations must degrade to a keyword-based understanding on LLM failure,
    timeout, or malformed output.
    """

    @abstractmethod
    def understand(self, query: str, schema_map: dict[str, str]) -> Understanding:
        """Extract intent, entities, filters, and target AML pattern.

        Args:
            query: The raw user query.
            schema_map: Dataset column -> dtype, to ground extraction.

        Returns:
            A validated :class:`Understanding` (primary LLM result or fallback).
        """
        # TODO(Phase 3): LLM call + Pydantic validation + keyword fallback.
        raise NotImplementedError


class Planner(ABC):
    """Builds an :class:`ExecutionPlan` from an :class:`Understanding`.

    **Deterministic — no LLM** (D1, D3). The mapping from understanding to selected
    tools is a pure function, which makes it fully testable (golden-plan tests).
    """

    @abstractmethod
    def build_plan(self, understanding: Understanding) -> ExecutionPlan:
        """Select which tools to run, in what order, and which to skip.

        Args:
            understanding: The structured query interpretation.

        Returns:
            An :class:`ExecutionPlan` with ordered ``steps`` and populated
            ``skipped`` (the visible proof of selective invocation).
        """
        # TODO(Phase 1/3): implement the D3 deterministic planning rules.
        raise NotImplementedError


class Explainer(ABC):
    """Produces a human-readable, evidence-grounded reason for a flag.

    Template-first (D9): the explanation is built from real evidence values and is
    never allowed to invent numbers. Any optional LLM phrasing must preserve the
    exact figures or fall back to the template.
    """

    @abstractmethod
    def explain(self, result: RiskResult, understanding: Understanding) -> str:
        """Generate an explanation tied to the query intent and triggering rule.

        Args:
            result: The flagged entity, including its raw ``evidence``.
            understanding: The original query interpretation (to tie the wording
                to the user's intent and detected AML pattern).

        Returns:
            A concise natural-language explanation string.
        """
        # TODO(Phase 4): deterministic templates (+ optional validated LLM polish).
        raise NotImplementedError
