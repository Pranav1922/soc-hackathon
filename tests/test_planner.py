"""Golden-plan tests (D18) — the proof of the headline requirement.

Structural checks pass today; the query→plan assertions are scaffolded and skipped
until the deterministic planner is implemented (Phase 1/3). The expected mapping is
encoded now so the tests are ready to switch on.
"""

from __future__ import annotations

import pytest

from app.agent.planner import DeterministicPlanner
from app.agent.tool_set import TOOLS
from app.enums import ToolName
from app.interfaces import Planner

# Expected selective-invocation table (AGENT_FLOW.md §3 / D3). Switch these on in Phase 3.
GOLDEN_PLANS: dict[str, dict[str, list[ToolName]]] = {
    "Find structuring patterns in the last 30 days": {
        "expected": [
            ToolName.DATA_LOADER,
            ToolName.FILTER,
            ToolName.FEATURE_ENGINEERING,
            ToolName.AML_PATTERN_DETECTOR,
            ToolName.RISK_CLASSIFIER,
            ToolName.EXPLAINER,
            ToolName.RECOMMENDER,
            ToolName.VISUALIZER,
        ],
        "skipped": [ToolName.EDA, ToolName.ANOMALY_DETECTOR],
    },
    "Which customers made 10+ transactions under $10,000?": {
        "expected": [
            ToolName.DATA_LOADER,
            ToolName.FEATURE_ENGINEERING,
            ToolName.AML_PATTERN_DETECTOR,
            ToolName.RISK_CLASSIFIER,
            ToolName.EXPLAINER,
            ToolName.RECOMMENDER,
            ToolName.VISUALIZER,
        ],
        "skipped": [ToolName.EDA, ToolName.ANOMALY_DETECTOR, ToolName.FILTER],
    },
}


def test_planner_implements_interface() -> None:
    """The concrete planner satisfies the frozen Planner contract."""
    assert issubclass(DeterministicPlanner, Planner)
    assert isinstance(DeterministicPlanner(), Planner)


def test_every_expected_tool_is_runnable() -> None:
    """Every tool referenced by a golden plan is a real, runnable tool (except EDA/others always exist)."""
    for spec in GOLDEN_PLANS.values():
        for tool in spec["expected"]:
            assert tool in TOOLS, f"{tool} missing from the runnable registry"


@pytest.mark.skip(reason="TODO(Phase 3): DeterministicPlanner.build_plan not implemented yet")
@pytest.mark.parametrize("query", list(GOLDEN_PLANS))
def test_golden_plan(query: str) -> None:
    """Each query yields exactly the expected tools + skipped set (dynamic planning)."""
    plan = DeterministicPlanner().build_plan(understanding=...)
    assert [s.tool for s in plan.steps] == GOLDEN_PLANS[query]["expected"]
    assert set(plan.skipped) == set(GOLDEN_PLANS[query]["skipped"])
