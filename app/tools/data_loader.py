"""DataLoader tool — load the sample dataset and clean it once (D5, D10).

Absorbs the former Preprocessor: dtype coercion, timestamp parsing, dedupe, and
derived ``date``/``hour`` columns all happen here, at load, exactly once. Also
records the dataset's max timestamp (for relative-date resolution) and the schema
map (for the LLM prompt and downstream tools).

Pandas + parquet only (D10) — no DuckDB, no SQL server. Relative dates are always
resolved against ``context.dataset_max_timestamp``, never the wall clock (D10).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

#: Canonical transaction schema (mirrors ``scripts/generate_synthetic.py``
#: ``SCHEMA_COLUMNS`` — keep the two in sync if the dataset schema changes).
REQUIRED_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "txn_id",
    "timestamp",
    "amount",
    "direction",
    "counterparty_id",
    "country",
    "channel",
)

#: Columns coerced to pandas' nullable string dtype (identifiers / categoricals).
_STRING_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "txn_id",
    "direction",
    "counterparty_id",
    "country",
    "channel",
)

#: Parquet vs. CSV, dispatched on suffix; anything else is unsupported.
_PARQUET_SUFFIXES: frozenset[str] = frozenset({".parquet", ".pq"})
_CSV_SUFFIXES: frozenset[str] = frozenset({".csv"})


class DataLoader(Tool):
    """Loads + cleans the transaction dataset into ``context.raw_df`` (pandas).

    Responsibilities (D5, D10):
        * Read the configured dataset (parquet or CSV) into a DataFrame.
        * Validate that every required column (:data:`REQUIRED_COLUMNS`) is present.
        * Coerce dtypes (timestamps, amount, identifier/categorical columns) and
          drop rows that fail to coerce (malformed data), logging how many.
        * Drop exact duplicate ``txn_id`` rows.
        * Derive ``date`` and ``hour`` columns from ``timestamp``.
        * Populate ``context.raw_df``, ``context.working_df`` (a full-dataset
          default so tools can run even when the Filter step is skipped —
          Filter narrows it further when the plan includes it),
          ``context.schema_map``, and ``context.dataset_max_timestamp``.

    Never computes features, applies AML rules, scores anomalies, or makes
    planning decisions — those are downstream tools' jobs.
    """

    @property
    def name(self) -> ToolName:
        return ToolName.DATA_LOADER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Load, validate, and clean the dataset once at the start of a plan.

        Args:
            context: Shared state; ``raw_df``/``working_df``/``schema_map``/
                ``dataset_max_timestamp`` are populated on success.
            params: May include ``"path"`` (str | Path) to override
                ``settings.dataset_path`` — primarily for tests.

        Returns:
            The mutated context, a :class:`ToolResult` with load stats, and a
            :class:`TraceEntry` recording what actually happened.
        """
        start = time.perf_counter()
        path = Path(params.get("path", settings.dataset_path))

        try:
            raw_rows, df = self._load_and_clean(path)
        except (FileNotFoundError, ValueError) as exc:
            # Missing file / unsupported format / no required columns present at
            # all — nothing downstream can proceed. Handled gracefully (never
            # raised out of the tool) so the executor's trace tells the whole
            # story instead of crashing the run.
            logger.error("DataLoader failed to load %s: %s", path, exc)
            duration_ms = int((time.perf_counter() - start) * 1000)
            result = ToolResult(
                tool=self.name,
                output={"path": str(path)},
                message=str(exc),
            )
            trace = TraceEntry(
                tool=self.name,
                status=ExecutionStatus.ERROR,
                rows_in=0,
                rows_out=0,
                duration_ms=duration_ms,
            )
            return context, result, trace

        # Populate context. working_df defaults to the full cleaned dataset so
        # tools that read it still see data on plans that skip Filter (D3: "not
        # every query needs every tool"); Filter narrows it further when planned.
        context.raw_df = df
        context.working_df = df.copy()
        context.schema_map = {col: str(dtype) for col, dtype in df.dtypes.items()}
        context.dataset_max_timestamp = (
            df["timestamp"].max() if not df.empty else None
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        rows_out = len(df)
        logger.info(
            "DataLoader: loaded %d rows from %s -> %d rows after cleaning",
            raw_rows,
            path,
            rows_out,
        )

        result = ToolResult(
            tool=self.name,
            output={
                "path": str(path),
                "rows_loaded": raw_rows,
                "rows_after_cleaning": rows_out,
                "columns": list(df.columns),
                "dataset_max_timestamp": context.dataset_max_timestamp,
            },
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=raw_rows,
            rows_out=rows_out,
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── internal helpers ────────────────────────────────────────────────────

    def _load_and_clean(self, path: Path) -> tuple[int, pd.DataFrame]:
        """Read ``path`` and apply the once-at-load cleaning pipeline.

        Returns:
            ``(raw_row_count, cleaned_dataframe)`` — ``raw_row_count`` is the row
            count exactly as read, before any coercion/dedup/drop, for an honest
            ``rows_in`` in the trace.

        Raises:
            FileNotFoundError: ``path`` does not exist.
            ValueError: unsupported file extension, or required columns are
                missing entirely (a fundamentally wrong/incompatible file).
        """
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found at {path}")

        df = self._read(path)
        raw_rows = len(df)

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Dataset at {path} is missing required columns: {missing}"
            )

        df = self._coerce_dtypes(df)
        df = self._drop_malformed(df, path)
        df = self._dedupe(df)
        df = self._derive_columns(df)

        return raw_rows, df

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        """Dispatch to the right pandas reader by file suffix."""
        suffix = path.suffix.lower()
        if suffix in _PARQUET_SUFFIXES:
            return pd.read_parquet(path)
        if suffix in _CSV_SUFFIXES:
            return pd.read_csv(path)
        raise ValueError(
            f"Unsupported dataset format {suffix!r} for {path} "
            f"(expected one of {sorted(_PARQUET_SUFFIXES | _CSV_SUFFIXES)})"
        )

    @staticmethod
    def _coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Coerce each required column to its expected dtype.

        Unparseable values become ``NaT``/``NaN`` here and are dropped as
        malformed rows in :meth:`_drop_malformed` — coercion never raises.
        """
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").astype(float)
        for col in _STRING_COLUMNS:
            df[col] = df[col].astype("string")
        return df

    @staticmethod
    def _drop_malformed(df: pd.DataFrame, path: Path) -> pd.DataFrame:
        """Drop rows with unparseable timestamp/amount or a null identifier."""
        before = len(df)
        mask = (
            df["timestamp"].notna()
            & df["amount"].notna()
            & df["customer_id"].notna()
            & df["txn_id"].notna()
        )
        df = df.loc[mask].reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            logger.warning(
                "DataLoader: dropped %d malformed row(s) from %s", dropped, path
            )
        return df

    @staticmethod
    def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
        """Drop exact duplicate ``txn_id`` rows, keeping the first occurrence."""
        before = len(df)
        df = df.drop_duplicates(subset="txn_id", keep="first").reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            logger.warning("DataLoader: dropped %d duplicate txn_id row(s)", dropped)
        return df

    @staticmethod
    def _derive_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Derive ``date`` and ``hour`` from ``timestamp`` (empty-safe, D11)."""
        df = df.copy()
        if df.empty:
            df["date"] = pd.Series(dtype="object")
            df["hour"] = pd.Series(dtype="Int64")
            return df
        df["date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour.astype("Int64")
        return df
