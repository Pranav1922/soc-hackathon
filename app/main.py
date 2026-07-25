"""FastAPI entrypoint — OPTIONAL boundary (D13).

Streamlit calls the agent in-process by default; this API exists only for a custom
frontend (the React stretch). Endpoints are scaffolded here (routes + contracts);
the orchestration wiring lands in later phases.

Run (only if needed): ``uvicorn app.main:app --reload``.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException, status

from app.agent.pipeline import Pipeline
from app.config import configure_logging, settings
from app.schemas import APIRequest, APIResponse

configure_logging()


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    """Return the process-wide orchestrator, built once on first use."""
    return Pipeline()

app = FastAPI(
    title="AI-Powered Suspicious Activity Detection",
    version="0.1.0",
    summary="Agentic AML analysis — query-driven, explainable, deterministic planning.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "provider": settings.llm_provider.value}


@app.get("/schema")
def get_schema() -> dict[str, str]:
    """Return the loaded dataset's column -> dtype map (for UIs / prompt grounding)."""
    return get_pipeline().schema_map


@app.get("/examples")
def get_examples() -> list[dict[str, str]]:
    """Return the flagship example queries (with pre-parsed understanding, D14)."""
    # TODO(Phase 3): return the offline-safe example query set.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "examples — Phase 3")


@app.post("/analyze", response_model=APIResponse)
def analyze(request: APIRequest) -> APIResponse:
    """Run the full agent pipeline for a query and return the structured response.

    Pipeline: understanding → deterministic plan → execute → format (D1, D12).
    """
    return get_pipeline().analyze(request.query)
