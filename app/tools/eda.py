"""EDA tool — baseline profiling and distributions, on demand (F1, C1).

Runs **only** when the query intent is broad exploration (D3). Profiles the dataset
so the agent can characterise "normal" before hunting anomalies:

    * ``context.artifacts["eda"]`` — a stats dict (row/null counts, amount summary,
      transactions per day, top countries).
    * ``context.charts`` — a small fixed set of baseline Plotly chart specs
      (amount histogram, transactions-over-time, top-countries bar).

Each :class:`ChartSpec.spec` is a native Plotly figure dict, matching the Visualizer.
This tool only profiles — it never filters, detects, scores, or engineers features.
Empty/missing data is a first-class SUCCESS with empty stats/charts (D11).

Reads:  ``context.working_df`` (falls back to ``context.raw_df``).
Writes: ``context.artifacts["eda"]`` and ``context.charts``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import ChartSpec, Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

_TOP_COUNTRIES = 5


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
        """Profile the dataset into ``artifacts["eda"]`` + baseline ``charts``."""
        start = time.perf_counter()
        df = context.working_df if context.working_df is not None else context.raw_df
        rows_in = 0 if df is None else len(df)

        try:
            stats = self._profile(df)
            charts = [] if df is None or df.empty else self._charts(df)
        except Exception as exc:  # noqa: BLE001 - never corrupt/crash; report via trace
            logger.error("EDA failed: %s: %s", type(exc).__name__, exc)
            return context, *self._error(exc, rows_in=rows_in, start=start)

        context.artifacts["eda"] = stats
        context.charts.extend(charts)

        logger.info("EDA: profiled %d rows -> %d baseline chart(s)", rows_in, len(charts))
        result = ToolResult(
            tool=self.name,
            output={"n_rows": rows_in, "charts_produced": len(charts), "stats": stats},
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=rows_in,
            rows_out=len(charts),
            duration_ms=_elapsed_ms(start),
        )
        return context, result, trace

    # ── profiling ─────────────────────────────────────────────────────────────

    @staticmethod
    def _profile(df: pd.DataFrame | None) -> dict[str, Any]:
        """Compute the profiling stats dict (empty-safe)."""
        if df is None or df.empty:
            return {"n_rows": 0, "n_columns": 0, "null_counts": {}}

        stats: dict[str, Any] = {
            "n_rows": len(df),
            "n_columns": int(df.shape[1]),
            "null_counts": {str(c): int(n) for c, n in df.isna().sum().items()},
        }
        if "amount" in df.columns:
            amount = df["amount"].dropna()
            if not amount.empty:
                stats["amount"] = {
                    "min": float(amount.min()),
                    "max": float(amount.max()),
                    "mean": float(amount.mean()),
                    "median": float(amount.median()),
                }
        if "customer_id" in df.columns:
            stats["n_customers"] = int(df["customer_id"].nunique())
        if "country" in df.columns:
            stats["top_countries"] = {
                str(k): int(v)
                for k, v in df["country"].value_counts().head(_TOP_COUNTRIES).items()
            }
        return stats

    # ── baseline charts (native Plotly specs) ─────────────────────────────────

    def _charts(self, df: pd.DataFrame) -> list[ChartSpec]:
        builders = (self._amount_hist, self._txns_over_time, self._top_countries_bar)
        return [chart for build in builders if (chart := build(df)) is not None]

    @staticmethod
    def _amount_hist(df: pd.DataFrame) -> ChartSpec | None:
        if "amount" not in df.columns:
            return None
        return ChartSpec(
            type="histogram",
            title="Amount Distribution",
            spec={
                "data": [{"type": "histogram", "x": df["amount"].dropna().tolist()}],
                "layout": {"xaxis": {"title": "Amount"}, "yaxis": {"title": "Count"}},
            },
        )

    @staticmethod
    def _txns_over_time(df: pd.DataFrame) -> ChartSpec | None:
        if "timestamp" not in df.columns:
            return None
        per_day = df.groupby(df["timestamp"].dt.date).size().sort_index()
        if per_day.empty:
            return None
        return ChartSpec(
            type="timeseries",
            title="Transactions per Day",
            spec={
                "data": [
                    {
                        "type": "bar",
                        "x": [str(d) for d in per_day.index],
                        "y": per_day.tolist(),
                    }
                ],
                "layout": {"xaxis": {"title": "Date"}, "yaxis": {"title": "Transactions"}},
            },
        )

    @staticmethod
    def _top_countries_bar(df: pd.DataFrame) -> ChartSpec | None:
        if "country" not in df.columns:
            return None
        top = df["country"].value_counts().head(_TOP_COUNTRIES)
        if top.empty:
            return None
        return ChartSpec(
            type="bar",
            title="Top Countries by Transaction Count",
            spec={
                "data": [
                    {"type": "bar", "x": top.index.tolist(), "y": top.tolist()}
                ],
                "layout": {"xaxis": {"title": "Country"}, "yaxis": {"title": "Count"}},
            },
        )

    # ── error path ────────────────────────────────────────────────────────────

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
