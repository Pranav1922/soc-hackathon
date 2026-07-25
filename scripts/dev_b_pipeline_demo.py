"""Developer B end-to-end pipeline demo / integration proof.

Runs the five core modules built by Developer B back-to-back on a small,
hand-crafted synthetic dataset — proving they actually chain together
correctly, not just pass in isolation with hand-built fixtures:

    DataLoader -> AMLPatternDetector -> RiskClassifier -> Explainer
    -> Recommender -> Visualizer -> ResponseFormatter

Deliberately self-contained (writes its own tiny CSV) so it does not depend
on scripts/generate_synthetic.py, which is not implemented yet.

Run with:
    python scripts/dev_b_pipeline_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.enums import AMLPattern, IntentType
from app.response import ResponseFormatter
from app.schemas import (
    Context,
    ExecutionPlan,
    ExecutionStep,
    Understanding,
)
from app.tools.aml_patterns import AMLPatternDetector
from app.tools.data_loader import DataLoader
from app.tools.explainer import Explainer
from app.tools.recommender import Recommender
from app.tools.risk_classifier import RiskClassifier
from app.tools.visualizer import Visualizer


def _build_sample_dataset() -> pd.DataFrame:
    """A handful of customers engineered to trip each P0 typology, plus one
    clean customer as a negative control."""
    rows: list[dict] = []

    # C1: structuring — 3 cash deposits just under $10k within a week.
    for i, day in enumerate([1, 3, 5]):
        rows.append(
            {
                "customer_id": "C1",
                "txn_id": f"C1_T{i}",
                "timestamp": f"2023-06-{day:02d}T10:00:00",
                "amount": 9200.0,
                "direction": "deposit",
                "counterparty_id": "BRANCH_A",
                "country": "US",
                "channel": "branch",
            }
        )

    # C2: smurfing — 5 small deposits from 5 distinct sources within a week.
    for i in range(5):
        rows.append(
            {
                "customer_id": "C2",
                "txn_id": f"C2_T{i}",
                "timestamp": f"2023-06-{i + 1:02d}T09:00:00",
                "amount": 800.0,
                "direction": "deposit",
                "counterparty_id": f"SRC_{i}",
                "country": "GB",
                "channel": "online",
            }
        )

    # C3: rapid cash-out — big deposit, most of it withdrawn same day.
    rows.append(
        {
            "customer_id": "C3",
            "txn_id": "C3_DEP",
            "timestamp": "2023-06-10T09:00:00",
            "amount": 15000.0,
            "direction": "deposit",
            "counterparty_id": "WIRE_IN",
            "country": "US",
            "channel": "online",
        }
    )
    rows.append(
        {
            "customer_id": "C3",
            "txn_id": "C3_WD",
            "timestamp": "2023-06-10T18:00:00",
            "amount": 14000.0,
            "direction": "withdrawal",
            "counterparty_id": "ATM_1",
            "country": "US",
            "channel": "atm",
        }
    )

    # C4: clean control — ordinary, unremarkable activity.
    rows.append(
        {
            "customer_id": "C4",
            "txn_id": "C4_T0",
            "timestamp": "2023-06-15T12:00:00",
            "amount": 150.0,
            "direction": "deposit",
            "counterparty_id": "EMPLOYER",
            "country": "US",
            "channel": "online",
        }
    )

    return pd.DataFrame(rows)


def main() -> None:
    df = _build_sample_dataset()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample_transactions.csv"
        df.to_csv(path, index=False)

        print(f"=== Dev B pipeline demo — {len(df)} synthetic transactions ===\n")

        context = Context(query="Find suspicious activity in this dataset")
        context.understanding = Understanding(
            intent=IntentType.DETECT_PATTERN, aml_pattern=AMLPattern.NONE
        )

        # 1. DataLoader
        context, load_result, load_trace = DataLoader().run(context, {"path": path})
        context.trace.append(load_trace)
        print(f"[DataLoader]        {load_trace.status.value:8s} "
              f"rows_in={load_trace.rows_in} rows_out={load_trace.rows_out}")
        assert load_trace.status.value == "SUCCESS", load_result.message

        # 2. AMLPatternDetector
        context, aml_result, aml_trace = AMLPatternDetector().run(context, {})
        context.trace.append(aml_trace)
        print(f"[AMLPatternDetector] {aml_trace.status.value:8s} "
              f"hits={aml_result.output.get('hits', aml_result.output.get('hit_count', '?'))}")

        # 3. RiskClassifier
        context, risk_result, risk_trace = RiskClassifier().run(context, {})
        context.trace.append(risk_trace)
        print(f"[RiskClassifier]    {risk_trace.status.value:8s} "
              f"entities_scored={risk_result.output['entities_scored']} "
              f"bands={risk_result.output['band_counts']}")

        # 4. Explainer
        context, explain_result, explain_trace = Explainer().run(context, {})
        context.trace.append(explain_trace)
        print(f"[Explainer]         {explain_trace.status.value:8s} "
              f"explained={explain_result.output['explained']}")

        # 5. Recommender
        context, rec_result, rec_trace = Recommender().run(context, {})
        context.trace.append(rec_trace)
        print(f"[Recommender]       {rec_trace.status.value:8s} "
              f"actions={rec_result.output['action_counts']}")

        # 6. Visualizer
        context, viz_result, viz_trace = Visualizer().run(context, {})
        context.trace.append(viz_trace)
        print(f"[Visualizer]        {viz_trace.status.value:8s} "
              f"charts={viz_result.output['chart_types']}")

        # 7. ResponseFormatter (post-execution, not a plan step)
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(tool=load_result.tool, reason="always runs first", confidence=1.0),
                ExecutionStep(tool=aml_result.tool, reason="pattern detection requested", confidence=1.0),
                ExecutionStep(tool=risk_result.tool, reason="flags produced", confidence=1.0),
                ExecutionStep(tool=explain_result.tool, reason="flags produced", confidence=1.0),
                ExecutionStep(tool=rec_result.tool, reason="flags produced", confidence=1.0),
                ExecutionStep(tool=viz_result.tool, reason="non-scalar query", confidence=1.0),
            ],
            skipped=[],
        )
        response = ResponseFormatter().format(context, plan)

        print(f"\n=== Final flagged entities: {len(response.results)} ===")
        for flag in sorted(response.results, key=lambda f: f.score, reverse=True):
            print(f"\n  {flag.entity_id} — {flag.risk.value.upper()} (score={flag.score:.2f}, action={flag.action.value})")
            print(f"    {flag.explanation}")
            print(f"    escalation: {flag.evidence.get('escalation_reason', 'n/a')}")

        print(f"\n=== Charts produced: {len(response.charts)} ===")
        for chart in response.charts:
            print(f"  - {chart.type}: {chart.title}")

        print(f"\n=== Trace ({len(response.trace)} steps) ===")
        for entry in response.trace:
            print(f"  {entry.tool.value:20s} {entry.status.value:8s} "
                  f"in={entry.rows_in:4d} out={entry.rows_out:4d} {entry.duration_ms}ms")

        # Sanity assertions — this IS the integration proof.
        assert "C1" in {f.entity_id for f in response.results}, "structuring customer not flagged"
        assert "C2" in {f.entity_id for f in response.results}, "smurfing customer not flagged"
        assert "C3" in {f.entity_id for f in response.results}, "rapid cash-out customer not flagged"
        assert "C4" not in {f.entity_id for f in response.results}, "clean customer wrongly flagged"
        assert len(response.charts) >= 2, "expected at least the histogram + risk distribution charts"

        print("\n✅ All integration assertions passed — the 5-module chain works end-to-end.")


if __name__ == "__main__":
    main()
