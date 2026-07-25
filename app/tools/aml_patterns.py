"""AMLPatternDetector tool — deterministic typology rules (F3, C5, D6).

The **primary** detector and the source of the headline, auditable explanations.
Thresholds are frozen in ``app.config`` (D6): structuring, smurfing, rapid cash-out,
and (P2) layering. Each hit carries a machine-readable ``rule_id`` and the exact
triggering evidence for the Explainer.

Runs directly against ``context.working_df`` (the feature table / filtered df is
an equally valid input per the module spec; a full ``FeatureEngineering`` pass is
not a prerequisite for these particular rules — each rule computes the narrow
per-customer windowed aggregate it needs internally).

Cash proxy (undocumented in the frozen schema, so pinned here as an explicit
assumption): structuring and smurfing target *cash* transactions. The schema has
no ``is_cash`` flag, so ``direction == "deposit"`` is used as the cash proxy —
the classic structuring/smurfing typology is about cash entering the system as
sub-threshold deposits. If a future schema adds a real cash/channel flag, swap
the mask in :meth:`_cash_deposit_mask` only.
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from typing import Any

import pandas as pd

from app.config import AML
from app.enums import AMLPattern, ExecutionStatus, ToolName
from app.interfaces import Tool
from app.schemas import Context, ToolResult, TraceEntry

logger = logging.getLogger(__name__)

#: Every pattern this detector knows how to evaluate (params["patterns"] may narrow this).
_ALL_PATTERNS: tuple[AMLPattern, ...] = (
    AMLPattern.STRUCTURING,
    AMLPattern.SMURFING,
    AMLPattern.RAPID_CASH_OUT,
    AMLPattern.LAYERING,
)

#: Columns every rule needs present on ``working_df`` (mirrors DataLoader.REQUIRED_COLUMNS).
_REQUIRED_INPUT_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "txn_id",
    "timestamp",
    "amount",
    "direction",
    "counterparty_id",
)

#: Layering DFS depth cap — a safety valve so a dense transfer graph can't blow up
#: the search; min_hops (3) is always well under this.
_LAYERING_MAX_DEPTH = 6


class AMLPatternDetector(Tool):
    """Applies frozen AML rules and records rule hits + evidence on the context.

    Writes hits to ``context.artifacts["aml_hits"]`` (a flat list) and
    ``context.artifacts["aml_hits_by_customer"]`` (grouped), for the
    RiskClassifier and Explainer to consume. Never touches ``context.flags``
    directly — that's the RiskClassifier's job (rule hit -> banded RiskResult).
    """

    @property
    def name(self) -> ToolName:
        return ToolName.AML_PATTERN_DETECTOR

    def run(
        self,
        context: Context,
        params: dict[str, Any],
    ) -> tuple[Context, ToolResult, TraceEntry]:
        start = time.perf_counter()
        df = context.working_df
        rows_in = 0 if df is None else len(df)

        if df is not None and not df.empty:
            missing = [c for c in _REQUIRED_INPUT_COLUMNS if c not in df.columns]
            if missing:
                logger.error("AMLPatternDetector: working_df missing columns %s", missing)
                duration_ms = int((time.perf_counter() - start) * 1000)
                result = ToolResult(
                    tool=self.name,
                    output={},
                    message=f"working_df is missing required columns: {missing}",
                )
                trace = TraceEntry(
                    tool=self.name,
                    status=ExecutionStatus.ERROR,
                    rows_in=rows_in,
                    rows_out=0,
                    duration_ms=duration_ms,
                )
                return context, result, trace

        patterns = self._resolve_patterns(params)
        hits: list[dict[str, Any]] = []

        # Empty/None working_df is a first-class state (D11) — evaluate to zero
        # hits, never error.
        if df is not None and not df.empty:
            if AMLPattern.STRUCTURING in patterns:
                hits.extend(self._detect_structuring(df))
            if AMLPattern.SMURFING in patterns:
                hits.extend(self._detect_smurfing(df))
            if AMLPattern.RAPID_CASH_OUT in patterns:
                hits.extend(self._detect_rapid_cash_out(df))
            if AMLPattern.LAYERING in patterns:
                hits.extend(self._detect_layering(df))

        existing: list[dict[str, Any]] = context.artifacts.get("aml_hits", [])
        existing = [*existing, *hits]
        context.artifacts["aml_hits"] = existing
        context.artifacts["aml_hits_by_customer"] = self._group_by_entity(existing)

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "AMLPatternDetector: evaluated %s on %d row(s) -> %d hit(s)",
            [p.value for p in patterns],
            rows_in,
            len(hits),
        )

        result = ToolResult(
            tool=self.name,
            output={
                "patterns_evaluated": [p.value for p in patterns],
                "hit_count": len(hits),
                "hits": hits,
            },
        )
        trace = TraceEntry(
            tool=self.name,
            status=ExecutionStatus.SUCCESS,
            rows_in=rows_in,
            rows_out=len(hits),
            duration_ms=duration_ms,
        )
        return context, result, trace

    # ── pattern selection ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_patterns(params: dict[str, Any]) -> tuple[AMLPattern, ...]:
        """Which patterns to evaluate this run — ``params["patterns"]`` narrows,
        an absent/empty request runs the full rule set (D3: planner decides
        *whether* to call this tool at all; once called, default to everything)."""
        requested = params.get("patterns") or params.get("pattern")
        if not requested:
            return _ALL_PATTERNS
        if isinstance(requested, (AMLPattern, str)):
            requested = [requested]

        resolved: list[AMLPattern] = []
        for item in requested:
            pattern = item if isinstance(item, AMLPattern) else AMLPattern(item)
            if pattern is AMLPattern.NONE:
                continue
            resolved.append(pattern)
        return tuple(resolved) if resolved else _ALL_PATTERNS

    # ── rule: structuring ───────────────────────────────────────────────────

    @staticmethod
    def _cash_deposit_mask(df: pd.DataFrame) -> pd.Series:
        """Cash proxy — see module docstring for the ``direction == "deposit"`` rationale."""
        return df["direction"] == "deposit"

    def _detect_structuring(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """≥ min_count cash deposits of $8,000-$9,999 within a rolling 7-day window."""
        cfg = AML.structuring
        mask = (
            self._cash_deposit_mask(df)
            & (df["amount"] >= cfg.amount_min)
            & (df["amount"] <= cfg.amount_max)
        )
        candidates = df.loc[mask, ["customer_id", "txn_id", "timestamp", "amount"]]
        window = pd.Timedelta(days=cfg.window_days)

        hits: list[dict[str, Any]] = []
        for customer_id, grp in candidates.groupby("customer_id", sort=False):
            grp = grp.sort_values("timestamp").reset_index(drop=True)
            left = 0
            for right in range(len(grp)):
                t_right = grp["timestamp"].iloc[right]
                while grp["timestamp"].iloc[left] < t_right - window:
                    left += 1
                count = right - left + 1
                if count >= cfg.min_count:
                    window_rows = grp.iloc[left : right + 1]
                    hits.append(
                        self._make_hit(
                            pattern=AMLPattern.STRUCTURING,
                            entity_id=str(customer_id),
                            evidence={
                                "txn_ids": window_rows["txn_id"].tolist(),
                                "count": int(count),
                                "amount_min": cfg.amount_min,
                                "amount_max": cfg.amount_max,
                                "window_days": cfg.window_days,
                                "window_start": window_rows["timestamp"].min().isoformat(),
                                "window_end": window_rows["timestamp"].max().isoformat(),
                                "total_amount": float(window_rows["amount"].sum()),
                            },
                        )
                    )
                    break  # one hit is enough evidence per customer
        return hits

    # ── rule: smurfing ──────────────────────────────────────────────────────

    def _detect_smurfing(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """One account receiving <$3,000 deposits from >=5 distinct sources within 7 days."""
        cfg = AML.smurfing
        mask = self._cash_deposit_mask(df) & (df["amount"] < cfg.max_amount)
        candidates = df.loc[
            mask, ["customer_id", "txn_id", "timestamp", "amount", "counterparty_id"]
        ]
        window = pd.Timedelta(days=cfg.window_days)

        hits: list[dict[str, Any]] = []
        for customer_id, grp in candidates.groupby("customer_id", sort=False):
            grp = grp.sort_values("timestamp").reset_index(drop=True)
            left = 0
            source_counts: Counter[str] = Counter()
            for right in range(len(grp)):
                source_counts[str(grp["counterparty_id"].iloc[right])] += 1
                t_right = grp["timestamp"].iloc[right]
                while grp["timestamp"].iloc[left] < t_right - window:
                    cp = str(grp["counterparty_id"].iloc[left])
                    source_counts[cp] -= 1
                    if source_counts[cp] <= 0:
                        del source_counts[cp]
                    left += 1
                if len(source_counts) >= cfg.min_distinct_sources:
                    window_rows = grp.iloc[left : right + 1]
                    hits.append(
                        self._make_hit(
                            pattern=AMLPattern.SMURFING,
                            entity_id=str(customer_id),
                            evidence={
                                "txn_ids": window_rows["txn_id"].tolist(),
                                "distinct_sources": len(source_counts),
                                "source_ids": sorted(set(source_counts)),
                                "max_amount": cfg.max_amount,
                                "window_days": cfg.window_days,
                                "window_start": window_rows["timestamp"].min().isoformat(),
                                "window_end": window_rows["timestamp"].max().isoformat(),
                                "total_amount": float(window_rows["amount"].sum()),
                            },
                        )
                    )
                    break
        return hits

    # ── rule: rapid cash-out ────────────────────────────────────────────────

    def _detect_rapid_cash_out(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """A withdrawal >= 90% of a deposit, within 24h of that deposit, same customer."""
        cfg = AML.rapid_cash_out
        window = pd.Timedelta(hours=cfg.window_hours)
        cols = ["customer_id", "txn_id", "timestamp", "amount", "direction"]

        hits: list[dict[str, Any]] = []
        for customer_id, grp in df[cols].groupby("customer_id", sort=False):
            deposits = grp.loc[grp["direction"] == "deposit"].sort_values("timestamp")
            withdrawals = grp.loc[grp["direction"] == "withdrawal"].sort_values("timestamp")
            if deposits.empty or withdrawals.empty:
                continue

            match: tuple[pd.Series, pd.Series] | None = None
            for _, dep in deposits.iterrows():
                candidate_mask = (withdrawals["timestamp"] > dep["timestamp"]) & (
                    withdrawals["timestamp"] <= dep["timestamp"] + window
                )
                candidates = withdrawals.loc[candidate_mask]
                if candidates.empty:
                    continue
                qualifying = candidates.loc[candidates["amount"] >= cfg.min_ratio * dep["amount"]]
                if not qualifying.empty:
                    match = (dep, qualifying.iloc[0])
                    break

            if match is None:
                continue
            dep, wd = match
            ratio = float(wd["amount"] / dep["amount"]) if dep["amount"] else 0.0
            hits.append(
                self._make_hit(
                    pattern=AMLPattern.RAPID_CASH_OUT,
                    entity_id=str(customer_id),
                    evidence={
                        "deposit_txn_id": dep["txn_id"],
                        "withdrawal_txn_id": wd["txn_id"],
                        "deposit_amount": float(dep["amount"]),
                        "withdrawal_amount": float(wd["amount"]),
                        "ratio": ratio,
                        "min_ratio": cfg.min_ratio,
                        "window_hours": cfg.window_hours,
                        "deposit_time": dep["timestamp"].isoformat(),
                        "withdrawal_time": wd["timestamp"].isoformat(),
                    },
                )
            )
        return hits

    # ── rule: layering (P2) ─────────────────────────────────────────────────

    def _detect_layering(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """>= min_hops chained transfers draining an account within 72h.

        Best-effort P2 rule: DFS over the transfer graph (customer_id ->
        counterparty_id edges), requiring strictly increasing timestamps (money
        must actually move forward hop to hop), no revisited node (cycle guard),
        and the whole chain fitting inside the window measured from the first
        hop. Depth is capped (_LAYERING_MAX_DEPTH) as a safety valve on dense
        graphs; one chain (first found) is reported per starting customer.
        """
        cfg = AML.layering
        mask = df["direction"] == "transfer"
        edges_df = df.loc[
            mask, ["customer_id", "counterparty_id", "txn_id", "timestamp", "amount"]
        ].sort_values("timestamp")
        if edges_df.empty:
            return []

        window = pd.Timedelta(hours=cfg.window_hours)
        edges_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in edges_df.itertuples(index=False):
            edges_by_source[str(row.customer_id)].append(
                {
                    "to": row.counterparty_id,
                    "txn_id": row.txn_id,
                    "timestamp": row.timestamp,
                    "amount": row.amount,
                }
            )
        for src_edges in edges_by_source.values():
            src_edges.sort(key=lambda e: e["timestamp"])

        def dfs(
            path_edges: list[dict[str, Any]], path_nodes: list[str]
        ) -> list[dict[str, Any]] | None:
            if (
                len(path_edges) >= cfg.min_hops
                and path_edges[-1]["timestamp"] - path_edges[0]["timestamp"] <= window
            ):
                return list(path_edges)
            if len(path_edges) >= _LAYERING_MAX_DEPTH:
                return None
            current = path_nodes[-1]
            for edge in edges_by_source.get(current, []):
                if edge["to"] in path_nodes:
                    continue  # cycle guard
                if path_edges and edge["timestamp"] <= path_edges[-1]["timestamp"]:
                    continue  # must move strictly forward in time
                if path_edges and edge["timestamp"] - path_edges[0]["timestamp"] > window:
                    continue
                found = dfs([*path_edges, edge], [*path_nodes, edge["to"]])
                if found:
                    return found
            return None

        hits: list[dict[str, Any]] = []
        seen_starts: set[str] = set()
        for start_customer in edges_by_source:
            if start_customer in seen_starts:
                continue
            chain = dfs([], [start_customer])
            if not chain:
                continue
            seen_starts.add(start_customer)
            hits.append(
                self._make_hit(
                    pattern=AMLPattern.LAYERING,
                    entity_id=str(start_customer),
                    evidence={
                        "txn_ids": [e["txn_id"] for e in chain],
                        "hops": len(chain),
                        "chain": [start_customer, *[e["to"] for e in chain]],
                        "min_hops": cfg.min_hops,
                        "window_hours": cfg.window_hours,
                        "start_time": chain[0]["timestamp"].isoformat(),
                        "end_time": chain[-1]["timestamp"].isoformat(),
                        "first_hop_amount": float(chain[0]["amount"]),
                    },
                )
            )
        return hits

    # ── shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_hit(pattern: AMLPattern, entity_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "pattern": pattern,
            "rule_id": pattern.value,
            "entity_id": entity_id,
            "entity_type": "customer",
            "evidence": evidence,
        }

    @staticmethod
    def _group_by_entity(hits: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for hit in hits:
            grouped[hit["entity_id"]].append(hit)
        return dict(grouped)
