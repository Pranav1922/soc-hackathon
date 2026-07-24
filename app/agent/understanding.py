"""Query Understanding — the single LLM call on the critical path (D2, D16).

Turns a natural-language query into a validated :class:`Understanding`. The LLM
result is Pydantic-validated; on any failure (timeout, exception, invalid JSON, or
schema-validation error) it degrades to a deterministic keyword-based fallback so the
rest of the (deterministic) pipeline still runs. **The application never crashes
because of an LLM failure.**

LLM access goes through the single project abstraction :class:`app.llm.client.LLMClient`
(obtained via :func:`app.llm.client.get_llm_client`); this module never talks to a
provider SDK directly, so new providers require no change here. All configuration is
read from :mod:`app.config`.

Note on "visualization requests": the frozen :class:`Understanding` has no dedicated
visualization field — the architecture routes the Visualizer through the planner
(Visualizer runs when EDA or a detector is present). Visualization intent is therefore
signalled here via ``needs_eda`` (and ``intent == EDA`` for pure exploration), not a
new field.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.config import settings
from app.enums import AMLPattern, IntentType, LLMProvider
from app.interfaces import QueryUnderstanding
from app.llm.client import LLMClient, get_llm_client
from app.schemas import DateRange, Filters, Understanding

logger = logging.getLogger(__name__)

# Confidence stamped on a fallback understanding — deliberately low to signal that the
# result is degraded (keyword-derived, not LLM-derived). Local to this module: it is
# QU-internal logic, not a shared tunable, and config.py is frozen.
_FALLBACK_CONFIDENCE: float = 0.4

# ── keyword / regex tables for the deterministic fallback ────────────────────

# AML patterns in priority order; first match wins.
_PATTERN_KEYWORDS: tuple[tuple[AMLPattern, tuple[str, ...]], ...] = (
    (AMLPattern.STRUCTURING, ("structuring", "structure", "sub-threshold", "sub threshold", "just under")),
    (AMLPattern.SMURFING, ("smurfing", "smurf", "many small", "multiple small", "distinct sources")),
    (AMLPattern.LAYERING, ("layering", "layered", "transfer chain", "hops", "hop")),
    (AMLPattern.RAPID_CASH_OUT, ("rapid cash", "cash out", "cash-out", "cashout", "velocity", "quick withdrawal", "rapid movement")),
)

_COMPARE_KEYWORDS: tuple[str, ...] = ("compare", "versus", "vs", "difference between", "against")
_EDA_KEYWORDS: tuple[str, ...] = (
    "analyse", "analyze", "explore", "overview", "profile", "summary",
    "summarise", "summarize", "baseline", "distribution", "eda", "composition",
)
_THRESHOLD_KEYWORDS: tuple[str, ...] = (
    "how many", "how much", "count", "number of", "more than", "at least",
    "fewer than", "greater than", "less than", "minimum", "maximum",
)
_DETECT_KEYWORDS: tuple[str, ...] = (
    "find", "flag", "detect", "identify", "suspicious", "high-risk", "high risk",
    "anomal", "launder",
)
_VIZ_KEYWORDS: tuple[str, ...] = (
    "chart", "plot", "graph", "visuali", "histogram", "distribution", "trend",
    "show me", "dashboard",
)
_TXN_TYPE_KEYWORDS: tuple[str, ...] = ("deposit", "withdrawal", "transfer")

# Country name -> ISO code (small, deterministic set; extend as needed).
_COUNTRY_CODES: dict[str, str] = {
    "india": "IN",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "united arab emirates": "AE",
    "uae": "AE",
}

_PERIOD_DAYS: dict[str, int] = {"day": 1, "week": 7, "month": 30, "year": 365}


def _matches(q: str, keywords: tuple[str, ...]) -> bool:
    """True if any keyword occurs in ``q`` as a whole word/phrase.

    Word-boundary matching avoids substring false positives (e.g. the keyword
    "count" must not match "country").
    """
    return any(re.search(rf"\b{re.escape(kw)}\b", q) for kw in keywords)

_ENTITY_RE = re.compile(
    r"(?:customer|account|client|cust|acct)\s*(?:id\s*)?#?\s*([A-Za-z]?\d{2,})", re.IGNORECASE
)
_ID_RE = re.compile(r"\bid\s*#?\s*([A-Za-z]?\d{2,})\b", re.IGNORECASE)
_LAST_N_PERIOD_RE = re.compile(r"(?:last|past|previous)\s+(\d+)\s+(day|week|month|year)s?", re.IGNORECASE)
_LAST_PERIOD_RE = re.compile(r"(?:last|past|previous)\s+(day|week|month|year)\b", re.IGNORECASE)
_COUNT_PLUS_RE = re.compile(r"\b\d+\s*\+")
# A currency sign is required so transaction *counts* ("more than 3 transactions")
# are not misread as dollar *amounts*. Missing a bare amount is harmless (no filter);
# a spurious amount filter would wrongly empty the subset.
_UNDER_RE = re.compile(r"(?:under|below|less than|up to|beneath)\s*\$\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_OVER_RE = re.compile(r"(?:over|above|more than|greater than|at least|exceeding|minimum of)\s*\$\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


class LLMQueryUnderstanding(QueryUnderstanding):
    """Primary understanding via LLM, with a deterministic keyword fallback.

    The LLM client is injected (dependency injection) for testability; when not
    provided it is lazily obtained from the frozen provider factory using the
    configured provider. Acquisition failures are treated as LLM failures and route
    to the fallback, so this class is usable even before any concrete provider ships.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self._llm = llm_client
        self._provider = provider or settings.llm_provider
        self._timeout = settings.llm_timeout_seconds

    # ── public API (QueryUnderstanding contract) ──────────────────────────────

    def understand(self, query: str, schema_map: dict[str, str]) -> Understanding:
        """Extract a validated :class:`Understanding` from a natural-language query.

        Attempts the LLM path first; on *any* failure, logs it and returns the
        deterministic keyword fallback. Always returns a valid ``Understanding``.
        """
        try:
            understanding = self._understand_via_llm(query, schema_map)
        except TimeoutError:
            logger.warning(
                "LLM understanding timed out after %ss; using keyword fallback", self._timeout
            )
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON (%s); using keyword fallback", exc)
        except ValidationError as exc:
            logger.warning(
                "LLM output failed schema validation (%d error(s)); using keyword fallback",
                len(exc.errors()),
            )
        except Exception as exc:  # noqa: BLE001 - must never crash on LLM failure (D2)
            logger.error(
                "LLM understanding failed (%s: %s); using keyword fallback",
                type(exc).__name__,
                exc,
            )
        else:
            logger.info(
                "Query understood via LLM: intent=%s pattern=%s confidence=%.2f",
                understanding.intent.value,
                understanding.aml_pattern.value,
                understanding.confidence,
            )
            return understanding

        return self._keyword_fallback(query, schema_map)

    # ── LLM path ──────────────────────────────────────────────────────────────

    def _understand_via_llm(self, query: str, schema_map: dict[str, str]) -> Understanding:
        """Call the LLM and validate its response. Raises on any failure."""
        client = self._get_client()
        raw = client.complete_json(
            system=self._build_system_prompt(),
            user=self._build_user_prompt(query, schema_map),
            timeout=self._timeout,
        )
        data = json.loads(raw)  # -> JSONDecodeError on malformed output
        return Understanding.model_validate(data)  # -> ValidationError on bad schema

    def _get_client(self) -> LLMClient:
        """Return the injected client, or lazily build one from the configured provider."""
        if self._llm is None:
            self._llm = get_llm_client(self._provider)
        return self._llm

    @staticmethod
    def _build_system_prompt() -> str:
        """Instruction prompt: return JSON matching the frozen Understanding schema."""
        intents = ", ".join(i.value for i in IntentType)
        patterns = ", ".join(p.value for p in AMLPattern)
        return (
            "You are an AML analyst assistant. Read the user's question about "
            "transaction data and return ONLY a JSON object with these fields:\n"
            f'  "intent": one of [{intents}]\n'
            '  "entities": list of customer/account ids mentioned (strings)\n'
            '  "filters": object with optional keys date_range '
            '({last_days|start|end}), country, segment, transaction_type, '
            "min_amount, max_amount\n"
            f'  "aml_pattern": one of [{patterns}]\n'
            '  "needs_eda": boolean (true for broad exploration or visualization)\n'
            '  "confidence": float between 0 and 1\n'
            "Respond with JSON only, no prose."
        )

    @staticmethod
    def _build_user_prompt(query: str, schema_map: dict[str, str]) -> str:
        """User content: the query grounded with the dataset schema."""
        if schema_map:
            columns = ", ".join(f"{name} ({dtype})" for name, dtype in schema_map.items())
        else:
            columns = "(schema unavailable)"
        return f"Dataset columns: {columns}\n\nQuestion: {query}"

    # ── deterministic keyword fallback ────────────────────────────────────────

    def _keyword_fallback(self, query: str, schema_map: dict[str, str]) -> Understanding:
        """Deterministic keyword extractor used when the LLM path fails (D2).

        Pure function of the query text (schema_map is accepted for interface
        symmetry but not required). Always returns a valid, low-confidence
        :class:`Understanding`.
        """
        q = query.lower()
        entities = _extract_entities(query)
        pattern = _detect_pattern(q)
        filters = _extract_filters(q)
        wants_viz = _matches(q, _VIZ_KEYWORDS)
        intent = _detect_intent(q, entities, pattern, wants_viz)
        needs_eda = intent is IntentType.EDA or wants_viz

        understanding = Understanding(
            intent=intent,
            entities=entities,
            filters=filters,
            aml_pattern=pattern,
            needs_eda=needs_eda,
            confidence=_FALLBACK_CONFIDENCE,
        )
        logger.info(
            "Query understood via keyword fallback: intent=%s pattern=%s",
            intent.value,
            pattern.value,
        )
        return understanding


