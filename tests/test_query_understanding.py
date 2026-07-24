"""Tests for LLMQueryUnderstanding (Dev A - Phase 2).

The LLM provider is always mocked — no test touches an external API. Covers the
successful LLM path, every fallback trigger, the deterministic keyword extractor,
confidence propagation, visualization/entity extraction, and provider-abstraction
conformance.
"""

from __future__ import annotations

import json

import pytest

from app.agent.understanding import _FALLBACK_CONFIDENCE, LLMQueryUnderstanding
from app.enums import AMLPattern, IntentType
from app.interfaces import QueryUnderstanding
from app.llm.client import LLMClient
from app.schemas import Understanding

# ── test doubles for the ONE provider abstraction (LLMClient) ────────────────


class StubLLM(LLMClient):
    """Returns a canned JSON string; records that it was called."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete_json(self, system: str, user: str, timeout: float) -> str:
        self.calls += 1
        self.last_system = system
        self.last_user = user
        return self.response


class RaisingLLM(LLMClient):
    """Raises a given exception to simulate provider failures / timeouts."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def complete_json(self, system: str, user: str, timeout: float) -> str:
        raise self.exc


def _valid_llm_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "intent": "detect_pattern",
        "entities": [],
        "filters": {"date_range": {"last_days": 30}},
        "aml_pattern": "structuring",
        "needs_eda": False,
        "confidence": 0.91,
    }
    payload.update(overrides)
    return json.dumps(payload)


SCHEMA = {"customer_id": "str", "amount": "float", "timestamp": "datetime"}


# ── successful LLM path ──────────────────────────────────────────────────────


def test_successful_llm_response_is_parsed_and_validated() -> None:
    qu = LLMQueryUnderstanding(llm_client=StubLLM(_valid_llm_json()))
    result = qu.understand("Find structuring in the last 30 days", SCHEMA)
    assert isinstance(result, Understanding)
    assert result.intent is IntentType.DETECT_PATTERN
    assert result.aml_pattern is AMLPattern.STRUCTURING
    assert result.filters.date_range is not None
    assert result.filters.date_range.last_days == 30


def test_confidence_is_propagated_from_llm() -> None:
    qu = LLMQueryUnderstanding(llm_client=StubLLM(_valid_llm_json(confidence=0.83)))
    result = qu.understand("anything", SCHEMA)
    assert result.confidence == 0.83
    # A successful parse must NOT be the low-confidence fallback value.
    assert result.confidence != _FALLBACK_CONFIDENCE


def test_llm_path_used_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubLLM(_valid_llm_json())
    qu = LLMQueryUnderstanding(llm_client=stub)
    qu.understand("Find structuring patterns", SCHEMA)
    assert stub.calls == 1  # the injected client was actually used


# ── fallback triggers (each must return a valid Understanding, never raise) ──


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("deadline"), RuntimeError("provider 500"), ConnectionError("dns")],
)
def test_llm_exception_triggers_fallback(exc: Exception) -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(exc))
    result = qu.understand("Find structuring in the last 30 days", SCHEMA)
    assert isinstance(result, Understanding)
    assert result.confidence == _FALLBACK_CONFIDENCE
    assert result.aml_pattern is AMLPattern.STRUCTURING  # keyword-derived


def test_invalid_json_triggers_fallback() -> None:
    qu = LLMQueryUnderstanding(llm_client=StubLLM("not-json {oops"))
    result = qu.understand("Analyse this dataset", SCHEMA)
    assert isinstance(result, Understanding)
    assert result.confidence == _FALLBACK_CONFIDENCE


def test_schema_validation_failure_triggers_fallback() -> None:
    # intent is not a valid IntentType -> ValidationError -> fallback.
    bad = json.dumps({"intent": "banana", "confidence": 0.5})
    qu = LLMQueryUnderstanding(llm_client=StubLLM(bad))
    result = qu.understand("Find structuring", SCHEMA)
    assert isinstance(result, Understanding)
    assert result.confidence == _FALLBACK_CONFIDENCE


