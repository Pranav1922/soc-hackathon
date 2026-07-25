"""Risk-scoring config-contract guard (D7).

Guards the frozen D7 risk weights/bands against drift. FeatureEngineering behaviour
is covered by ``tests/test_feature_engineering.py``.
"""

from __future__ import annotations

from app.config import RISK, RULE_SEVERITY_LEVELS


def test_risk_formula_constants_match_frozen_decision() -> None:
    """config must encode the D7 risk weights + bands exactly."""
    assert RISK.rule_weight == 0.6
    assert RISK.anomaly_weight == 0.4
    assert RISK.high_band == 0.75
    assert RISK.medium_band == 0.45
    assert RULE_SEVERITY_LEVELS == (0.0, 0.5, 0.8, 1.0)
