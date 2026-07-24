"""RiskClassifier tool — fuse signals into a risk band (F4, D1, D7).

Applies the **frozen deterministic formula** from ``app.config.RISK``:
``score = min(1.0, rule_weight * rule_severity + anomaly_weight * anomaly_score)``,
then bands into low/medium/high. A confirmed rule hit floors the band at medium.
Produces one :class:`RiskResult` per flagged entity (explanation/action filled by
the Explainer and Recommender).
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class RiskClassifier(Tool):
    """Combines rule hits and anomaly scores into banded :class:`RiskResult` items."""

    @property
    def name(self) -> ToolName:
        return ToolName.RISK_CLASSIFIER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 2): apply the frozen RISK formula + bands; build RiskResult
        # objects (risk, score, evidence) and append to context.flags.
        raise NotImplementedError("RiskClassifier.run — implemented in Phase 2")
