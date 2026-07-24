"""Provider-agnostic LLM client (D16).

One thin interface over the free-tier providers (Groq primary; Gemini/Ollama
fallbacks). Used for exactly one critical-path call — Query Understanding — plus
optional explanation phrasing. It returns text/JSON only; it never computes risk
numbers or builds plans.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.enums import LLMProvider


class LLMClient(ABC):
    """Abstract LLM backend. Concrete providers implement :meth:`complete_json`."""

    @abstractmethod
    def complete_json(self, system: str, user: str, timeout: float) -> str:
        """Return the model's response as a raw JSON string.

        Args:
            system: System prompt (schema/instructions).
            user: User content (the query + dataset schema).
            timeout: Hard timeout in seconds (D2: 8s on the critical path).

        Returns:
            Raw JSON text, to be validated by the caller into a Pydantic model.
        """
        # TODO(Phase 3): implement per provider (Groq/Gemini/Ollama).
        raise NotImplementedError


def get_llm_client(provider: LLMProvider | None = None) -> LLMClient:
    """Factory: return a client for the configured (or given) provider.

    Args:
        provider: Override; defaults to ``settings.llm_provider``.

    Returns:
        A concrete :class:`LLMClient`.
    """
    # TODO(Phase 3): construct GroqClient / GeminiClient / OllamaClient based on
    # the selected provider and settings.llm_api_key / settings.llm_model.
    raise NotImplementedError("get_llm_client — implemented in Phase 3")
