"""Filter tool — reduce the dataset to the query's subset (Requirement A5, B3).

Applies date range, country, segment, transaction type, amount bounds, and
single-entity id filters to produce ``context.working_df``. Relative date ranges
resolve against ``context.dataset_max_timestamp`` (D10). An empty result is a valid
first-class outcome (D11), not an error.
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class Filter(Tool):
    """Slices ``context.raw_df`` into ``context.working_df`` per the query filters."""

    @property
    def name(self) -> ToolName:
        return ToolName.FILTER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 1): translate Understanding.filters / entities into a pandas
        # mask; resolve DateRange.last_days against dataset_max_timestamp; set
        # context.working_df; record rows_in/rows_out in the trace entry.
        raise NotImplementedError("Filter.run — implemented in Phase 1")
