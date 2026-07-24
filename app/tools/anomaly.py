"""AnomalyDetector tool — IsolationForest for unknown anomalies (F3, C6, D8).

The **secondary** detector: it catches anomalies the named rules don't, but never
overrides a clear rule hit. Runs only when the subset is large enough
(``config.ISOLATION_FOREST.min_samples``, D3/D8) and uses a fixed random state for
reproducible demos.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class AnomalyDetector(Tool):
    """Scores entities with a scaled IsolationForest; adds per-feature attribution."""

    @property
    def name(self) -> ToolName:
        return ToolName.ANOMALY_DETECTOR

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 4): StandardScaler -> IsolationForest(params from config);
        # normalize scores to [0,1]; compute feature-deviation attribution; write
        # anomaly scores to context.artifacts. Skip (SKIPPED trace) when N < min.
        raise NotImplementedError("AnomalyDetector.run — implemented in Phase 4")
