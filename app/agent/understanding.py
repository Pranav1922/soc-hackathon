"""Query Understanding — the single LLM call on the critical path (D2, D16).

Turns a natural-language query into a validated :class:`Understanding`. The LLM
result is Pydantic-validated; on failure/timeout/malformed output it degrades to a
keyword-based understanding so the rest of the (deterministic) pipeline still runs.
"""

from __future__ import annotations

from app.config import settings
from app.interfaces import QueryUnderstanding
from app.llm.client import LLMClient
from app.schemas import Understanding


class LLMQueryUnderstanding(QueryUnderstanding):
    """Primary understanding via LLM, with a deterministic keyword fallback."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        # TODO(Phase 3): default to a provider client selected from settings.
        self._llm = llm_client
        self._timeout = settings.llm_timeout_seconds

    def understand(self, query: str, schema_map: dict[str, str]) -> Understanding:
        # TODO(Phase 3): build the prompt (query + schema), call the LLM with an
        # 8s timeout, validate JSON into Understanding; on any failure call
        # self._keyword_fallback(query, schema_map).
        raise NotImplementedError("LLMQueryUnderstanding.understand — Phase 3")

    def _keyword_fallback(self, query: str, schema_map: dict[str, str]) -> Understanding:
        """Deterministic keyword extractor used when the LLM is unavailable (D2)."""
        # TODO(Phase 3): regex/keyword rules -> intent, entities, filters, pattern
        # with a low confidence score.
        raise NotImplementedError("LLMQueryUnderstanding._keyword_fallback — Phase 3")
