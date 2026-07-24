"""FeatureEngineering tool — build AML features on demand (F2, C3).

Computes **only** the feature families the query needs (D3): transaction frequency,
rolling sums, amount deviation (per-customer z-score), velocity, rapid cash-out, and
sub-threshold counts. Output feeds both the rule engine and the anomaly detector.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class FeatureEngineering(Tool):
    """Derives model-/rule-ready AML features into ``context.features``."""

    @property
    def name(self) -> ToolName:
        return ToolName.FEATURE_ENGINEERING

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 2): compute requested feature families (params-driven) with
        # pandas groupby/rolling; set context.features keyed by entity/txn.
        raise NotImplementedError("FeatureEngineering.run — implemented in Phase 2")
