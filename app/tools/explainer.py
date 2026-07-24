"""Explainer tool — evidence-grounded, human-readable reasons per flag (F5, D9).

Template-first (D9): the explanation is built deterministically from the flag's real
evidence values and tied to the query intent + detected AML pattern. Optional LLM
phrasing (P1) may only rephrase while preserving the exact numbers, else it falls
back to the template. Implements the :class:`app.interfaces.Explainer` contract and
is also runnable as a :class:`Tool` step.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Explainer as ExplainerInterface
from app.interfaces import Tool
from app.schemas import Context, RiskResult, ToolResult, TraceEntry, Understanding


class Explainer(Tool, ExplainerInterface):
    """Fills each flag's ``explanation`` from its evidence, tied to the query."""

    @property
    def name(self) -> ToolName:
        return ToolName.EXPLAINER

    def explain(self, result: RiskResult, understanding: Understanding) -> str:
        # TODO(Phase 4): build a deterministic sentence from result.evidence +
        # understanding.aml_pattern; optional validated LLM polish.
        raise NotImplementedError("Explainer.explain — implemented in Phase 4")

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 4): call self.explain for each flag in context.flags and set
        # its explanation field.
        raise NotImplementedError("Explainer.run — implemented in Phase 4")
