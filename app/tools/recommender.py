"""Recommender tool — map risk band to an escalation action (D6-output, D1).

Deterministic mapping tied to rule severity, not just the band:
low → monitor, medium → review, high → report. Sets each flag's ``action``.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class Recommender(Tool):
    """Assigns monitor / review / report to each flagged entity."""

    @property
    def name(self) -> ToolName:
        return ToolName.RECOMMENDER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 1/2): map RiskLevel -> EscalationAction for each flag in
        # context.flags, with a short justification tied to the triggering rule.
        raise NotImplementedError("Recommender.run — implemented in Phase 1/2")
