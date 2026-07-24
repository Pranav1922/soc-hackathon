"""AML rule tests (D18). Config-contract checks pass now; rule-hit fixtures are
scaffolded and skipped until the rule engine lands (Phase 2)."""

from __future__ import annotations

import pytest

from app.config import AML, CTR_THRESHOLD


def test_structuring_thresholds_match_frozen_decision() -> None:
    """config must encode D6 structuring thresholds exactly (guards against drift)."""
    assert AML.structuring.min_count == 3
    assert AML.structuring.amount_min == 8_000.0
    assert AML.structuring.amount_max == 9_999.0
    assert AML.structuring.window_days == 7
    # Structuring amounts sit just under the CTR reporting line.
    assert AML.structuring.amount_max < CTR_THRESHOLD == 10_000.0


def test_smurfing_and_rapid_cash_out_thresholds() -> None:
    """config must encode D6 smurfing + rapid-cash-out thresholds exactly."""
    assert AML.smurfing.min_distinct_sources == 5
    assert AML.smurfing.max_amount == 3_000.0
    assert AML.rapid_cash_out.min_ratio == 0.90
    assert AML.rapid_cash_out.window_hours == 24


@pytest.mark.skip(reason="TODO(Phase 2): AMLPatternDetector not implemented yet")
def test_structuring_fixture_flags_planted_customer() -> None:
    """A crafted customer with 3 sub-$10k deposits in 7 days is flagged structuring."""
    # Phase 2: build fixture df -> AMLPatternDetector -> assert rule hit + evidence.