# ── module-level extraction helpers (pure, deterministic) ────────────────────


def _detect_intent(
    q: str, entities: list[str], pattern: AMLPattern, wants_viz: bool
) -> IntentType:
    """Map query text to a single :class:`IntentType` (deterministic priority order)."""
    if entities:
        return IntentType.SINGLE_ENTITY
    if _matches(q, _COMPARE_KEYWORDS):
        return IntentType.COMPARE
    if _COUNT_PLUS_RE.search(q) or _matches(q, _THRESHOLD_KEYWORDS):
        return IntentType.THRESHOLD_RULE
    if _matches(q, _EDA_KEYWORDS):
        return IntentType.EDA
    if pattern is not AMLPattern.NONE or _matches(q, _DETECT_KEYWORDS):
        return IntentType.DETECT_PATTERN
    if wants_viz:
        # A pure visualization/exploration request with no analytical target.
        return IntentType.EDA
    return IntentType.DETECT_PATTERN


def _detect_pattern(q: str) -> AMLPattern:
    """Return the first matching AML pattern, or NONE."""
    for pattern, keywords in _PATTERN_KEYWORDS:
        if _matches(q, keywords):
            return pattern
    return AMLPattern.NONE


def _extract_entities(query: str) -> list[str]:
    """Extract customer/account ids mentioned in the query (order-preserving, unique)."""
    found: list[str] = []
    for regex in (_ENTITY_RE, _ID_RE):
        for match in regex.findall(query):
            if match not in found:
                found.append(match)
    return found


