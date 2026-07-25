"""AMLPatternDetector tool — deterministic typology rules (F3, C5, D6).

The **primary** detector and the source of the headline, auditable evidence.
Thresholds are frozen in :data:`app.config.AML` (D6). This tool evaluates only the
deterministic AML rule families the architecture specifies:

    * ``structuring``     — ≥ N deposits in the sub-threshold band within a rolling
                            window, per customer (D6 structuring).
    * ``smurfing``        — one account fed by small deposits from ≥ K distinct
                            sources within a window (D6 smurfing).
    * ``rapid_cash_out``  — a withdrawal ≥ ratio·deposit within Δt of that deposit
                            (D6 rapid cash-out).

``layering`` is P2 (IMPLEMENTATION_PLAN Phase 2: "layering = P2"); when requested it
is skipped (logged), never partially invented.

Each hit is a machine-readable dict carrying ``rule_id`` + triggering evidence
(txn ids, values) for the RiskClassifier and Explainer. Hits are stored in
``context.artifacts["rule_hits"]`` — the schema's scratch space for intermediate
tool artifacts (there is no dedicated rule-hit field, and this tool must not invent
one). It never scores risk, explains, recommends, engineers features, or runs ML.

Reads:  ``context.working_df`` (falls back to ``context.raw_df``); ``params["patterns"]``.
Writes: ``context.artifacts["rule_hits"]``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from app.config import AML
from app.enums import AMLPattern, ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

RuleHit = dict[str, Any]

# Machine-readable rule identifiers (consumed by the Explainer downstream).
_RULE_ID: dict[str, str] = {
    AMLPattern.STRUCTURING.value: "structuring_sub_threshold_clustering",
    AMLPattern.SMURFING.value: "smurfing_multi_source_deposits",
    AMLPattern.RAPID_CASH_OUT.value: "rapid_cash_out_deposit_withdrawal",
}

# P0 deterministic rule families, in canonical (deterministic) evaluation order.
_P0_PATTERNS: tuple[str, ...] = (
    AMLPattern.STRUCTURING.value,
    AMLPattern.SMURFING.value,
    AMLPattern.RAPID_CASH_OUT.value,
)

# Columns each rule needs (beyond ``customer_id``, always required).
_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    AMLPattern.STRUCTURING.value: ("txn_id", "timestamp", "amount", "direction"),
    AMLPattern.SMURFING.value: (
        "txn_id",
        "timestamp",
        "amount",
        "direction",
        "counterparty_id",
    ),
    AMLPattern.RAPID_CASH_OUT.value: ("txn_id", "timestamp", "amount", "direction"),
}

_DEPOSIT = "deposit"
_WITHDRAWAL = "withdrawal"
_CUSTOMER = "customer_id"


class AMLPatternDetector(Tool):
    """Applies frozen AML rules and records rule hits + evidence on the context."""

    @property
    def name(self) -> ToolName:
        return ToolName.AML_PATTERN_DETECTOR

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        """Evaluate the requested AML rule sets over the current working subset.

        Args:
            context: Shared state; reads ``working_df`` (or ``raw_df``) and writes
                ``artifacts["rule_hits"]``.
            params: May include ``"patterns"`` — the pattern names to evaluate.
                When absent/empty, all P0 rules are evaluated.

        Returns:
            The mutated context, a :class:`ToolResult` with hit stats, and a
            :class:`TraceEntry`. A tool-level failure is reported as an ``ERROR``
            trace, never raised (the executor records it and continues).
        """
        start = time.perf_counter()
        df = self._source_frame(context)
        requested = self._resolve_patterns(params)

        try:
            hits, evaluated, skipped = self._detect(df, requested)
        except Exception as exc:  # noqa: BLE001 - never corrupt/crash; report via trace
            logger.error("AMLPatternDetector failed: %s: %s", type(exc).__name__, exc)
            return context, *self._error(exc, rows_in=len(df), start=start)

        context.artifacts["rule_hits"] = hits

        by_pattern = {p: sum(h["pattern"] == p for h in hits) for p in evaluated}
        logger.info(
            "AMLPatternDetector: rows_in=%d hits=%d evaluated=%s skipped=%s",
            len(df),
            len(hits),
            evaluated,
            skipped,
        )
        result = ToolResult(
            tool=self.name,
            output={
                "n_hits": len(hits),
                "patterns_evaluated": evaluated,
                "patterns_skipped": skipped,
                "hits_by_pattern": by_pattern,
            },
            message=None if hits else "no rule hits",
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=len(df),
            rows_out=len(hits),
            duration_ms=_elapsed_ms(start),
        )
        return context, result, trace

    # ── inputs ────────────────────────────────────────────────────────────────

    @staticmethod
    def _source_frame(context: Context) -> pd.DataFrame:
        """The subset to detect over: ``working_df`` if present, else ``raw_df``.

        Rules need transaction-level rows (for txn-id evidence); the per-customer
        ``context.features`` table is not sufficient, so detection reads the frame.
        Returns an empty DataFrame when neither is present (first-class empty, D11).
        """
        if context.working_df is not None:
            return context.working_df
        if context.raw_df is not None:
            return context.raw_df
        logger.warning("AMLPatternDetector: no dataframe in context; no rule hits")
        return pd.DataFrame()

    @staticmethod
    def _resolve_patterns(params: dict[str, Any]) -> list[str]:
        """Requested pattern names; absent/empty/invalid means all P0 rules."""
        raw = params.get("patterns")
        if not isinstance(raw, (list, tuple)) or not raw:
            return list(_P0_PATTERNS)
        return [str(p) for p in raw]

    # ── detection dispatch ────────────────────────────────────────────────────

    def _detect(
        self, df: pd.DataFrame, requested: list[str]
    ) -> tuple[list[RuleHit], list[str], list[str]]:
        """Run the requested P0 rules; return (hits, evaluated, skipped)."""
        if df.empty:
            return [], [], []
        if _CUSTOMER not in df.columns:
            raise ValueError(f"required column {_CUSTOMER!r} is missing")

        rules: dict[str, Callable[[pd.DataFrame], list[RuleHit]]] = {
            AMLPattern.STRUCTURING.value: self._detect_structuring,
            AMLPattern.SMURFING.value: self._detect_smurfing,
            AMLPattern.RAPID_CASH_OUT.value: self._detect_rapid_cash_out,
        }

        hits: list[RuleHit] = []
        evaluated: list[str] = []
        skipped: list[str] = []
        for pattern in _P0_PATTERNS:
            if pattern not in requested:
                continue
            missing = [c for c in _REQUIRED_COLUMNS[pattern] if c not in df.columns]
            if missing:
                logger.warning(
                    "AMLPatternDetector: skip %s (missing columns %s)", pattern, missing
                )
                skipped.append(pattern)
                continue
            hits.extend(rules[pattern](df))
            evaluated.append(pattern)

        # Requested patterns that are not P0 rules (e.g. layering=P2, or unknown).
        for pattern in requested:
            if pattern not in _P0_PATTERNS and pattern not in skipped:
                logger.info(
                    "AMLPatternDetector: skip pattern %s (not a P0 rule)", pattern
                )
                skipped.append(pattern)
        return hits, evaluated, skipped

    # ── individual rules (deterministic, config-driven) ───────────────────────

    def _detect_structuring(self, df: pd.DataFrame) -> list[RuleHit]:
        """≥ min_count deposits in the sub-threshold band within a rolling window."""
        cfg = AML.structuring
        window = pd.Timedelta(days=cfg.window_days).to_timedelta64()
        band = (df["direction"] == _DEPOSIT) & df["amount"].between(
            cfg.amount_min, cfg.amount_max
        )
        qualifying = df.loc[band, [_CUSTOMER, "txn_id", "timestamp", "amount"]]

        hits: list[RuleHit] = []
        for customer, sub in qualifying.groupby(_CUSTOMER, sort=True):
            sub = sub.sort_values("timestamp").reset_index(drop=True)
            if len(sub) < cfg.min_count:
                continue
            times = sub["timestamp"].to_numpy()
            best: tuple[int, int, int] | None = None  # (count, left, right)
            left = 0
            for right in range(len(times)):
                while times[right] - times[left] > window:
                    left += 1
                count = right - left + 1
                if count >= cfg.min_count and (best is None or count > best[0]):
                    best = (count, left, right)
            if best is not None:
                _, left_i, right_i = best
                window_txns = sub.iloc[left_i : right_i + 1]
                hits.append(
                    self._hit(
                        customer,
                        AMLPattern.STRUCTURING,
                        {
                            "txn_ids": window_txns["txn_id"].tolist(),
                            "count": int(best[0]),
                            "amount_min": float(window_txns["amount"].min()),
                            "amount_max": float(window_txns["amount"].max()),
                            "window_days": cfg.window_days,
                            "window_start": str(window_txns["timestamp"].iloc[0]),
                            "window_end": str(window_txns["timestamp"].iloc[-1]),
                            "ctr_threshold": AML.ctr_threshold,
                        },
                    )
                )
        return hits

    def _detect_smurfing(self, df: pd.DataFrame) -> list[RuleHit]:
        """One account fed by small deposits from ≥ K distinct sources in a window."""
        cfg = AML.smurfing
        window = pd.Timedelta(days=cfg.window_days).to_timedelta64()
        small = (df["direction"] == _DEPOSIT) & (df["amount"] < cfg.max_amount)
        qualifying = df.loc[
            small, [_CUSTOMER, "txn_id", "timestamp", "amount", "counterparty_id"]
        ]

        hits: list[RuleHit] = []
        for customer, sub in qualifying.groupby(_CUSTOMER, sort=True):
            sub = sub.sort_values("timestamp").reset_index(drop=True)
            times = sub["timestamp"].to_numpy()
            n = len(sub)
            best: tuple[int, int, int] | None = None  # (distinct, start, end)
            for i in range(n):
                sources: set[Any] = set()
                end = i
                j = i
                while j < n and times[j] - times[i] <= window:
                    sources.add(sub["counterparty_id"].iloc[j])
                    end = j
                    j += 1
                distinct = len(sources)
                if distinct >= cfg.min_distinct_sources and (
                    best is None or distinct > best[0]
                ):
                    best = (distinct, i, end)
            if best is not None:
                distinct, start_i, end_i = best
                window_txns = sub.iloc[start_i : end_i + 1]
                hits.append(
                    self._hit(
                        customer,
                        AMLPattern.SMURFING,
                        {
                            "txn_ids": window_txns["txn_id"].tolist(),
                            "distinct_sources": distinct,
                            "sources": sorted(
                                window_txns["counterparty_id"].unique().tolist()
                            ),
                            "window_days": cfg.window_days,
                            "window_start": str(window_txns["timestamp"].iloc[0]),
                            "window_end": str(window_txns["timestamp"].iloc[-1]),
                            "max_amount": cfg.max_amount,
                        },
                    )
                )
        return hits

    def _detect_rapid_cash_out(self, df: pd.DataFrame) -> list[RuleHit]:
        """A withdrawal ≥ ratio·deposit within Δt of that deposit, per customer."""
        cfg = AML.rapid_cash_out
        window = pd.Timedelta(hours=cfg.window_hours)
        cols = [_CUSTOMER, "txn_id", "timestamp", "amount", "direction"]

        hits: list[RuleHit] = []
        for customer, sub in df[cols].groupby(_CUSTOMER, sort=True):
            sub = sub.sort_values("timestamp")
            deposits = sub[sub["direction"] == _DEPOSIT]
            withdrawals = sub[sub["direction"] == _WITHDRAWAL]
            if deposits.empty or withdrawals.empty:
                continue
            for _, dep in deposits.iterrows():
                dep_amount = dep["amount"]
                if pd.isna(dep_amount) or dep_amount <= 0:
                    continue
                dep_ts = dep["timestamp"]
                candidates = withdrawals[
                    (withdrawals["timestamp"] >= dep_ts)
                    & (withdrawals["timestamp"] <= dep_ts + window)
                    & (withdrawals["amount"] >= cfg.min_ratio * dep_amount)
                ]
                if candidates.empty:
                    continue
                wd = candidates.iloc[0]
                hits.append(
                    self._hit(
                        customer,
                        AMLPattern.RAPID_CASH_OUT,
                        {
                            "deposit_txn_id": dep["txn_id"],
                            "withdrawal_txn_id": wd["txn_id"],
                            "deposit_amount": float(dep_amount),
                            "withdrawal_amount": float(wd["amount"]),
                            "ratio": round(float(wd["amount"]) / float(dep_amount), 4),
                            "hours_between": round(
                                (wd["timestamp"] - dep_ts).total_seconds() / 3600.0, 2
                            ),
                            "window_hours": cfg.window_hours,
                        },
                    )
                )
                break  # earliest qualifying deposit is enough to flag the customer
        return hits

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hit(entity_id: Any, pattern: AMLPattern, evidence: dict[str, Any]) -> RuleHit:
        """Build a machine-readable rule-hit record."""
        return {
            "entity_id": str(entity_id),
            "entity_type": "customer",
            "pattern": pattern.value,
            "rule_id": _RULE_ID[pattern.value],
            "evidence": evidence,
        }

    def _error(
        self, exc: Exception, rows_in: int, start: float
    ) -> tuple[ToolResult, TraceEntry]:
        """Build the (ToolResult, TraceEntry) pair for a tool-level failure."""
        result = ToolResult(tool=self.name, output={}, message=str(exc))
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.ERROR,
            rows_in=rows_in,
            rows_out=0,
            duration_ms=_elapsed_ms(start),
        )
        return result, trace


def _elapsed_ms(start: float) -> int:
    """Whole milliseconds elapsed since ``start`` (``perf_counter`` reference)."""
    return int((time.perf_counter() - start) * 1000)
