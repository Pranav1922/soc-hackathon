"""AMLPatternDetector tool — deterministic typology rules (F3, C5, D6).

The **primary** detector and the source of the headline, auditable explanations.
Thresholds are frozen in ``app.config`` (D6): structuring, smurfing, rapid cash-out,
and (P2) layering. Each hit carries a machine-readable ``rule_id`` and the exact
triggering evidence for the Explainer.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class AMLPatternDetector(Tool):
    """Applies frozen AML rules and records rule hits + evidence on the context."""

    @property
    def name(self) -> ToolName:
        return ToolName.AML_PATTERN_DETECTOR

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 2): evaluate the requested pattern rule set using thresholds
        # from app.config.AML; attach hits (rule_id + evidence) to context for the
        # RiskClassifier and Explainer.
        raise NotImplementedError("AMLPatternDetector.run — implemented in Phase 2")
