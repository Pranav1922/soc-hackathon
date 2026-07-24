"""Deterministic Planner — understanding → ExecutionPlan, no LLM (D1, D3).

A **pure function** of the :class:`Understanding`. Because it is deterministic, the
plan is fully testable (golden-plan tests) and identical on every run. It selects
only the tools a query needs and populates ``skipped`` for the ones it doesn't — the
visible proof that the system is not a fixed pipeline.

Scope (hard boundaries, per the module brief):
    * The planner ONLY decides which tools run and in which order.
    * It never calls the LLM, executes tools, loads data, computes features/rules/
      anomaly scores, classifies risk, or formats responses.

Routing rules (frozen: ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` D3, made concrete by
``docs/AGENT_FLOW.md`` §2–§3). Two documented tensions are resolved here, inside the
planner, without touching any frozen contract:

    1. AnomalyDetector's runtime ``N >= min_samples`` gate (D3/D8) cannot be known at
       plan time (the subset only exists after Filter runs). The planner therefore
       *selects* the AnomalyDetector based on intent/pattern and passes ``min_rows``
       (from config) in its ``inputs``; the tool enforces the gate at execution and
       records a SKIPPED trace if the subset is too small.
    2. ``rapid_cash_out`` appears both as a rule (D6) and as an anomaly/velocity path
       (AGENT_FLOW §3 contrast table, "Velocity, India" → AnomalyDetector, rules
       skipped). The contrast table is the operative routing artifact, so
       ``rapid_cash_out`` routes to the AnomalyDetector, and the deterministic rule
       engine handles structuring/smurfing/layering.
"""

from __future__ import annotations

import logging

from app.config import ISOLATION_FOREST, PLANNER
from app.enums import AMLPattern, IntentType, ToolName
from app.interfaces import Planner
from app.schemas import ExecutionPlan, ExecutionStep, Understanding

logger = logging.getLogger(__name__)

# Canonical execution order of the runnable, planner-selectable tools (D5). Excludes
# ResponseFormatter, which is invoked post-execution and is never a plan step (D3).
_TOOL_ORDER: tuple[ToolName, ...] = (
    ToolName.DATA_LOADER,
    ToolName.FILTER,
    ToolName.EDA,
    ToolName.FEATURE_ENGINEERING,
    ToolName.AML_PATTERN_DETECTOR,
    ToolName.ANOMALY_DETECTOR,
    ToolName.RISK_CLASSIFIER,
    ToolName.EXPLAINER,
    ToolName.RECOMMENDER,
    ToolName.VISUALIZER,
)

# Patterns caught by the deterministic rule engine vs. the anomaly/velocity path
# (AGENT_FLOW §3 contrast table). See tension (2) in the module docstring.
_RULE_BASED_PATTERNS: frozenset[AMLPattern] = frozenset(
    {AMLPattern.STRUCTURING, AMLPattern.SMURFING, AMLPattern.LAYERING}
)
_ANOMALY_PATTERNS: frozenset[AMLPattern] = frozenset({AMLPattern.RAPID_CASH_OUT})

# Intents that mean "detect a pattern across the (possibly compared) population".
_PATTERN_INTENTS: frozenset[IntentType] = frozenset(
    {IntentType.DETECT_PATTERN, IntentType.COMPARE}
)

# Rule patterns evaluated for broad / single-entity queries (no specific pattern given).
_ALL_RULE_PATTERNS: tuple[AMLPattern, ...] = (
    AMLPattern.STRUCTURING,
    AMLPattern.SMURFING,
    AMLPattern.LAYERING,
)

# Feature families the FeatureEngineering tool should compute, per target pattern.
# These are planner -> tool routing hints (which features to build), not tunable
# numbers, so they live here rather than in config.py.
_FEATURE_FAMILIES: dict[AMLPattern, tuple[str, ...]] = {
    AMLPattern.STRUCTURING: ("sub_threshold", "rolling_sum"),
    AMLPattern.SMURFING: ("distinct_sources", "small_deposit_count"),
    AMLPattern.LAYERING: ("transfer_chain",),
    AMLPattern.RAPID_CASH_OUT: ("velocity", "rapid_cash_out"),
    AMLPattern.NONE: (
        "frequency",
        "rolling_sum",
        "amount_deviation",
        "velocity",
        "rapid_cash_out",
    ),
}
# Families for a direct aggregation / threshold answer (no ML pattern).
_AGGREGATION_FAMILIES: tuple[str, ...] = ("transaction_count", "amount_aggregation")


