"""Golden-plan & routing tests for the DeterministicPlanner (D18).

These are the proof of the headline requirement: different queries produce different
plans, deterministically. Every assertion runs today (no skips) — the planner is pure
business logic with no external dependencies.
"""

from __future__ import annotations

import pytest

from app.agent.planner import DeterministicPlanner
from app.agent.tool_set import TOOLS
from app.enums import AMLPattern, IntentType, ToolName
from app.interfaces import Planner
from app.schemas import DateRange, Filters, Understanding

T = ToolName


@pytest.fixture
def planner() -> DeterministicPlanner:
    return DeterministicPlanner()


def _tools(plan) -> list[ToolName]:
    return [step.tool for step in plan.steps]


# ── Golden plans: query → understanding → expected steps + skipped (AGENT_FLOW §3) ──

GOLDEN: dict[str, dict] = {
    "Find structuring patterns in the last 30 days": {
        "understanding": Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.STRUCTURING,
            filters=Filters(date_range=DateRange(last_days=30)),
            confidence=0.98,
        ),
        "expected": [
            T.DATA_LOADER,
            T.FILTER,
            T.FEATURE_ENGINEERING,
            T.AML_PATTERN_DETECTOR,
            T.RISK_CLASSIFIER,
            T.EXPLAINER,
            T.RECOMMENDER,
            T.VISUALIZER,
        ],
        "skipped": {T.EDA, T.ANOMALY_DETECTOR},
    },
    "Which customers made 10+ transactions under $10,000?": {
        "understanding": Understanding(
            intent=IntentType.THRESHOLD_RULE,
            aml_pattern=AMLPattern.STRUCTURING,
            confidence=0.95,
        ),
        "expected": [
            T.DATA_LOADER,
            T.FEATURE_ENGINEERING,
            T.AML_PATTERN_DETECTOR,
            T.RISK_CLASSIFIER,
            T.EXPLAINER,
            T.RECOMMENDER,
            T.VISUALIZER,
        ],
        "skipped": {T.EDA, T.ANOMALY_DETECTOR, T.FILTER},
    },
    "Is customer 4521 suspicious?": {
        "understanding": Understanding(
            intent=IntentType.SINGLE_ENTITY,
            entities=["4521"],
            confidence=0.9,
        ),
        "expected": [
            T.DATA_LOADER,
            T.FILTER,
            T.FEATURE_ENGINEERING,
            T.AML_PATTERN_DETECTOR,
            T.RISK_CLASSIFIER,
            T.EXPLAINER,
            T.RECOMMENDER,
            T.VISUALIZER,
        ],
        "skipped": {T.EDA, T.ANOMALY_DETECTOR},
    },
    "Analyse this dataset for suspicious activity": {
        "understanding": Understanding(
            intent=IntentType.EDA,
            aml_pattern=AMLPattern.NONE,
            needs_eda=True,
            confidence=0.85,
        ),
        "expected": [
            T.DATA_LOADER,
            T.EDA,
            T.FEATURE_ENGINEERING,
            T.AML_PATTERN_DETECTOR,
            T.ANOMALY_DETECTOR,
            T.RISK_CLASSIFIER,
            T.EXPLAINER,
            T.RECOMMENDER,
            T.VISUALIZER,
        ],
        "skipped": {T.FILTER},
    },
    "Flag high-risk customers in India using velocity": {
        "understanding": Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.RAPID_CASH_OUT,
            filters=Filters(country="IN"),
            confidence=0.92,
        ),
        "expected": [
            T.DATA_LOADER,
            T.FILTER,
            T.FEATURE_ENGINEERING,
            T.ANOMALY_DETECTOR,
            T.RISK_CLASSIFIER,
            T.EXPLAINER,
            T.RECOMMENDER,
            T.VISUALIZER,
        ],
        "skipped": {T.EDA, T.AML_PATTERN_DETECTOR},
    },
}


# ── contract / structural ───────────────────────────────────────────────────

def test_planner_implements_interface(planner: DeterministicPlanner) -> None:
    assert issubclass(DeterministicPlanner, Planner)
    assert isinstance(planner, Planner)


@pytest.mark.parametrize("query", list(GOLDEN))
def test_golden_plan(planner: DeterministicPlanner, query: str) -> None:
    """Each query yields exactly the expected ordered tools + skipped set."""
    spec = GOLDEN[query]
    plan = planner.build_plan(spec["understanding"])
    assert _tools(plan) == spec["expected"], query
    assert set(plan.skipped) == spec["skipped"], query


def test_every_planned_tool_is_runnable(planner: DeterministicPlanner) -> None:
    """Every tool the planner can emit exists in the runnable registry."""
    for spec in GOLDEN.values():
        for step in planner.build_plan(spec["understanding"]).steps:
            assert step.tool in TOOLS, step.tool


# ── the required query archetypes ───────────────────────────────────────────

def test_scalar_query_skips_analysis_and_visualizer(planner: DeterministicPlanner) -> None:
    """A pure aggregation (threshold + no pattern) returns a scalar: no detectors, no viz."""
    plan = planner.build_plan(
        Understanding(intent=IntentType.THRESHOLD_RULE, aml_pattern=AMLPattern.NONE)
    )
    tools = _tools(plan)
    assert tools == [T.DATA_LOADER, T.FEATURE_ENGINEERING]
    for absent in (
        T.EDA,
        T.AML_PATTERN_DETECTOR,
        T.ANOMALY_DETECTOR,
        T.RISK_CLASSIFIER,
        T.VISUALIZER,
    ):
        assert absent in plan.skipped
        assert absent not in tools


