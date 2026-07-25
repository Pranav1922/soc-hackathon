"""Filter tool — reduce the dataset to the query's subset (Requirement A5, B3).

Applies the query's date range, country, segment, transaction type, amount bounds,
and single-entity ids to narrow ``context.working_df`` (which DataLoader defaults to
the full cleaned dataset). Relative date ranges resolve against
``context.dataset_max_timestamp`` (D10), never the wall clock. An empty result is a
valid first-class outcome (D11), not an error.

Filters/entities are read from ``context.understanding`` (the authoritative typed
source); a filter whose column is absent from the data is skipped (logged), never a
crash. This tool only narrows rows — it never scores, detects, or engineers features.

Reads:  ``context.working_df`` (falls back to ``context.raw_df``),
        ``context.understanding``, ``context.dataset_max_timestamp``.
Writes: ``context.working_df``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, Filters, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

_CUSTOMER = "customer_id"


class Filter(Tool):
    """Slices ``context.working_df`` down to the query's requested subset."""

    @property
    def name(self) -> ToolName:
        return ToolName.FILTER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Narrow ``context.working_df`` per the understanding's filters/entities.

        Returns a ``SUCCESS`` trace with ``rows_in``/``rows_out`` (an empty subset is
        valid, D11); an ``ERROR`` trace on an unexpected failure (never raised).
        """
        start = time.perf_counter()
        df = context.working_df if context.working_df is not None else context.raw_df
        rows_in = 0 if df is None else len(df)

        if df is None:
            logger.warning("Filter: no dataframe in context; nothing to filter")
            return context, *self._result(applied=[], rows_in=0, rows_out=0, start=start)

        understanding = context.understanding
        filters = understanding.filters if understanding is not None else Filters()
        entities = list(understanding.entities) if understanding is not None else []

        try:
            mask = pd.Series(True, index=df.index)
            applied: list[str] = []
            mask, applied = self._apply_entities(df, entities, mask, applied)
            mask, applied = self._apply_filters(df, filters, context, mask, applied)
            filtered = df[mask]
        except Exception as exc:  # noqa: BLE001 - never corrupt/crash; report via trace
            logger.error("Filter failed: %s: %s", type(exc).__name__, exc)
            return context, *self._error(exc, rows_in=rows_in, start=start)

        context.working_df = filtered
        rows_out = len(filtered)
        logger.info(
            "Filter: %d -> %d rows (applied: %s)", rows_in, rows_out, applied or "none"
        )
        return context, *self._result(
            applied=applied, rows_in=rows_in, rows_out=rows_out, start=start
        )

    # ── filter application (each skips gracefully if its column is absent) ─────

    @staticmethod
    def _apply_entities(
        df: pd.DataFrame, entities: list[str], mask: pd.Series, applied: list[str]
    ) -> tuple[pd.Series, list[str]]:
        if entities and _CUSTOMER in df.columns:
            mask &= df[_CUSTOMER].astype(str).isin([str(e) for e in entities])
            applied.append("entities")
        elif entities:
            logger.warning("Filter: entities requested but no %r column", _CUSTOMER)
        return mask, applied

    def _apply_filters(
        self,
        df: pd.DataFrame,
        filters: Filters,
        context: Context,
        mask: pd.Series,
        applied: list[str],
    ) -> tuple[pd.Series, list[str]]:
        if filters.date_range is not None and "timestamp" in df.columns:
            mask &= self._date_mask(df, filters, context)
            applied.append("date_range")
        elif filters.date_range is not None:
            logger.warning("Filter: date filter requested but no 'timestamp' column")

        # Equality filters: (filter value, data column).
        for value, column, label in (
            (filters.country, "country", "country"),
            (filters.segment, "segment", "segment"),
            (filters.transaction_type, "direction", "transaction_type"),
        ):
            if value is None:
                continue
            if column in df.columns:
                mask &= df[column] == value
                applied.append(label)
            else:
                logger.warning("Filter: %s requested but no %r column", label, column)

        if "amount" in df.columns:
            if filters.min_amount is not None:
                mask &= df["amount"] >= filters.min_amount
                applied.append("min_amount")
            if filters.max_amount is not None:
                mask &= df["amount"] <= filters.max_amount
                applied.append("max_amount")
        elif filters.min_amount is not None or filters.max_amount is not None:
            logger.warning("Filter: amount filter requested but no 'amount' column")

        return mask, applied

    @staticmethod
    def _date_mask(df: pd.DataFrame, filters: Filters, context: Context) -> pd.Series:
        """Boolean mask for the date range (relative dates resolve to dataset max)."""
        date_range = filters.date_range
        assert date_range is not None  # guarded by caller
        ts = df["timestamp"]
        mask = pd.Series(True, index=df.index)
        if date_range.last_days is not None:
            anchor = context.dataset_max_timestamp
            if anchor is None:
                anchor = ts.max()  # fall back to the subset's own max (D10 spirit)
            cutoff = pd.Timestamp(anchor) - pd.Timedelta(days=date_range.last_days)
            mask &= ts >= cutoff
        if date_range.start is not None:
            mask &= ts >= pd.Timestamp(date_range.start)
        if date_range.end is not None:
            mask &= ts <= pd.Timestamp(date_range.end)
        return mask

    # ── trace builders ────────────────────────────────────────────────────────

    def _result(
        self, applied: list[str], rows_in: int, rows_out: int, start: float
    ) -> tuple[ToolResult, TraceEntry]:
        result = ToolResult(
            tool=self.name,
            output={"applied_filters": applied, "rows_in": rows_in, "rows_out": rows_out},
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=rows_in,
            rows_out=rows_out,
            duration_ms=_elapsed_ms(start),
        )
        return result, trace

    def _error(
        self, exc: Exception, rows_in: int, start: float
    ) -> tuple[ToolResult, TraceEntry]:
        result = ToolResult(tool=self.name, output={}, message=str(exc))
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.ERROR,
            rows_in=rows_in,
            rows_out=0,
            duration_ms=_elapsed_ms(start),
        )
        return result, trace


def _elapsed_ms(start: float) -> int:
    """Whole milliseconds elapsed since ``start`` (``perf_counter`` reference)."""
    return int((time.perf_counter() - start) * 1000)