class DeterministicPlanner(Planner):
    """Maps intent / pattern / filters / entities to an ordered tool plan (D3)."""

    def __init__(self) -> None:
        self._planner_cfg = PLANNER
        self._anomaly_min_rows = ISOLATION_FOREST.min_samples

    # ── public API ────────────────────────────────────────────────────────────

    def build_plan(self, understanding: Understanding) -> ExecutionPlan:
        """Build the deterministic execution plan for a validated understanding.

        Args:
            understanding: A validated :class:`Understanding` (produced upstream by
                Query Understanding or its keyword fallback).

        Returns:
            An :class:`ExecutionPlan` whose ``steps`` are ordered and whose
            ``skipped`` lists every runnable tool that was deliberately not selected.

        Raises:
            TypeError: If ``understanding`` is not an :class:`Understanding` instance.
        """
        if not isinstance(understanding, Understanding):
            raise TypeError(
                "DeterministicPlanner.build_plan expects an Understanding instance, "
                f"got {type(understanding).__name__!r}"
            )

        selected = self._select_tools(understanding)
        steps = [
            self._make_step(tool, understanding)
            for tool in _TOOL_ORDER
            if tool in selected
        ]
        skipped = [tool for tool in _TOOL_ORDER if tool not in selected]

        logger.debug(
            "Planned %d step(s) for intent=%s pattern=%s: %s | skipped: %s",
            len(steps),
            understanding.intent.value,
            understanding.aml_pattern.value,
            [s.tool.value for s in steps],
            [t.value for t in skipped],
        )
        return ExecutionPlan(steps=steps, skipped=skipped)

    # ── tool selection (the D3 rules) ─────────────────────────────────────────

    def _select_tools(self, u: Understanding) -> set[ToolName]:
        """Return the set of tools to run for this understanding (order-independent)."""
        intent = u.intent
        pattern = u.aml_pattern
        pattern_intent = intent in _PATTERN_INTENTS

        # DataLoader always runs first.
        selected: set[ToolName] = {ToolName.DATA_LOADER}

        # Filter iff the query carries any filter or entity to narrow the data.
        if self._has_filters(u):
            selected.add(ToolName.FILTER)

        # EDA only for broad exploration.
        include_eda = intent is IntentType.EDA
        if include_eda:
            selected.add(ToolName.EDA)

        # AML rule engine: named rule-based pattern, OR "run all rules" for
        # single-entity / EDA, OR a threshold query with a pattern, OR a broad
        # pattern-detection query with no specific pattern.
        include_aml = (
            pattern in _RULE_BASED_PATTERNS
            or intent in (IntentType.SINGLE_ENTITY, IntentType.EDA)
            or (intent is IntentType.THRESHOLD_RULE and pattern is not AMLPattern.NONE)
            or (pattern_intent and pattern is AMLPattern.NONE)
        )
        if include_aml:
            selected.add(ToolName.AML_PATTERN_DETECTOR)

        # Anomaly (unknown-anomaly / velocity) path: broad EDA, or a pattern query
        # whose pattern is anomaly-based (rapid_cash_out) or unspecified.
        include_anomaly = intent is IntentType.EDA or (
            pattern_intent and (pattern in _ANOMALY_PATTERNS or pattern is AMLPattern.NONE)
        )
        if include_anomaly:
            selected.add(ToolName.ANOMALY_DETECTOR)

        has_detector = include_aml or include_anomaly

        # Feature engineering is needed by any detector, and for direct aggregation
        # (threshold) answers even when no detector runs.
        if has_detector or intent is IntentType.THRESHOLD_RULE:
            selected.add(ToolName.FEATURE_ENGINEERING)

        # Classification / explanation / recommendation only make sense when a
        # detector can produce flags.
        if has_detector:
            selected.update(
                {
                    ToolName.RISK_CLASSIFIER,
                    ToolName.EXPLAINER,
                    ToolName.RECOMMENDER,
                }
            )

        # Visualizer runs when there is something visual to show (distributions or
        # flags); a pure scalar/aggregation answer skips it (D3).
        if include_eda or has_detector:
            selected.add(ToolName.VISUALIZER)

        return selected

    # ── step construction (reason / confidence / inputs) ──────────────────────

    def _make_step(self, tool: ToolName, u: Understanding) -> ExecutionStep:
        """Build a fully-populated :class:`ExecutionStep` for a selected tool."""
        reason, inputs, qu_derived = self._step_spec(tool, u)
        confidence = u.confidence if qu_derived else self._planner_cfg.deterministic_confidence
        return ExecutionStep(
            tool=tool,
            reason=reason,
            confidence=confidence,
            inputs=inputs,
        )

    def _step_spec(
        self, tool: ToolName, u: Understanding
    ) -> tuple[str, dict, bool]:
        """Return ``(reason, inputs, qu_derived)`` for a tool.

        ``qu_derived`` is True when the step's selection/parameters came from an
        LLM-extracted signal (filters, entities, or a specific AML pattern); such
        steps inherit the understanding's confidence to propagate extraction
        uncertainty (D12). Purely structural steps use the deterministic confidence.
        """
        pattern = u.aml_pattern
        specific_pattern = pattern is not AMLPattern.NONE

        if tool is ToolName.DATA_LOADER:
            return "Load and clean the transaction dataset", {}, False

        if tool is ToolName.FILTER:
            inputs: dict = {}
            filt = u.filters.model_dump(exclude_none=True)
            if filt:
                inputs["filters"] = filt
            if u.entities:
                inputs["entities"] = list(u.entities)
            return "Restrict the data to the requested subset", inputs, True

        if tool is ToolName.EDA:
            return "Profile the dataset to establish baseline behaviour", {}, False

        if tool is ToolName.FEATURE_ENGINEERING:
            # Threshold queries need direct aggregation features; pattern queries need
            # the families specific to their target typology.
            if u.intent is IntentType.THRESHOLD_RULE:
                families = _AGGREGATION_FAMILIES
            else:
                families = _FEATURE_FAMILIES[pattern]
            # Threshold FE families come from the intent (aggregation), not the
            # pattern, so it is not QU-pattern-derived in that case.
            fe_qu_derived = specific_pattern and u.intent is not IntentType.THRESHOLD_RULE
            return (
                "Build the AML features required for this query",
                {"families": list(families)},
                fe_qu_derived,
            )

        if tool is ToolName.AML_PATTERN_DETECTOR:
            if specific_pattern:
                patterns = [pattern.value]
                reason = f"Apply the {pattern.value} rule set"
            else:
                patterns = [p.value for p in _ALL_RULE_PATTERNS]
                reason = "Apply all AML rule sets"
            return reason, {"patterns": patterns}, specific_pattern

        if tool is ToolName.ANOMALY_DETECTOR:
            return (
                "Score the subset for unknown anomalies (runs only if large enough)",
                {"min_rows": self._anomaly_min_rows},
                specific_pattern,
            )

        if tool is ToolName.RISK_CLASSIFIER:
            return "Classify flagged entities into low/medium/high risk", {}, False

        if tool is ToolName.EXPLAINER:
            return "Generate an evidence-grounded reason per flag", {}, False

        if tool is ToolName.RECOMMENDER:
            return "Recommend an escalation action per flag", {}, False

        if tool is ToolName.VISUALIZER:
            return "Produce supporting charts for reviewer confidence", {}, False

        # Defensive: only reachable if a new selectable tool is added without a spec.
        raise ValueError(f"No step spec defined for tool {tool!r}")  # pragma: no cover

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _has_filters(u: Understanding) -> bool:
        """True if the understanding carries any filter or entity to narrow the data."""
        has_any_filter = bool(u.filters.model_dump(exclude_none=True))
        return has_any_filter or bool(u.entities)
