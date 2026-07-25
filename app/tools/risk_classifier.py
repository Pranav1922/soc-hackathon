"""RiskClassifier tool — fuse signals into a risk band (F4, D1, D7).

Applies the **frozen deterministic formula** from ``app.config.RISK``:
``score = min(1.0, rule_weight * rule_severity + anomaly_weight * anomaly_score)``,
then bands into low/medium/high. A confirmed rule hit floors the band at medium.
Produces one :class:`RiskResult` per flagged entity (explanation/action filled by
the Explainer and Recommender).

**Inputs (both optional — either may be absent depending on which plan steps
ran before this one):**
* ``context.artifacts["aml_hits_by_customer"]`` — ``dict[str, list[dict]]``,
  written by :class:`app.tools.aml_patterns.AMLPatternDetector`. Absent/empty if
  that step was skipped or found nothing.
* ``context.artifacts["anomaly_scores"]`` — ``dict[str, float]`` (entity_id ->
  score in ``[0, 1]``), written by :class:`app.tools.anomaly.AnomalyDetector`
  (not yet implemented — Phase 4). Absent means "no anomaly signal available",
  which the formula already handles correctly (``anomaly_score`` defaults to
  ``0.0`` per D7 — not an error condition).

Every entity appearing in *either* input is scored; an entity with only an
anomaly score and no rule hit is still eligible for a (lower) risk score.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import RISK, RULE_SEVERITY
from app.enums import EscalationAction, ExecutionStatus, RiskLevel, ToolName
from app.interfaces import Tool
from app.schemas import Context, RiskResult, ToolResult, TraceEntry

logger = logging.getLogger(__name__)


class RiskClassifier(Tool):
    """Combines rule hits and anomaly scores into banded :class:`RiskResult` items."""

    @property
    def name(self) -> ToolName:
        return ToolName.RISK_CLASSIFIER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Score every entity with a rule hit and/or an anomaly score (D7).

        Args:
            context: Shared state; reads ``artifacts["aml_hits_by_customer"]``
                and ``artifacts["anomaly_scores"]``, appends to ``context.flags``.
            params: Unused — the formula and bands are frozen constants
                (``app.config.RISK``), not runtime-tunable.

        Returns:
            The mutated context, a :class:`ToolResult` with band counts, and a
            :class:`TraceEntry`.
        """
        start = time.perf_counter()

        hits_by_entity: dict[str, list[dict[str, Any]]] = context.artifacts.get(
            "aml_hits_by_customer", {}
        )
        anomaly_scores: dict[str, float] = context.artifacts.get(
            "anomaly_scores", {}
        )
        entity_ids = sorted(set(hits_by_entity) | set(anomaly_scores))

        if not entity_ids:
            logger.info("RiskClassifier: no rule hits or anomaly scores to fuse.")
            duration_ms = int((time.perf_counter() - start) * 1000)
            result = ToolResult(
                tool=self.name,
                output={"entities_scored": 0, "band_counts": {}},
                message="No candidate entities to score.",
            )
            trace = TraceEntry(
                tool=self.name,
                status=ExecutionStatus.SUCCESS,
                rows_in=0,
                rows_out=0,
                duration_ms=duration_ms,
            )
            return context, result, trace

        new_flags: list[RiskResult] = [
            self._classify_entity(
                entity_id,
                hits_by_entity.get(entity_id, []),
                anomaly_scores.get(entity_id, 0.0),
            )
            for entity_id in entity_ids
        ]
        context.flags.extend(new_flags)

        band_counts: dict[str, int] = {}
        for flag in new_flags:
            band_counts[flag.risk.value] = band_counts.get(flag.risk.value, 0) + 1

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "RiskClassifier: scored %d entities -> %s", len(new_flags), band_counts
        )

        result = ToolResult(
            tool=self.name,
            output={"entities_scored": len(new_flags), "band_counts": band_counts},
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=len(entity_ids),
            rows_out=len(new_flags),
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _classify_entity(
        entity_id: str,
        rule_hits: list[dict[str, Any]],
        anomaly_score: float,
    ) -> RiskResult:
        """Fuse one entity's rule hits + anomaly score into a :class:`RiskResult`.

        Placeholder fields not owned by this tool:
            ``explanation`` — filled by :class:`app.tools.explainer.Explainer`.
            ``action`` — filled by :class:`app.tools.recommender.Recommender`
            (defaulted to the least-severe :attr:`EscalationAction.MONITOR` here
            so the object is valid before Recommender runs).
        """
        if rule_hits:
            rule_severity = max(RULE_SEVERITY[hit["pattern"]] for hit in rule_hits)
        else:
            rule_severity = 0.0

        raw_score = RISK.rule_weight * rule_severity + RISK.anomaly_weight * anomaly_score
        score = min(1.0, raw_score)

        floored = False
        if rule_hits and score < RISK.rule_hit_floor:
            # D7: a confirmed rule hit cannot score below the medium band —
            # rule_hit_floor == medium_band by construction, so this alone
            # guarantees the banding below lands on at least MEDIUM.
            score = RISK.rule_hit_floor
            floored = True

        risk = RiskClassifier._band(score)

        evidence: dict[str, Any] = {
            "rule_severity": rule_severity,
            "anomaly_score": anomaly_score,
            "rule_weight": RISK.rule_weight,
            "anomaly_weight": RISK.anomaly_weight,
            "raw_score": raw_score,
            "floored_to_medium": floored,
            "rule_hits": rule_hits,
        }

        return RiskResult(
            entity_id=entity_id,
            entity_type="customer",
            risk=risk,
            score=score,
            explanation="",
            action=EscalationAction.MONITOR,
            evidence=evidence,
        )

    @staticmethod
    def _band(score: float) -> RiskLevel:
        """Deterministic band cutoffs from ``app.config.RISK`` (D7)."""
        if score >= RISK.high_band:
            return RiskLevel.HIGH
        if score >= RISK.medium_band:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
