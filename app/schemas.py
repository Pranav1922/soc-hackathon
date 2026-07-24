"""Shared Pydantic models — the frozen data contracts.

Every model that crosses a module boundary is defined **exactly once, here**, and
imported elsewhere. This is the single source of truth for the request/response
contract (D12), the agent's internal ``Context``, and the planned-vs-actual
execution split (``ExecutionStep`` vs ``TraceEntry``).

Frozen by ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` (D2, D7, D11, D12).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    AMLPattern,
    EscalationAction,
    ExecutionStatus,
    IntentType,
    RiskLevel,
    ToolName,
)

# ─────────────────────────────────────────────────────────────────────────────
# Query Understanding (output of the single LLM call — D2)
# ─────────────────────────────────────────────────────────────────────────────


class DateRange(BaseModel):
    """A resolved or relative date filter.

    ``last_days`` is relative and is resolved against the **dataset's max
    timestamp**, never ``today`` (D10). ``start``/``end`` are absolute bounds.
    """

    last_days: int | None = Field(default=None, ge=0)
    start: date | None = None
    end: date | None = None


class Filters(BaseModel):
    """Structured filters extracted from the query (Requirement A5).

    All optional — a query may specify any subset (or none). Absent fields mean
    "no constraint on this dimension".
    """

    date_range: DateRange | None = None
    country: str | None = None
    segment: str | None = None
    transaction_type: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None


class Understanding(BaseModel):
    """Structured interpretation of the user query (D2).

    Produced either by the LLM (primary) or the keyword-extractor fallback. This is
    the *only* consumer-facing product of the LLM on the critical path; everything
    downstream is deterministic.
    """

    intent: IntentType
    entities: list[str] = Field(default_factory=list)
    filters: Filters = Field(default_factory=Filters)
    aml_pattern: AMLPattern = AMLPattern.NONE
    needs_eda: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Execution: PLANNED (ExecutionStep / ExecutionPlan) vs ACTUAL (TraceEntry)
# These are two SEPARATE concepts and must never be merged (D12).
# ─────────────────────────────────────────────────────────────────────────────


class ExecutionStep(BaseModel):
    """A single **planned** step: what the planner decided and why (D12).

    Not a runtime record — see :class:`TraceEntry` for what actually happened.
    """

    tool: ToolName
    #: Human-readable justification for selecting this tool.
    reason: str
    #: Planner confidence in this selection (1.0 for deterministic rules; may
    #: reflect the Understanding confidence for QU-derived decisions).
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    #: Exact parameters that will be passed to the tool — for debugging / UI
    #: visualization only. **Not** execution output.
    inputs: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """The ordered set of steps the executor will run, plus the tools skipped (D3).

    ``skipped`` is populated deliberately — it is the visible proof that the agent
    invokes only the tools a given query needs (not a fixed pipeline).
    """

    steps: list[ExecutionStep] = Field(default_factory=list)
    skipped: list[ToolName] = Field(default_factory=list)


class TraceEntry(BaseModel):
    """A single **actual** runtime record for a tool that ran (D12).

    Runtime information only — never planning fields. Pairs with, but is distinct
    from, :class:`ExecutionStep`.
    """

    tool: ToolName
    status: ExecutionStatus
    rows_in: int = 0
    rows_out: int = 0
    duration_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Tool results & risk findings
# ─────────────────────────────────────────────────────────────────────────────


class ToolResult(BaseModel):
    """Generic result payload returned by a tool alongside the threaded context.

    Kept intentionally loose (``output`` is a free dict) so each tool can return its
    own shape; strongly-typed, cross-cutting outputs (e.g. flags) use
    :class:`RiskResult` instead.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool: ToolName
    output: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class RiskResult(BaseModel):
    """A single flagged transaction or customer (an item in ``results[]``, D12).

    Carries everything a reviewer needs: the risk band, the deterministic score, an
    evidence-grounded explanation, the escalation action, and the raw evidence.
    """

    entity_id: str
    #: "customer" or "transaction" (per Requirement D1 — flag per transaction/customer).
    entity_type: str = "customer"
    risk: RiskLevel
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    action: EscalationAction
    #: Machine-readable evidence (triggering txn ids, rule id, feature values).
    evidence: dict[str, Any] = Field(default_factory=dict)


class ChartSpec(BaseModel):
    """A visualization spec for the UI (Plotly figure description).

    ``spec`` holds the serializable figure/data; the UI renders it. Kept generic so
    the Visualizer can emit timelines, histograms, bars, etc.
    """

    type: str
    title: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Agent context — mutable state threaded through the executor
# ─────────────────────────────────────────────────────────────────────────────


class Context(BaseModel):
    """Shared, mutable state passed between tools during execution.

    The executor threads one ``Context`` through every planned step. Tools read the
    fields they need and write their outputs back. DataFrame fields require
    ``arbitrary_types_allowed`` (pandas is not a Pydantic-native type).

    Empty subsets are a first-class state (D11): ``working_df`` may legitimately be
    an empty DataFrame, and every tool must handle that without erroring.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str
    understanding: Understanding | None = None

    #: Full cleaned dataset (loaded + cleaned once at startup — D5, D10).
    raw_df: pd.DataFrame | None = None
    #: Current working subset after filtering (may be empty — D11).
    working_df: pd.DataFrame | None = None
    #: Engineered AML features for the working subset.
    features: pd.DataFrame | None = None

    #: Column name -> dtype string, for the LLM prompt and Filter/FE tools.
    schema_map: dict[str, str] = Field(default_factory=dict)
    #: Max timestamp in the dataset, for resolving relative dates (D10).
    dataset_max_timestamp: datetime | None = None

    #: Accumulated flagged entities produced by detectors/classifier.
    flags: list[RiskResult] = Field(default_factory=list)
    #: Charts produced by the Visualizer / EDA tools.
    charts: list[ChartSpec] = Field(default_factory=list)
    #: Runtime trace, appended to by the executor as each step runs.
    trace: list[TraceEntry] = Field(default_factory=list)
    #: Free scratch space for intermediate tool artifacts (e.g. EDA stats,
    #: anomaly scores) that don't warrant a dedicated field.
    artifacts: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# API request / response (the frozen response contract — D12)
# ─────────────────────────────────────────────────────────────────────────────


class APIRequest(BaseModel):
    """Inbound analysis request (UI in-process call or optional FastAPI ``/analyze``)."""

    query: str
    #: Optional id of a flagship example query that ships with pre-parsed
    #: understanding, so it runs with the LLM fully offline (D14).
    example_id: str | None = None


class APIResponse(BaseModel):
    """The single structured response object returned to the UI/judge (D12).

    Shape: ``{query, understanding, plan[], skipped[], results[], charts[], trace[]}``.
    The ``plan`` + ``skipped`` + ``trace`` fields are the deliverable "what the agent
    decided and why".
    """

    query: str
    understanding: Understanding | None = None
    plan: list[ExecutionStep] = Field(default_factory=list)
    skipped: list[ToolName] = Field(default_factory=list)
    results: list[RiskResult] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    trace: list[TraceEntry] = Field(default_factory=list)
