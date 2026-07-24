"""Synthetic transaction generator (D15).

Produces a documented dataset with **planted, explainable AML cases** (known
structuring / smurfing customers) so the demo reliably finds real positives. The
schema, assumptions, and generation logic are the source for the README dataset
section (rules G5/G7).

Usage (later phase):
    python -m scripts.generate_synthetic --rows 100000 --out data/synthetic/transactions.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import SYNTHETIC_DATA_DIR, configure_logging

# Target schema (documented in README when the generator lands):
#   customer_id: str | txn_id: str | timestamp: datetime | amount: float
#   direction: "deposit" | "withdrawal" | "transfer"
#   counterparty_id: str | country: str | channel: str
SCHEMA_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "txn_id",
    "timestamp",
    "amount",
    "direction",
    "counterparty_id",
    "country",
    "channel",
)


def parse_args() -> argparse.Namespace:
    """CLI arguments for the generator."""
    parser = argparse.ArgumentParser(description="Generate synthetic AML transaction data.")
    parser.add_argument("--rows", type=int, default=100_000, help="Number of transactions.")
    parser.add_argument(
        "--out",
        type=Path,
        default=SYNTHETIC_DATA_DIR / "transactions.parquet",
        help="Output parquet path.",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (reproducible).")
    return parser.parse_args()


def main() -> None:
    """Entry point (scaffold)."""
    configure_logging()
    _args = parse_args()
    # TODO(Phase 0/2): generate a realistic base population, then inject planted
    # structuring/smurfing/rapid-cash-out cases with known ground truth; write
    # parquet to args.out. Document schema + assumptions in the README.
    raise NotImplementedError("generate_synthetic — implemented when the data layer lands")


if __name__ == "__main__":
    main()
