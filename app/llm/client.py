"""Provider-agnostic LLM client (D16).

A thin interface over the free-tier providers (Groq primary; Gemini/Ollama
optional fallbacks). Used for exactly one critical-path call — Query Understanding —
plus optional explanation phrasing.

Each provider does **only** transport: build the provider's message payload, call it
with the configured model/timeout/retries, and return the model's raw text exactly as
received. It never parses, repairs, or validates JSON, never strips markdown, and
never implements fallback or business logic — Query Understanding owns all of that and
catches any exception raised here.

Provider SDKs are imported **lazily** inside each client so that importing this module
never fails when an optional SDK (Gemini/Ollama) is absent; such a failure surfaces
only when that provider is actually used, and Query Understanding falls back.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import settings
from app.enums import LLMProvider

#: Local Ollama REST host (not a configurable Settings key — a fixed default).
_OLLAMA_HOST = "http://localhost:11434"


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
        ...


class GroqClient(LLMClient):
    """Groq provider (primary). Uses the installed ``groq`` SDK."""

    def __init__(self) -> None:
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._max_retries = settings.llm_max_retries

    def complete_json(self, system: str, user: str, timeout: float) -> str:
        from groq import Groq  # lazy import

        client = Groq(api_key=self._api_key, max_retries=self._max_retries)
        completion = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        return completion.choices[0].message.content or ""


class OllamaClient(LLMClient):
    """Ollama provider (optional, offline). Uses the ``ollama`` SDK if installed."""

    def __init__(self) -> None:
        self._model = settings.llm_model

    def complete_json(self, system: str, user: str, timeout: float) -> str:
        import ollama  # lazy import (optional SDK)

        client = ollama.Client(host=_OLLAMA_HOST, timeout=timeout)
        response = client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format="json",
        )
        return response["message"]["content"]


class GeminiClient(LLMClient):
    """Gemini provider (optional). Uses the ``google-generativeai`` SDK if installed."""

    def __init__(self) -> None:
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key

    def complete_json(self, system: str, user: str, timeout: float) -> str:
        import google.generativeai as genai  # lazy import (optional SDK)

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model, system_instruction=system)
        response = model.generate_content(
            user, request_options={"timeout": timeout}
        )
        return response.text


def get_llm_client(provider: LLMProvider | None = None) -> LLMClient:
    """Factory: return a client for the configured (or given) provider.

    Args:
        provider: Override; defaults to ``settings.llm_provider``.

    Returns:
        A concrete :class:`LLMClient`. Construction does not import any provider
        SDK (imports are lazy, inside :meth:`complete_json`).

    Raises:
        ValueError: for an unsupported provider.
    """
    selected = provider or settings.llm_provider
    if selected is LLMProvider.GROQ:
        return GroqClient()
    if selected is LLMProvider.OLLAMA:
        return OllamaClient()
    if selected is LLMProvider.GEMINI:
        return GeminiClient()
    raise ValueError(f"Unsupported LLM provider: {selected!r}")
