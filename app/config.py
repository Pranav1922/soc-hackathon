"""Central configuration — the single source of every tunable value.

Two kinds of configuration live here:

1. **Frozen constants** (AML thresholds, risk formula, IsolationForest params).
   These are pinned by ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` (D6, D7, D8) and
   must not be changed live during a demo — only here, before recording.
2. **Environment-driven settings** (LLM keys/timeouts, API host/port, paths,
   logging), read from ``.env`` via :class:`Settings`.

**There must be no magic numbers elsewhere in the codebase.** Every threshold,
weight, window, and path is defined once, here, and imported where needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.enums import AMLPattern, LLMProvider

# ─────────────────────────────────────────────────────────────────────────────
# Paths (pathlib everywhere — never string paths)
# ─────────────────────────────────────────────────────────────────────────────

#: Repository root (``app/config.py`` → ``app/`` → repo root).
BASE_DIR: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = BASE_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
SAMPLE_DATA_DIR: Path = DATA_DIR / "sample"
SYNTHETIC_DATA_DIR: Path = DATA_DIR / "synthetic"

#: Default dataset the agent analyses (overridable via ``DATASET_PATH`` env var).
DEFAULT_DATASET_PATH: Path = SAMPLE_DATA_DIR / "transactions.parquet"


# ─────────────────────────────────────────────────────────────────────────────
# AML rule thresholds — FROZEN (D6). CTR = Currency Transaction Report line.
# ─────────────────────────────────────────────────────────────────────────────

#: US Currency Transaction Report reporting threshold; basis for "just under" logic.
CTR_THRESHOLD: float = 10_000.0


@dataclass(frozen=True)
class StructuringRule:
    """Structuring: many sub-threshold cash deposits to dodge the CTR line (D6)."""

    min_count: int = 3
    amount_min: float = 8_000.0
    amount_max: float = 9_999.0
    window_days: int = 7


@dataclass(frozen=True)
class SmurfingRule:
    """Smurfing: one account fed by many small deposits from distinct sources (D6)."""

    max_amount: float = 3_000.0
    min_distinct_sources: int = 5
    window_days: int = 7


@dataclass(frozen=True)
class RapidCashOutRule:
    """Rapid cash-out: a large withdrawal shortly after a matching deposit (D6)."""

    min_ratio: float = 0.90
    window_hours: int = 24


@dataclass(frozen=True)
class LayeringRule:
    """Layering (P2): chained transfers draining an account quickly (D6)."""

    min_hops: int = 3
    window_hours: int = 72


@dataclass(frozen=True)
class AMLThresholds:
    """Bundle of all AML rule configs, exposed as ``AML``."""

    structuring: StructuringRule = field(default_factory=StructuringRule)
    smurfing: SmurfingRule = field(default_factory=SmurfingRule)
    rapid_cash_out: RapidCashOutRule = field(default_factory=RapidCashOutRule)
    layering: LayeringRule = field(default_factory=LayeringRule)
    ctr_threshold: float = CTR_THRESHOLD


#: Import this everywhere AML thresholds are needed.
AML: AMLThresholds = AMLThresholds()


# ─────────────────────────────────────────────────────────────────────────────
# Risk scoring — FROZEN deterministic formula (D7)
#   score = min(1.0, rule_weight * rule_severity + anomaly_weight * anomaly_score)
#   bands: >= high_band -> high, >= medium_band -> medium, else low
#   a confirmed rule hit floors the band at medium.
# ─────────────────────────────────────────────────────────────────────────────

#: Allowed rule-severity levels (D7: rule_severity ∈ {0, 0.5, 0.8, 1.0}).
RULE_SEVERITY_LEVELS: tuple[float, ...] = (0.0, 0.5, 0.8, 1.0)

#: Per-pattern severity used by the Risk Classifier.
#: TODO(Phase 5): calibrate these on the sample dataset, then freeze.
RULE_SEVERITY: dict[AMLPattern, float] = {
    AMLPattern.STRUCTURING: 0.8,
    AMLPattern.SMURFING: 0.8,
    AMLPattern.LAYERING: 1.0,
    AMLPattern.RAPID_CASH_OUT: 0.5,
    AMLPattern.NONE: 0.0,
}


@dataclass(frozen=True)
class RiskScoring:
    """Weights and band cutoffs for the deterministic risk score (D7)."""

    rule_weight: float = 0.6
    anomaly_weight: float = 0.4
    high_band: float = 0.75
    medium_band: float = 0.45
    #: A confirmed rule hit cannot score below this band.
    rule_hit_floor: float = 0.45


RISK: RiskScoring = RiskScoring()


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly detection — IsolationForest (D8), secondary to rules
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IsolationForestParams:
    """Fixed IsolationForest configuration — reproducible across demo runs (D8)."""

    contamination: float = 0.02
    random_state: int = 42
    n_estimators: int = 100
    #: Minimum subset size before ML runs at all; below this, rules only (D3, D8).
    min_samples: int = 500


ISOLATION_FOREST: IsolationForestParams = IsolationForestParams()


# ─────────────────────────────────────────────────────────────────────────────
# Planner settings (D3)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlannerConfig:
    """Knobs for the deterministic planner (see D3 planning rules)."""

    #: Confidence stamped on steps chosen by hard deterministic rules (D12).
    deterministic_confidence: float = 1.0
    #: Gate for including the AnomalyDetector step (mirrors IsolationForest.min_samples).
    anomaly_min_rows: int = ISOLATION_FOREST.min_samples


PLANNER: PlannerConfig = PlannerConfig()


# ─────────────────────────────────────────────────────────────────────────────
# Environment-driven settings (secrets, runtime) — read from .env (D16)
# ─────────────────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Runtime settings loaded from environment / ``.env``.

    Frozen constants above are *not* here — only values that legitimately vary by
    environment (keys, timeouts, ports, paths, log level).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM (the single Query-Understanding call — D2, D16)
    llm_provider: LLMProvider = LLMProvider.GROQ
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 8.0
    llm_max_retries: int = 1

    # API (OPTIONAL boundary — D13)
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Data
    dataset_path: Path = DEFAULT_DATASET_PATH

    # Logging
    log_level: str = "INFO"


#: Import this singleton for env-driven settings.
settings: Settings = Settings()


# ─────────────────────────────────────────────────────────────────────────────
# Logging (use logging, never print)
# ─────────────────────────────────────────────────────────────────────────────


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once, at process entry (UI / API / scripts).

    Args:
        level: Override for the configured log level; falls back to ``settings.log_level``.
    """

    logging.basicConfig(
        level=(level or settings.log_level).upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
