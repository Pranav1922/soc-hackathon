"""AnomalyDetector tool — IsolationForest for unknown anomalies (F3, C6, D8).

The **secondary** detector: it catches anomalies the named rules don't, never
overriding a clear rule hit. It runs only when the subset is large enough
(``config.ISOLATION_FOREST.min_samples``, D3/D8) and uses the frozen configuration
(fixed ``random_state``) for reproducible demos.

Pipeline role:
    * Reads the engineered per-entity feature table (``context.features``) — nothing
      else.
    * Scales the numeric features, fits an IsolationForest, and normalizes the raw
      scores to ``[0, 1]`` (higher = more anomalous), plus a lightweight per-entity
      feature-deviation attribution.
    * Writes the scores/attribution into ``context.artifacts`` — the approved scratch
      space the RiskClassifier later reads (it defaults to 0 when absent, D7).

Boundaries: it only scores anomalies. It never classifies risk, detects AML
patterns, explains, recommends, or touches ``context.flags``.

Reads:  ``context.features``; ``params["min_rows"]`` (gate; defaults to config).
Writes: ``context.artifacts["anomaly_scores"]`` and ``["anomaly_attribution"]``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.config import ISOLATION_FOREST
from app.enums import ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

_SCORES_KEY = "anomaly_scores"
_ATTRIBUTION_KEY = "anomaly_attribution"


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
        """Score the engineered feature table, gated by the minimum-sample rule.

        Args:
            context: Shared state; reads ``features`` and writes
                ``artifacts["anomaly_scores"]`` / ``["anomaly_attribution"]``.
            params: May include ``"min_rows"`` (defaults to
                ``config.ISOLATION_FOREST.min_samples``).

        Returns:
            The mutated context, a :class:`ToolResult`, and a :class:`TraceEntry`.
            Returns a ``SKIPPED`` trace when there are too few samples / no usable
            features (D3/D8); an ``ERROR`` trace on an unexpected failure (never
            raised out of the tool).
        """
        start = time.perf_counter()
        features = context.features
        min_rows = _coerce_min_rows(params.get("min_rows"))

        # ── minimum-sample / availability gate (D3/D8) ───────────────────────
        n_rows = 0 if features is None else len(features)
        if features is None or features.empty or n_rows < min_rows:
            reason = f"below minimum samples ({n_rows} < {min_rows})"
            context.artifacts[_SCORES_KEY] = {}
            logger.info("AnomalyDetector skipped: %s", reason)
            return context, *self._skipped(reason, rows_in=n_rows, start=start)

        numeric = features.select_dtypes(include="number")
        if numeric.shape[1] == 0:
            reason = "no numeric feature columns"
            context.artifacts[_SCORES_KEY] = {}
            logger.info("AnomalyDetector skipped: %s", reason)
            return context, *self._skipped(reason, rows_in=n_rows, start=start)

        # ── fit + score ──────────────────────────────────────────────────────
        try:
            scores, attribution = self._score(numeric)
        except Exception as exc:  # noqa: BLE001 - never corrupt/crash; report via trace
            logger.error("AnomalyDetector failed: %s: %s", type(exc).__name__, exc)
            return context, *self._error(exc, rows_in=n_rows, start=start)

        context.artifacts[_SCORES_KEY] = scores
        context.artifacts[_ATTRIBUTION_KEY] = attribution

        duration_ms = _elapsed_ms(start)
        logger.info(
            "AnomalyDetector: rows_in=%d scored=%d features=%d",
            n_rows,
            len(scores),
            numeric.shape[1],
        )
        result = ToolResult(
            tool=self.name,
            output={
                "n_scored": len(scores),
                "n_features": int(numeric.shape[1]),
                "feature_columns": list(numeric.columns),
                "contamination": ISOLATION_FOREST.contamination,
                "random_state": ISOLATION_FOREST.random_state,
            },
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=n_rows,
            rows_out=len(scores),
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── scoring (deterministic; frozen config) ────────────────────────────────

    def _score(
        self, numeric: pd.DataFrame
    ) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        """Fit a scaled IsolationForest and return (scores, attribution).

        Scores are normalized to ``[0, 1]`` (higher = more anomalous). Attribution
        is the single most-deviating feature per entity (largest absolute scaled
        value). Deterministic given the frozen ``random_state``.
        """
        cfg = ISOLATION_FOREST
        columns = list(numeric.columns)
        ids = [str(i) for i in numeric.index]

        matrix = np.nan_to_num(
            numeric.to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0
        )
        scaled = StandardScaler().fit_transform(matrix)

        model = IsolationForest(
            n_estimators=cfg.n_estimators,
            contamination=cfg.contamination,
            random_state=cfg.random_state,
        )
        model.fit(scaled)
        # score_samples: higher = more normal -> negate so higher = more anomalous.
        raw = -np.asarray(model.score_samples(scaled), dtype=float)
        normalized = _normalize(raw)

        scores = {entity: float(value) for entity, value in zip(ids, normalized)}

        top_idx = np.argmax(np.abs(scaled), axis=1)
        attribution = {
            ids[row]: {
                "top_feature": str(columns[top_idx[row]]),
                "deviation": round(float(abs(scaled[row, top_idx[row]])), 4),
            }
            for row in range(len(ids))
        }
        return scores, attribution

    # ── trace builders ────────────────────────────────────────────────────────

    def _skipped(
        self, reason: str, rows_in: int, start: float
    ) -> tuple[ToolResult, TraceEntry]:
        result = ToolResult(tool=self.name, output={"reason": reason}, message=reason)
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SKIPPED,
            rows_in=rows_in,
            rows_out=0,
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


def _coerce_min_rows(value: Any) -> int:
    """Resolve the sample gate, falling back to config on a missing/invalid value.

    Keeps a malformed ``min_rows`` param from raising out of the tool (the planner
    sends an int, but the tool must never crash on a bad param).
    """
    if value is None:
        return ISOLATION_FOREST.min_samples
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(
            "AnomalyDetector: invalid min_rows %r; using config default", value
        )
        return ISOLATION_FOREST.min_samples


def _normalize(values: np.ndarray) -> np.ndarray:
    """Min-max normalize to ``[0, 1]``; all-equal input maps to all zeros."""
    low = float(values.min())
    high = float(values.max())
    if high - low == 0.0:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def _elapsed_ms(start: float) -> int:
    """Whole milliseconds elapsed since ``start`` (``perf_counter`` reference)."""
    return int((time.perf_counter() - start) * 1000)
