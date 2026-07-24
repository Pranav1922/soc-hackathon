"""DataLoader tool — load the sample dataset and clean it once (D5, D10).

Absorbs the former Preprocessor: dtype coercion, timestamp parsing, dedupe, and
derived ``date``/``hour`` columns all happen here, at load, exactly once. Also
records the dataset's max timestamp (for relative-date resolution) and the schema
map (for the LLM prompt and downstream tools).
"""

from __future__ import annotations

from typing import Any

from app.enums import ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry


class DataLoader(Tool):
    """Loads + cleans the transaction dataset into ``context.raw_df`` (pandas)."""

    @property
    def name(self) -> ToolName:
        return ToolName.DATA_LOADER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        # TODO(Phase 1): read parquet/CSV via pandas; coerce dtypes; parse
        # timestamps; dedupe; derive date/hour; set context.raw_df,
        # context.schema_map, context.dataset_max_timestamp. Never use the wall
        # clock for relative dates (D10).
        raise NotImplementedError("DataLoader.run — implemented in Phase 1")