def test_out_of_range_confidence_triggers_fallback() -> None:
    bad = json.dumps({"intent": "detect_pattern", "confidence": 5.0})
    qu = LLMQueryUnderstanding(llm_client=StubLLM(bad))
    result = qu.understand("Find structuring", SCHEMA)
    assert result.confidence == _FALLBACK_CONFIDENCE


def test_missing_provider_falls_back_without_crashing() -> None:
    # No client injected and the factory is not implemented yet -> must fall back.
    qu = LLMQueryUnderstanding()
    result = qu.understand("Find structuring in the last 30 days", SCHEMA)
    assert isinstance(result, Understanding)
    assert result.confidence == _FALLBACK_CONFIDENCE


# ── deterministic keyword fallback content ───────────────────────────────────


def test_fallback_extracts_pattern_and_date_range() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Find structuring patterns in the last 30 days", SCHEMA)
    assert result.intent is IntentType.DETECT_PATTERN
    assert result.aml_pattern is AMLPattern.STRUCTURING
    assert result.filters.date_range is not None
    assert result.filters.date_range.last_days == 30


def test_fallback_entity_extraction_sets_single_entity() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Is customer 4521 suspicious?", SCHEMA)
    assert result.entities == ["4521"]
    assert result.intent is IntentType.SINGLE_ENTITY


def test_fallback_threshold_and_amount_extraction() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Which customers made 10+ transactions under $10,000?", SCHEMA)
    assert result.intent is IntentType.THRESHOLD_RULE
    assert result.filters.max_amount == 10000.0


def test_fallback_does_not_misread_transaction_count_as_amount() -> None:
    # "more than 3 transactions" is a count, not a $ amount -> no amount filter.
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Customers with more than 3 transactions", SCHEMA)
    assert result.intent is IntentType.THRESHOLD_RULE
    assert result.filters.min_amount is None
    assert result.filters.max_amount is None


def test_fallback_country_filter() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Flag high-risk customers in India using velocity", SCHEMA)
    assert result.filters.country == "IN"
    assert result.aml_pattern is AMLPattern.RAPID_CASH_OUT


def test_fallback_eda_intent_for_broad_query() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Analyse this dataset for suspicious activity", SCHEMA)
    assert result.intent is IntentType.EDA
    assert result.needs_eda is True


# ── visualization intent ─────────────────────────────────────────────────────


def test_visualization_request_sets_needs_eda() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Plot high-risk customers by country", SCHEMA)
    assert result.needs_eda is True  # visualization signalled via needs_eda
    assert result.intent is IntentType.DETECT_PATTERN


def test_pure_exploration_visualization_is_eda() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    result = qu.understand("Show me a chart of transaction amount distributions", SCHEMA)
    assert result.intent is IntentType.EDA
    assert result.needs_eda is True


# ── determinism & provider abstraction ───────────────────────────────────────


def test_fallback_is_deterministic() -> None:
    qu = LLMQueryUnderstanding(llm_client=RaisingLLM(RuntimeError()))
    query = "Find structuring patterns in the last 30 days"
    first = qu.understand(query, SCHEMA).model_dump()
    second = qu.understand(query, SCHEMA).model_dump()
    assert first == second


def test_implements_query_understanding_interface() -> None:
    qu = LLMQueryUnderstanding(llm_client=StubLLM(_valid_llm_json()))
    assert isinstance(qu, QueryUnderstanding)


def test_depends_only_on_the_llmclient_abstraction() -> None:
    # The injected dependency is the single project abstraction, not a bespoke client.
    stub = StubLLM(_valid_llm_json())
    assert isinstance(stub, LLMClient)
    qu = LLMQueryUnderstanding(llm_client=stub)
    result = qu.understand("Find structuring", SCHEMA)
    assert isinstance(result, Understanding)
