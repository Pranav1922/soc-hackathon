"""Deterministic Planner — understanding → ExecutionPlan, no LLM (D1, D3).

A pure function of the :class:`Understanding`. Because it is deterministic, the plan
is fully testable (golden-plan tests) and identical on every run. It selects only
the tools a query needs and populates ``skipped`` for the ones it doesn't — the
visible proof that the system is not a fixed pipeline.

The exact selection rules are frozen in ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` D3.
"""

from __future__ import annotations

from app.config import PLANNER
from app.interfaces import Planner
from app.schemas import ExecutionPlan, Understanding


class DeterministicPlanner(Planner):
    """Maps intent / pattern / filters / entities to an ordered tool plan (D3)."""

    def __init__(self) -> None:
        self._config = PLANNER

    def build_plan(self, understanding: Understanding) -> ExecutionPlan:
        # TODO(Phase 1/3): implement the D3 rules:
        #   - DataLoader always first
        #   - Filter iff filters/entities present
        #   - EDA only when intent == EDA
        #   - FeatureEngineering only the families the pattern needs
        #   - AMLPatternDetector when a named pattern is present (or all for
        #     single_entity/eda)
        #   - AnomalyDetector when broad/unknown AND rows >= config.anomaly_min_rows
        #   - RiskClassifier + Explainer + Recommender whenever flags are produced
        #   - Visualizer unless the answer is a single scalar
        # Populate ExecutionStep.reason/confidence/inputs and skipped[].
        raise NotImplementedError("DeterministicPlanner.build_plan — Phase 1/3")