def _extract_filters(q: str) -> Filters:
    """Extract structured filters (date range, country, txn type, amount bounds)."""
    return Filters(
        date_range=_extract_date_range(q),
        country=_extract_country(q),
        transaction_type=_extract_transaction_type(q),
        min_amount=_extract_amount(_OVER_RE, q),
        max_amount=_extract_amount(_UNDER_RE, q),
    )


def _extract_date_range(q: str) -> DateRange | None:
    """Parse relative periods like 'last 30 days' / 'past week' into ``last_days``."""
    match = _LAST_N_PERIOD_RE.search(q)
    if match:
        count = int(match.group(1))
        return DateRange(last_days=count * _PERIOD_DAYS[match.group(2).lower()])
    single = _LAST_PERIOD_RE.search(q)
    if single:
        return DateRange(last_days=_PERIOD_DAYS[single.group(1).lower()])
    return None


def _extract_country(q: str) -> str | None:
    """Map a mentioned country name to its ISO code."""
    for name, code in _COUNTRY_CODES.items():
        if re.search(rf"\b{re.escape(name)}\b", q):
            return code
    return None


def _extract_transaction_type(q: str) -> str | None:
    """Detect a transaction-type keyword (deposit / withdrawal / transfer)."""
    for txn_type in _TXN_TYPE_KEYWORDS:
        if re.search(rf"\b{txn_type}\b", q):
            return txn_type
    return None


def _extract_amount(regex: re.Pattern[str], q: str) -> float | None:
    """Parse a dollar amount following an under/over phrase, if present."""
    match = regex.search(q)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))
