"""Visualizer tool — charts/tables for reviewer confidence (E7, VIZ).

Emits a small fixed set of Plotly chart specs (timeline of flagged txns, amount
histogram vs the $10k CTR line, per-entity feature bars, risk distribution) into
``context.charts``. Runs unless the query answer is a single scalar (D3).
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class Visualizer(Tool):
    """Produces Plotly :class:`ChartSpec` items for the UI."""

    @property
    def name(self) -> ToolName:
        return ToolName.VISUALIZER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 4): build the fixed chart set from context.flags/features and
        # append ChartSpec objects to context.charts.
        raise NotImplementedError("Visualizer.run — implemented in Phase 4")
