#!/usr/bin/env bash
# One-command launch (satisfies "runnable with setup steps", G2).
# Starts the Streamlit UI, which calls the agent in-process (D13).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Create/activate a local venv if one isn't already active.
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

pip install --quiet --requirement requirements.txt

# Load .env if present (keys are read via pydantic-settings too).
if [[ -f ".env" ]]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
fi

exec streamlit run ui/streamlit_app.py
