"""Unit tests for the LLM Client provider layer (D16).

Every provider SDK is faked — no test performs a real network request. Verifies the
factory / provider selection, each provider's raw-text passthrough, timeout and
config propagation, lazy imports, exception propagation, and that the client never
parses/validates JSON or logs secrets.
"""

from __future__ import annotations

import logging
import sys
import types
from typing import Any

import pytest

from app.config import settings
from app.enums import LLMProvider
from app.llm.client import (
    GeminiClient,
    GroqClient,
    LLMClient,
    OllamaClient,
    get_llm_client,
)

SYSTEM = "return json"
USER = "Find structuring"
TIMEOUT = 8.0


# ── fake provider SDK modules (injected into sys.modules) ────────────────────


def _fake_groq(content: Any, rec: dict) -> types.ModuleType:
    mod = types.ModuleType("groq")

    class Groq:
        def __init__(self, **kwargs: Any) -> None:
            rec["init"] = kwargs

            def create(**ckw: Any) -> Any:
                rec["create"] = ckw
                if isinstance(content, Exception):
                    raise content
                message = types.SimpleNamespace(content=content)
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create)
            )

    mod.Groq = Groq  # type: ignore[attr-defined]
    return mod


def _fake_ollama(content: Any, rec: dict) -> types.ModuleType:
    mod = types.ModuleType("ollama")

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            rec["init"] = kwargs

        def chat(self, **ckw: Any) -> Any:
            rec["chat"] = ckw
            if isinstance(content, Exception):
                raise content
            return {"message": {"content": content}}

    mod.Client = Client  # type: ignore[attr-defined]
    return mod


def _fake_gemini(content: Any, rec: dict) -> types.ModuleType:
    mod = types.ModuleType("google.generativeai")

    def configure(**kwargs: Any) -> None:
        rec["configure"] = kwargs

    class GenerativeModel:
        def __init__(self, model_name: str, system_instruction: str | None = None) -> None:
            rec["model"] = {"model_name": model_name, "system_instruction": system_instruction}

        def generate_content(self, user: str, request_options: dict | None = None) -> Any:
            rec["generate"] = {"user": user, "request_options": request_options}
            if isinstance(content, Exception):
                raise content
            return types.SimpleNamespace(text=content)

    mod.configure = configure  # type: ignore[attr-defined]
    mod.GenerativeModel = GenerativeModel  # type: ignore[attr-defined]
    return mod


def _install(monkeypatch: pytest.MonkeyPatch, name: str, module: types.ModuleType) -> None:
    monkeypatch.setitem(sys.modules, name, module)


# ── factory / provider selection ─────────────────────────────────────────────


def test_factory_selects_by_provider() -> None:
    assert isinstance(get_llm_client(LLMProvider.GROQ), GroqClient)
    assert isinstance(get_llm_client(LLMProvider.OLLAMA), OllamaClient)
    assert isinstance(get_llm_client(LLMProvider.GEMINI), GeminiClient)


def test_factory_defaults_to_configured_provider() -> None:
    # Default settings.llm_provider is GROQ.
    assert isinstance(get_llm_client(), GroqClient)


def test_factory_construction_does_not_import_sdks() -> None:
    # Selecting a provider must not import its SDK (imports are lazy in complete_json).
    get_llm_client(LLMProvider.OLLAMA)  # ollama is not installed; must not raise
    get_llm_client(LLMProvider.GEMINI)


def test_all_clients_implement_the_interface() -> None:
    for cls in (GroqClient, OllamaClient, GeminiClient):
        assert issubclass(cls, LLMClient)


# ── Groq ─────────────────────────────────────────────────────────────────────


def test_groq_returns_raw_content_and_propagates_config(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "groq", _fake_groq('{"intent":"eda"}', rec))
    monkeypatch.setattr(settings, "llm_api_key", "KEY123")
    monkeypatch.setattr(settings, "llm_max_retries", 3)
    monkeypatch.setattr(settings, "llm_model", "llama-x")

    out = GroqClient().complete_json(SYSTEM, USER, TIMEOUT)

    assert out == '{"intent":"eda"}'  # raw, unparsed
    assert rec["init"] == {"api_key": "KEY123", "max_retries": 3}
    assert rec["create"]["model"] == "llama-x"
    assert rec["create"]["timeout"] == TIMEOUT
    assert rec["create"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in rec["create"]["messages"]] == ["system", "user"]


# ── Ollama ───────────────────────────────────────────────────────────────────


def test_ollama_returns_raw_content_and_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "ollama", _fake_ollama('{"ok":1}', rec))
    monkeypatch.setattr(settings, "llm_model", "llama-x")

    out = OllamaClient().complete_json(SYSTEM, USER, TIMEOUT)

    assert out == '{"ok":1}'
    assert rec["init"]["timeout"] == TIMEOUT
    assert rec["chat"]["model"] == "llama-x"
    assert rec["chat"]["format"] == "json"


# ── Gemini (lazy import) ─────────────────────────────────────────────────────


def test_gemini_returns_raw_text_and_passes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "google.generativeai", _fake_gemini('{"g":1}', rec))
    monkeypatch.setattr(settings, "llm_api_key", "GKEY")
    monkeypatch.setattr(settings, "llm_model", "gemini-x")

    out = GeminiClient().complete_json(SYSTEM, USER, TIMEOUT)

    assert out == '{"g":1}'
    assert rec["configure"] == {"api_key": "GKEY"}
    assert rec["model"]["system_instruction"] == SYSTEM
    assert rec["generate"]["request_options"] == {"timeout": TIMEOUT}


def test_missing_optional_sdk_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure 'ollama' is unimportable (it is not installed); complete_json must
    # raise (Query Understanding catches it and falls back).
    monkeypatch.setitem(sys.modules, "ollama", None)
    with pytest.raises(ImportError):
        OllamaClient().complete_json(SYSTEM, USER, TIMEOUT)


# ── raw passthrough (no parsing / no validation) ─────────────────────────────


def test_invalid_json_is_returned_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "groq", _fake_groq("not json {oops", rec))
    out = GroqClient().complete_json(SYSTEM, USER, TIMEOUT)
    assert out == "not json {oops"  # not parsed, not repaired, not validated


def test_markdown_fenced_output_is_not_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    fenced = '```json\n{"x":1}\n```'
    _install(monkeypatch, "groq", _fake_groq(fenced, rec))
    assert GroqClient().complete_json(SYSTEM, USER, TIMEOUT) == fenced


def test_none_content_becomes_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "groq", _fake_groq(None, rec))
    assert GroqClient().complete_json(SYSTEM, USER, TIMEOUT) == ""


# ── error propagation ────────────────────────────────────────────────────────


def test_provider_exception_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    rec: dict = {}
    _install(monkeypatch, "groq", _fake_groq(RuntimeError("provider 500"), rec))
    with pytest.raises(RuntimeError, match="provider 500"):
        GroqClient().complete_json(SYSTEM, USER, TIMEOUT)


# ── no secret logging ────────────────────────────────────────────────────────


def test_api_key_is_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    rec: dict = {}
    _install(monkeypatch, "groq", _fake_groq("{}", rec))
    monkeypatch.setattr(settings, "llm_api_key", "SUPERSECRET")
    with caplog.at_level(logging.DEBUG):
        GroqClient().complete_json(SYSTEM, USER, TIMEOUT)
    assert "SUPERSECRET" not in caplog.text
