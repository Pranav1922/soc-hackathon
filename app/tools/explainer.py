"""Explainer tool — evidence-grounded, human-readable reasons per flag (F5, D9).

Template-first (D9): the explanation is built deterministically from the flag's real
evidence values and tied to the query intent + detected AML pattern. Optional LLM
phrasing (P1) may only rephrase while preserving the exact numbers, else it falls
back to the template. Implements the :class:`app.interfaces.Explainer` contract and
is also runnable as a :class:`Tool` step.

**P0 scope only** — no LLM call here (D9: "Don't block the demo on LLM narration").
LLM polish is explicitly P1 in the frozen docs; this implementation is the
template layer that P1 would wrap, never bypass.

Reads ``result.evidence["rule_hits"]`` and ``result.evidence["anomaly_score"]``,
both written by :class:`app.tools.risk_classifier.RiskClassifier` — never
recomputes evidence itself.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.enums import AMLPattern, ExecutionStatus, IntentType, ToolName
from app.interfaces import Explainer as ExplainerInterface
from app.interfaces import Tool
from app.schemas import Context, RiskResult, ToolResult, TraceEntry, Understanding

logger = logging.getLogger(__name__)

#: Fallback understanding used only when a flag is explained outside a full
#: pipeline run (e.g. direct unit testing) and ``context.understanding`` is
#: unset. In the real plan, QueryUnderstanding always runs before Explainer
#: (D2/D3), so this path is not expected to be hit in production.
_NEUTRAL_UNDERSTANDING = Understanding(intent=IntentType.DETECT_PATTERN)


class Explainer(Tool, ExplainerInterface):
    """Fills each flag's ``explanation`` from its evidence, tied to the query."""

    @property
    def name(self) -> ToolName:
        return ToolName.EXPLAINER

    def explain(self, result: RiskResult, understanding: Understanding) -> str:
        """Build a deterministic, evidence-grounded sentence for one flag.

        Args:
            result: The flagged entity, including RiskClassifier's evidence
                (``rule_hits`` list and ``anomaly_score``).
            understanding: The query interpretation — used to prefer the rule
                hit matching the requested ``aml_pattern`` when the entity has
                more than one, tying the explanation to what was actually asked.

        Returns:
            A single sentence built only from real evidence values — never an
            invented number.
        """
        rule_hits: list[dict[str, Any]] = result.evidence.get("rule_hits", [])
        anomaly_score: float = result.evidence.get("anomaly_score", 0.0)

        if rule_hits:
            hit = self._select_hit(rule_hits, understanding)
            template = _TEMPLATES.get(hit["pattern"], self._template_generic_rule)
            return template(hit["evidence"])

        if anomaly_score > 0.0:
            return self._template_anomaly_only(anomaly_score)

        # RiskClassifier only creates flags for entities with a rule hit and/or
        # a positive anomaly score, so this is a defensive fallback, not an
        # expected path.
        return (
            f"Entity {result.entity_id} was flagged with a risk score of "
            f"{result.score:.2f}, but no specific rule or anomaly evidence was "
            f"recorded."
        )

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Explain every flag in ``context.flags`` (idempotent — re-explains all).

        Args:
            context: Shared state; ``context.flags`` is mutated in place.
            params: Unused — P0 explanations are deterministic templates only.

        Returns:
            The mutated context, a :class:`ToolResult` summary, and a
            :class:`TraceEntry`.
        """
        start = time.perf_counter()
        understanding = context.understanding or _NEUTRAL_UNDERSTANDING
        rows_in = len(context.flags)

        for flag in context.flags:
            flag.explanation = self.explain(flag, understanding)

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Explainer: explained %d flag(s)", rows_in)

        result = ToolResult(
            tool=self.name,
            output={"explained": rows_in},
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=rows_in,
            rows_out=rows_in,
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── hit selection ────────────────────────────────────────────────────────

    @staticmethod
    def _select_hit(
        rule_hits: list[dict[str, Any]], understanding: Understanding
    ) -> dict[str, Any]:
        """Prefer the hit matching the query's requested pattern (D9: "tied to
        the query intent + detected AML pattern"); otherwise the strongest."""
        if understanding.aml_pattern != AMLPattern.NONE:
            for hit in rule_hits:
                if hit["pattern"] == understanding.aml_pattern:
                    return hit
        # No pattern requested (or requested one absent from this entity's
        # hits) — fall back to the most severe hit, matching RiskClassifier's
        # own "strongest rule wins" logic.
        from app.config import RULE_SEVERITY

        return max(rule_hits, key=lambda h: RULE_SEVERITY[h["pattern"]])

    # ── templates (D9: deterministic, evidence-only, no invented numbers) ────

    @staticmethod
    def _template_structuring(evidence: dict[str, Any]) -> str:
        return (
            f"Customer made {evidence['count']} cash deposits totaling "
            f"${evidence['total_amount']:,.2f}, each between "
            f"${evidence['amount_min']:,.0f} and ${evidence['amount_max']:,.0f}, "
            f"within a {evidence['window_days']}-day window "
            f"({evidence['window_start']} to {evidence['window_end']}) — "
            f"consistent with structuring to stay under the $10,000 CTR "
            f"reporting threshold."
        )

    @staticmethod
    def _template_smurfing(evidence: dict[str, Any]) -> str:
        return (
            f"Account received deposits under ${evidence['max_amount']:,.0f} "
            f"from {evidence['distinct_sources']} distinct sources "
            f"(total ${evidence['total_amount']:,.2f}) within a "
            f"{evidence['window_days']}-day window "
            f"({evidence['window_start']} to {evidence['window_end']}) — "
            f"consistent with smurfing."
        )

    @staticmethod
    def _template_rapid_cash_out(evidence: dict[str, Any]) -> str:
        return (
            f"A withdrawal of ${evidence['withdrawal_amount']:,.2f} "
            f"({evidence['ratio']:.0%} of the preceding "
            f"${evidence['deposit_amount']:,.2f} deposit) occurred within "
            f"{evidence['window_hours']}h of that deposit — consistent with "
            f"rapid cash-out."
        )

    @staticmethod
    def _template_layering(evidence: dict[str, Any]) -> str:
        chain = " -> ".join(evidence["chain"])
        return (
            f"Funds moved through a {evidence['hops']}-hop transfer chain "
            f"({chain}) within {evidence['window_hours']}h — consistent with "
            f"layering to obscure the funds' origin."
        )

    @staticmethod
    def _template_generic_rule(evidence: dict[str, Any]) -> str:
        # Defensive fallback for any future pattern added to AMLPattern without
        # a matching template — still evidence-grounded, just less specific.
        txn_ids = evidence.get("txn_ids", [])
        return (
            f"Entity matched a rule-based AML pattern with supporting "
            f"transaction(s) {txn_ids}."
        )

    @staticmethod
    def _template_anomaly_only(anomaly_score: float) -> str:
        return (
            f"Flagged by anomaly detection (score {anomaly_score:.2f}) with no "
            f"confirmed rule match — recommend manual review of the underlying "
            f"transaction pattern."
        )


#: Pattern -> template dispatch, built after the class so the bound staticmethods exist.
_TEMPLATES: dict[AMLPattern, Any] = {
    AMLPattern.STRUCTURING: Explainer._template_structuring,
    AMLPattern.SMURFING: Explainer._template_smurfing,
    AMLPattern.RAPID_CASH_OUT: Explainer._template_rapid_cash_out,
    AMLPattern.LAYERING: Explainer._template_layering,
}
