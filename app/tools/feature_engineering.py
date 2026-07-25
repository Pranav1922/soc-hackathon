"""FeatureEngineering tool — build AML features on demand (F2, C3, D3).

Computes **only** the feature families requested by the plan (D3). The engineered
features are exactly those defined by the architecture (MODULE_BREAKDOWN §9;
ARCHITECTURE §3; REQUIREMENTS C3):

    * ``frequency``        — transactions per customer.
    * ``rolling_sum``      — peak trailing N-day amount sum per customer
                             (window = ``config.AML.structuring.window_days``).
    * ``amount_deviation`` — per-customer max absolute amount z-score.
    * ``velocity``         — transactions per active day per customer.
    * ``rapid_cash_out``   — count of withdrawals within Δt of a preceding deposit
                             (Δt = ``config.AML.rapid_cash_out.window_hours``).
    * ``sub_threshold``    — count of amounts in the structuring band
                             (``config.AML.structuring.amount_min..amount_max``).

Output: a feature table keyed by ``customer_id``, stored in ``context.features``.

Boundaries: this tool only prepares features. It never loads files, applies AML
rules, scores anomalies, classifies risk, explains, recommends, or plans. Requested
families that are not one of the six defined features above are skipped (logged),
never invented.

Reads:  ``context.working_df`` (the filtered subset; falls back to ``context.raw_df``).
Writes: ``context.features``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from app.config import AML
from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

_CUSTOMER = "customer_id"

# The six engineered feature families defined by the architecture, in canonical
# (deterministic) output order. Values are the produced column names.
FREQUENCY = "frequency"
ROLLING_SUM = "rolling_sum"
AMOUNT_DEVIATION = "amount_deviation"
VELOCITY = "velocity"
RAPID_CASH_OUT = "rapid_cash_out"
SUB_THRESHOLD = "sub_threshold"

_CANONICAL_ORDER: tuple[str, ...] = (
    FREQUENCY,
    ROLLING_SUM,
    AMOUNT_DEVIATION,
    VELOCITY,
    RAPID_CASH_OUT,
    SUB_THRESHOLD,
)

_COLUMN_NAMES: dict[str, str] = {
    FREQUENCY: "txn_count",
    ROLLING_SUM: "rolling_sum_max",
    AMOUNT_DEVIATION: "amount_zscore_max",
    VELOCITY: "velocity_per_day",
    RAPID_CASH_OUT: "rapid_cash_out_count",
    SUB_THRESHOLD: "sub_threshold_count",
}

# Columns each family needs to be computable (beyond ``customer_id``, always required).
_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    FREQUENCY: (),
    ROLLING_SUM: ("timestamp", "amount"),
    AMOUNT_DEVIATION: ("amount",),
    VELOCITY: ("timestamp",),
    RAPID_CASH_OUT: ("timestamp", "direction"),
    SUB_THRESHOLD: ("amount",),
}


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
        """Compute the requested feature families for the current working subset.

        Args:
            context: Shared state; reads ``working_df`` (or ``raw_df``) and writes
                ``features``.
            params: May include ``"families"`` — a list of requested family names.
                When absent/empty, all six defined families are computed.

        Returns:
            The mutated context, a :class:`ToolResult` with build stats, and a
            :class:`TraceEntry`. A tool-level failure is reported as an ``ERROR``
            trace, never raised (the executor records it and continues).
        """
        start = time.perf_counter()
        df = self._source_frame(context)
        requested, skipped_unknown = self._resolve_families(params)

        try:
            features, computed, skipped_cols = self._build_features(df, requested)
        except Exception as exc:  # noqa: BLE001 - never corrupt/crash; report via trace
            logger.error("FeatureEngineering failed: %s: %s", type(exc).__name__, exc)
            return context, *self._error(exc, rows_in=len(df), start=start)

        skipped = sorted(set(skipped_unknown) | set(skipped_cols))
        context.features = features

        duration_ms = _elapsed_ms(start)
        rows_out = len(features)
        logger.info(
            "FeatureEngineering: rows_in=%d customers=%d families=%s skipped=%s",
            len(df),
            rows_out,
            computed,
            skipped,
        )
        result = ToolResult(
            tool=self.name,
            output={
                "n_customers": rows_out,
                "feature_columns": list(features.columns),
                "computed_families": computed,
                "skipped_families": skipped,
            },
            message=None if computed else "no features computed",
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=len(df),
            rows_out=rows_out,
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── inputs ────────────────────────────────────────────────────────────────

    @staticmethod
    def _source_frame(context: Context) -> pd.DataFrame:
        """The subset to engineer over: ``working_df`` if present, else ``raw_df``.

        Returns an empty DataFrame when neither is available so downstream logic
        treats "no data" as a first-class empty result (D11), not a crash.
        """
        if context.working_df is not None:
            return context.working_df
        if context.raw_df is not None:
            return context.raw_df
        logger.warning("FeatureEngineering: no dataframe in context; empty features")
        return pd.DataFrame()

    @staticmethod
    def _resolve_families(params: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Split the requested families into (known, unknown-skipped).

        Absent/empty/invalid ``families`` means "all six defined families".
        """
        raw = params.get("families")
        if not isinstance(raw, (list, tuple)) or not raw:
            return list(_CANONICAL_ORDER), []
        requested = [str(f) for f in raw]
        known = [f for f in _CANONICAL_ORDER if f in requested]
        unknown = [f for f in requested if f not in _CANONICAL_ORDER]
        if unknown:
            logger.warning(
                "FeatureEngineering: skipping undefined feature families %s", unknown
            )
        return known, unknown

    # ── feature building ──────────────────────────────────────────────────────

    def _build_features(
        self, df: pd.DataFrame, requested: list[str]
    ) -> tuple[pd.DataFrame, list[str], list[str]]:
        """Build the requested feature columns into a per-customer table.

        Returns:
            ``(features_df, computed_families, skipped_families)`` where
            ``skipped_families`` are requested families missing an input column.
        """
        wanted = [f for f in _CANONICAL_ORDER if f in requested]

        # Empty in -> empty out (first-class empty result, D11). No column checks:
        # there is nothing to compute, so requested families are trivially satisfied.
        if df.empty:
            empty = {_COLUMN_NAMES[f]: pd.Series(dtype=float) for f in wanted}
            features = pd.DataFrame(empty, index=pd.Index([], name=_CUSTOMER))
            return features, wanted, []

        if _CUSTOMER not in df.columns:
            raise ValueError(f"required column {_CUSTOMER!r} is missing")

        customers = pd.Index(
            sorted(df[_CUSTOMER].dropna().unique()), name=_CUSTOMER
        )
        builders: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
            FREQUENCY: self._frequency,
            ROLLING_SUM: self._rolling_sum,
            AMOUNT_DEVIATION: self._amount_deviation,
            VELOCITY: self._velocity,
            RAPID_CASH_OUT: self._rapid_cash_out,
            SUB_THRESHOLD: self._sub_threshold,
        }

        columns: dict[str, pd.Series] = {}
        computed: list[str] = []
        skipped: list[str] = []
        for family in wanted:
            missing = [c for c in _REQUIRED_COLUMNS[family] if c not in df.columns]
            if missing:
                logger.warning(
                    "FeatureEngineering: skip %s (missing columns %s)", family, missing
                )
                skipped.append(family)
                continue
            series = builders[family](df)
            columns[_COLUMN_NAMES[family]] = series.reindex(customers, fill_value=0)
            computed.append(family)

        features = pd.DataFrame(columns, index=customers)
        return features, computed, skipped

    # ── individual feature computations (pure, deterministic) ─────────────────

    @staticmethod
    def _frequency(df: pd.DataFrame) -> pd.Series:
        return df.groupby(_CUSTOMER).size().astype(float)

    @staticmethod
    def _velocity(df: pd.DataFrame) -> pd.Series:
        grouped = df.groupby(_CUSTOMER)["timestamp"]
        span_days = (grouped.max() - grouped.min()).dt.days.add(1).clip(lower=1)
        counts = df.groupby(_CUSTOMER).size()
        return (counts / span_days).astype(float)

    @staticmethod
    def _amount_deviation(df: pd.DataFrame) -> pd.Series:
        grouped = df.groupby(_CUSTOMER)["amount"]
        mean = grouped.transform("mean")
        std = grouped.transform("std")
        z = ((df["amount"] - mean) / std).replace([np.inf, -np.inf], np.nan).abs()
        return z.groupby(df[_CUSTOMER]).max().fillna(0.0).astype(float)

    @staticmethod
    def _rolling_sum(df: pd.DataFrame) -> pd.Series:
        window = f"{AML.structuring.window_days}D"
        out: dict[Any, float] = {}
        for customer, sub in df.groupby(_CUSTOMER):
            series = sub.set_index("timestamp")["amount"].sort_index()
            peak = series.rolling(window).sum().max()
            # A window of only-NaN amounts yields NaN; coerce to 0.0 so no feature
            # column ever contains NaN (never silently corrupt data for downstream ML).
            out[customer] = float(peak) if pd.notna(peak) else 0.0
        return pd.Series(out, dtype=float)

    @staticmethod
    def _rapid_cash_out(df: pd.DataFrame) -> pd.Series:
        delta = np.timedelta64(AML.rapid_cash_out.window_hours, "h")
        out: dict[Any, int] = {}
        for customer, sub in df.groupby(_CUSTOMER):
            deposits = sub.loc[sub["direction"] == "deposit", "timestamp"].to_numpy()
            withdrawals = sub.loc[
                sub["direction"] == "withdrawal", "timestamp"
            ].to_numpy()
            count = 0
            if deposits.size:
                for w in withdrawals:
                    if ((deposits <= w) & ((w - deposits) <= delta)).any():
                        count += 1
            out[customer] = count
        return pd.Series(out, dtype=float)

    @staticmethod
    def _sub_threshold(df: pd.DataFrame) -> pd.Series:
        band = df["amount"].between(
            AML.structuring.amount_min, AML.structuring.amount_max
        )
        return df.loc[band].groupby(_CUSTOMER).size().astype(float)

    # ── error path ────────────────────────────────────────────────────────────

    def _error(
        self, exc: Exception, rows_in: int, start: float
    ) -> tuple[ToolResult, TraceEntry]:
        """Build the (ToolResult, TraceEntry) pair for a tool-level failure."""
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
