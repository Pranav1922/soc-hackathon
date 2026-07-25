"""AML config-contract guards (D18/D6).

Guards the frozen D6 thresholds against drift. The AML detector's *behaviour* is
covered by ``tests/test_aml_patterns.py`` (the canonical detector after the Dev-B
integration); the earlier behaviour tests here asserted the retired ``rule_hits``
artifact contract and were removed during that integration.
"""

from __future__ import annotations

from app.config import AML, CTR_THRESHOLD


def test_structuring_thresholds_match_frozen_decision() -> None:
    assert AML.structuring.min_count == 3
    assert AML.structuring.amount_min == 8_000.0
    assert AML.structuring.amount_max == 9_999.0
    assert AML.structuring.window_days == 7
    assert AML.structuring.amount_max < CTR_THRESHOLD == 10_000.0


def test_smurfing_and_rapid_cash_out_thresholds() -> None:
    assert AML.smurfing.min_distinct_sources == 5
    assert AML.smurfing.max_amount == 3_000.0
    assert AML.rapid_cash_out.min_ratio == 0.90
    assert AML.rapid_cash_out.window_hours == 24
