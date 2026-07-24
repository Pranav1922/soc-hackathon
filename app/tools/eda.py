"""EDA tool — baseline profiling and distributions, on demand (F1, C1).

Runs **only** when the query intent is broad exploration (D3). Produces profiling
stats and baseline distribution chart specs so the agent can characterise "normal"
before hunting anomalies.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class EDA(Tool):
    """Profiles the (usually unfiltered) dataset: counts, distributions, baselines."""

    @property
    def name(self) -> ToolName:
        return ToolName.EDA

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 4): pandas describe/groupby profiling; write stats to
        # context.artifacts and baseline charts to context.charts (capped set).
        raise NotImplementedError("EDA.run — implemented in Phase 4")