def test_anomaly_query_uses_anomaly_detector(planner: DeterministicPlanner) -> None:
    """A velocity / rapid-cash-out query routes to the AnomalyDetector, not the rules."""
    plan = planner.build_plan(
        Understanding(
            intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.RAPID_CASH_OUT
        )
    )
    tools = _tools(plan)
    assert T.ANOMALY_DETECTOR in tools
    assert T.AML_PATTERN_DETECTOR not in tools
    assert T.AML_PATTERN_DETECTOR in plan.skipped


def test_aml_rule_query_uses_rule_engine_not_anomaly(planner: DeterministicPlanner) -> None:
    """A structuring query routes to the rule engine and skips ML anomaly detection."""
    plan = planner.build_plan(
        Understanding(
            intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.STRUCTURING
        )
    )
    tools = _tools(plan)
    assert T.AML_PATTERN_DETECTOR in tools
    assert T.ANOMALY_DETECTOR not in tools
    assert T.ANOMALY_DETECTOR in plan.skipped
    # The AML step carries exactly the requested pattern in its inputs.
    aml_step = next(s for s in plan.steps if s.tool is T.AML_PATTERN_DETECTOR)
    assert aml_step.inputs == {"patterns": [AMLPattern.STRUCTURING.value]}


def test_visualization_included_for_detection_query(planner: DeterministicPlanner) -> None:
    """Any query with a detector produces charts for reviewer confidence."""
    plan = planner.build_plan(
        Understanding(
            intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.STRUCTURING
        )
    )
    assert T.VISUALIZER in _tools(plan)


# ── skipped-tool generation ─────────────────────────────────────────────────

def test_skipped_covers_all_unused_runnable_tools(planner: DeterministicPlanner) -> None:
    """steps ∪ skipped == the 10 runnable tools; the two are disjoint."""
    plan = planner.build_plan(
        Understanding(intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.STRUCTURING)
    )
    used = set(_tools(plan))
    skipped = set(plan.skipped)
    assert used.isdisjoint(skipped)
    assert used | skipped == set(TOOLS)  # exactly the 10 runnable tools
    # ResponseFormatter is never planned nor "skipped" — it is post-execution.
    assert T.RESPONSE_FORMATTER not in used
    assert T.RESPONSE_FORMATTER not in skipped


def test_filter_included_only_when_filters_or_entities_present(
    planner: DeterministicPlanner,
) -> None:
    with_filter = planner.build_plan(
        Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.STRUCTURING,
            filters=Filters(country="IN"),
        )
    )
    without_filter = planner.build_plan(
        Understanding(intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.STRUCTURING)
    )
    assert T.FILTER in _tools(with_filter)
    assert T.FILTER not in _tools(without_filter)
    assert T.FILTER in without_filter.skipped


def test_data_loader_is_always_first(planner: DeterministicPlanner) -> None:
    for spec in GOLDEN.values():
        plan = planner.build_plan(spec["understanding"])
        assert plan.steps[0].tool is T.DATA_LOADER


# ── invalid input ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [None, {"intent": "eda"}, "eda", 42])
def test_invalid_understanding_raises_type_error(
    planner: DeterministicPlanner, bad: object
) -> None:
    with pytest.raises(TypeError):
        planner.build_plan(bad)  # type: ignore[arg-type]


# ── determinism ─────────────────────────────────────────────────────────────

def test_same_input_same_plan(planner: DeterministicPlanner) -> None:
    """Same understanding → identical plan (fields and order), across repeated calls."""
    u = Understanding(
        intent=IntentType.DETECT_PATTERN,
        aml_pattern=AMLPattern.STRUCTURING,
        filters=Filters(date_range=DateRange(last_days=30)),
        confidence=0.98,
    )
    first = planner.build_plan(u)
    second = planner.build_plan(u)
    assert first.model_dump() == second.model_dump()


def test_determinism_across_instances() -> None:
    """Two independent planner instances produce identical plans for the same input."""
    u = Understanding(intent=IntentType.EDA, aml_pattern=AMLPattern.NONE)
    assert (
        DeterministicPlanner().build_plan(u).model_dump()
        == DeterministicPlanner().build_plan(u).model_dump()
    )


# ── confidence propagation (D12) ────────────────────────────────────────────

def test_confidence_reflects_understanding_for_qu_derived_steps(
    planner: DeterministicPlanner,
) -> None:
    """Filter / pattern-specific steps inherit the understanding confidence; purely
    structural steps use the deterministic 1.0."""
    plan = planner.build_plan(
        Understanding(
            intent=IntentType.DETECT_PATTERN,
            aml_pattern=AMLPattern.STRUCTURING,
            filters=Filters(country="IN"),
            confidence=0.7,
        )
    )
    by_tool = {s.tool: s for s in plan.steps}
    assert by_tool[T.FILTER].confidence == 0.7
    assert by_tool[T.AML_PATTERN_DETECTOR].confidence == 0.7
    assert by_tool[T.DATA_LOADER].confidence == 1.0
    assert by_tool[T.RISK_CLASSIFIER].confidence == 1.0
