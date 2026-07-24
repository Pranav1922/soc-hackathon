"""Shared enumerations — the single source of truth for categorical values.

Every enum in the system is defined **exactly once, here**. Other modules import
these; they never redefine them. All enums subclass ``str`` so they serialize
cleanly to/from JSON (Pydantic, API responses, LLM output).

Frozen by ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` (D2, D4, D5, D12).
"""

from __future__ import annotations

from enum import Enum


class ToolName(str, Enum):
    """Every tool the system knows about (D5 — final tool inventory).

    The Planner may emit any of these **except** :attr:`RESPONSE_FORMATTER`, which
    is invoked *after* execution to assemble the final response and is therefore
    never selected as a plan step (see D3). It is included in the inventory (D5)
    so the enum remains the single source of truth for tool identity.

    String values are the canonical CamelCase names used across the docs, the
    ``plan[]``/``trace[]`` contracts, and the golden-plan tests.
    """

    DATA_LOADER = "DataLoader"
    FILTER = "Filter"
    EDA = "EDA"
    FEATURE_ENGINEERING = "FeatureEngineering"
    AML_PATTERN_DETECTOR = "AMLPatternDetector"
    ANOMALY_DETECTOR = "AnomalyDetector"
    RISK_CLASSIFIER = "RiskClassifier"
    EXPLAINER = "Explainer"
    RECOMMENDER = "Recommender"
    VISUALIZER = "Visualizer"
    RESPONSE_FORMATTER = "ResponseFormatter"  # post-execution only; never planned (D3)


class IntentType(str, Enum):
    """High-level query intent extracted by Query Understanding (D2)."""

    EDA = "eda"
    DETECT_PATTERN = "detect_pattern"
    THRESHOLD_RULE = "threshold_rule"
    SINGLE_ENTITY = "single_entity"
    COMPARE = "compare"


class AMLPattern(str, Enum):
    """Target money-laundering typology (D2, D6)."""

    STRUCTURING = "structuring"
    SMURFING = "smurfing"
    LAYERING = "layering"
    RAPID_CASH_OUT = "rapid_cash_out"
    NONE = "none"


class RiskLevel(str, Enum):
    """Risk band produced by the Risk Classifier (D7)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EscalationAction(str, Enum):
    """Recommended next action for a flagged entity (Recommender).

    Maps from :class:`RiskLevel`: low → monitor, medium → review, high → report.
    """

    MONITOR = "monitor"
    REVIEW = "review"
    REPORT = "report"


class ExecutionStatus(str, Enum):
    """Runtime outcome of a single tool step, recorded in a ``TraceEntry`` (D12)."""

    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class LLMProvider(str, Enum):
    """Supported LLM backends for the single Query-Understanding call (D16)."""

    GROQ = "groq"
    GEMINI = "gemini"
    OLLAMA = "ollama"
