"""Recommender tool — map risk band to an escalation action (D6-output, D1).

Deterministic mapping tied to rule severity, not just the band:
low → monitor, medium → review, high → report. Sets each flag's ``action``.

MODULE_BREAKDOWN.md flags a risk with this module: "trivial mapping looks thin
→ tie to rule severity, not just band." The *action* itself is still the exact
frozen band mapping (also pinned in ``EscalationAction``'s own docstring) — the
mitigation is that the accompanying justification names the specific triggering
rule and its severity (or the anomaly score, if no rule fired), so the
recommendation reads as evidence-driven rather than a bare lookup table.

Runs after :class:`app.tools.explainer.Explainer` (D3 plan order), so
``flag.explanation`` is already set — this tool never touches it. The short
justification text is instead stored at ``flag.evidence["escalation_reason"]``,
since ``RiskResult`` has no dedicated justification field of its own.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import RULE_SEVERITY
from app.enums import EscalationAction, ExecutionStatus, RiskLevel, ToolName
from app.interfaces import Tool
from app.schemas import Context, RiskResult, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

#: The frozen band -> action mapping (D1/D6-output; mirrors EscalationAction's
#: own docstring). Defined once here so it can't drift from the enum's contract.
_ACTION_BY_BAND: dict[RiskLevel, EscalationAction] = {
    RiskLevel.LOW: EscalationAction.MONITOR,
    RiskLevel.MEDIUM: EscalationAction.REVIEW,
    RiskLevel.HIGH: EscalationAction.REPORT,
}

#: Action-specific closing phrase for the justification sentence.
_ACTION_PHRASE: dict[EscalationAction, str] = {
    EscalationAction.MONITOR: "routine monitoring is sufficient",
    EscalationAction.REVIEW: "recommend analyst review",
    EscalationAction.REPORT: "recommend filing a Suspicious Activity Report (SAR)",
}


class Recommender(Tool):
    """Assigns monitor / review / report to each flagged entity."""

    @property
    def name(self) -> ToolName:
        return ToolName.RECOMMENDER

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Map each flag's risk band to an escalation action + justification.

        Args:
            context: Shared state; ``context.flags`` is mutated in place —
                ``action`` is set and ``evidence["escalation_reason"]`` is added.
            params: Unused — the band -> action mapping is a frozen constant.

        Returns:
            The mutated context, a :class:`ToolResult` with action counts, and a
            :class:`TraceEntry`.
        """
        start = time.perf_counter()
        rows_in = len(context.flags)

        for flag in context.flags:
            action = _ACTION_BY_BAND[flag.risk]
            flag.action = action
            flag.evidence["escalation_reason"] = self._justify(flag, action)

        action_counts: dict[str, int] = {}
        for flag in context.flags:
            action_counts[flag.action.value] = action_counts.get(flag.action.value, 0) + 1

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Recommender: assigned actions for %d flag(s) -> %s", rows_in, action_counts)

        result = ToolResult(
            tool=self.name,
            output={"recommended": rows_in, "action_counts": action_counts},
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=rows_in,
            rows_out=rows_in,
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _justify(flag: RiskResult, action: EscalationAction) -> str:
        """Build a short, evidence-tied justification (not just the band name)."""
        rule_hits: list[dict[str, Any]] = flag.evidence.get("rule_hits", [])
        band_label = flag.risk.value.capitalize()
        action_phrase = _ACTION_PHRASE[action]

        if rule_hits:
            strongest = max(rule_hits, key=lambda h: RULE_SEVERITY[h["pattern"]])
            pattern_label = strongest["pattern"].value.replace("_", " ")
            severity = RULE_SEVERITY[strongest["pattern"]]
            basis = (
                f"{band_label} risk due to a confirmed {pattern_label} rule hit "
                f"(severity {severity:.1f})"
            )
        else:
            anomaly_score = flag.evidence.get("anomaly_score", 0.0)
            basis = (
                f"{band_label} risk based on an anomaly score of "
                f"{anomaly_score:.2f} with no confirmed rule match"
            )

        return f"{basis}; {action_phrase}."
