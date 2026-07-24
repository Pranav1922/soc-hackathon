"""Feature-engineering tests (D18). Scaffolded and skipped until the FE tool lands
(Phase 2). The risk-scoring config contract is checked now."""

from __future__ import annotations

import pytest

from app.config import RISK, RULE_SEVERITY_LEVELS


def test_risk_formula_constants_match_frozen_decision() -> None:
    """config must encode the D7 risk weights + bands exactly."""
    assert RISK.rule_weight == 0.6
    assert RISK.anomaly_weight == 0.4
    assert RISK.high_band == 0.75
    assert RISK.medium_band == 0.45
    assert RULE_SEVERITY_LEVELS == (0.0, 0.5, 0.8, 1.0)


@pytest.mark.skip(reason="TODO(Phase 2): FeatureEngineering not implemented yet")
def test_rolling_sum_and_velocity_correctness() -> None:
    """Rolling 7-day sums / velocity / z-score match hand-computed values."""
    # Phase 2: craft a small df with known windows and assert exact features.
