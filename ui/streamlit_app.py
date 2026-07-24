"""Streamlit UI — the demo surface (D13).

Calls the agent **in-process** (no separate server). Renders the query box, the
flagship example buttons, the plan/skipped panel, the results table with risk
badges, expandable per-flag explanations, charts, and the runtime trace.

Run: ``streamlit run ui/streamlit_app.py`` (or ``./run.sh``).

This is scaffolding: layout intent is documented; the interactive wiring to the
agent pipeline is implemented in later phases.
"""

from __future__ import annotations

import streamlit as st

from app.config import configure_logging

configure_logging()


def render() -> None:
    """Render the single-page app.

    Layout (Phase 4):
        1. Header + one-line pitch.
        2. Query input + flagship example buttons (offline-safe understanding, D14).
        3. Plan / skipped panel — the "what the agent decided and why" centerpiece.
        4. Results table (risk badges) + expandable evidence-grounded explanations.
        5. Charts (Plotly) + runtime trace table.
    """
    st.set_page_config(page_title="AI Suspicious Activity Detection", layout="wide")
    st.title("AI-Powered Suspicious Activity Detection")
    st.caption(
        "Ask a question about the transactions. The agent plans a different tool "
        "path per query and shows you exactly what it decided, why, and the evidence."
    )
    # TODO(Phase 1/4): query box -> call pipeline in-process -> render APIResponse
    # (plan, skipped, results, charts, trace).
    st.info("Foundation scaffold — analysis UI is implemented in later phases.")


if __name__ == "__main__":
    render()
