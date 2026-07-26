# AI-Powered Suspicious Activity Detection

An agentic AML (Anti-Money Laundering) investigation system. A user asks a natural-language
question about transaction data; the agent **understands** the query, **dynamically plans a
different tool path for each question**, executes only the tools it needs, and returns
explainable, evidence-grounded risk flags with escalation recommendations — plus a visible
trace of *what it decided and why*.

> Built for a 48-hour campus hackathon (Problem Statement 1: AI-Powered Suspicious Activity
> Detection). Architecture detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
> [`docs/AGENT_FLOW.md`](docs/AGENT_FLOW.md), [`docs/MODULE_BREAKDOWN.md`](docs/MODULE_BREAKDOWN.md).

---

## Problem statement

Traditional rule-based AML systems drown compliance teams in false positives, while
sophisticated techniques — structuring, smurfing, layering — slip past rigid thresholds. The
goal: an autonomous agent that parses a plain-language request, investigates only what that
request needs, and returns a risk assessment a human reviewer can actually audit — not a
black-box score.

## What it does

- Parses a natural-language query → intent, filters (date range, segment, country, txn type),
  entities, and target AML pattern
- Builds a **query-specific execution plan** — invokes only the tools that query needs, never
  a fixed sequence
- Detects four AML typologies deterministically: **structuring, smurfing, rapid cash-out,
  layering** — each with exact, auditable evidence (transaction IDs, thresholds, amounts)
- Runs an unsupervised **IsolationForest** as a secondary detector for anomalies the named
  rules don't cover, fit live on the query's own filtered subset
- Fuses both signals into a **low / medium / high** risk band per entity, via a frozen,
  documented formula
- Generates a human-readable explanation and a recommended action (**monitor / review /
  report**) per flag
- Returns one structured response showing the plan, the skipped tools, the results, supporting
  charts, and a full execution trace — the direct evidence that the system is not a fixed
  pipeline

## Architecture summary

**One LLM call → deterministic planner → deterministic executor** (a modular monolith).

```
User query
  → Query Understanding      (1 LLM call → intent / entities / filters / AML pattern; keyword fallback)
  → Planner (DETERMINISTIC)  → ExecutionPlan (chooses only the tools this query needs)
  → Executor                 → runs selected tools, threads a shared Context, records a trace
  → Response                 → { query, understanding, plan[], skipped[], results[], charts[], trace[] }
```

- **The LLM never computes numbers or builds the plan** — it only extracts a structured
  understanding. Planning and execution are pure, deterministic, and testable — this is what
  keeps the demo reliable and every result reproducible.
- **Hybrid detection:** deterministic AML rules (structuring / smurfing / rapid cash-out /
  layering) are primary and own the explanations; IsolationForest is the secondary
  "unknown-anomaly" detector, never overriding a confirmed rule hit.
- **Explainability first:** explanations are template-built from real evidence values, never
  hallucinated by the LLM.
- **Different queries produce different plans** — the `plan[]` + `skipped[]` fields in every
  response are the visible proof.

Full detail (architecture diagram, component responsibilities, response contract, rejected
alternatives): see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/AGENT_FLOW.md`](docs/AGENT_FLOW.md).

### Tech stack

**Backend:** Python 3.11 · pandas + pyarrow · scikit-learn (IsolationForest) · Plotly ·
Pydantic · FastAPI (optional API boundary) · Groq (Llama 3.3 70B, free tier) with
Gemini/Ollama as optional fallbacks · pytest

**Frontend:** two interfaces are provided —
- **React + TypeScript** console ("AEGIS") — Vite, Tailwind CSS, React Router, Framer Motion,
  Plotly.js, Axios
- **Streamlit** — a lightweight fallback that calls the agent in-process; fewer moving parts,
  useful if the React/FastAPI integration has issues live

Full rationale for every choice (and what was rejected, and why): see
[`docs/TECH_STACK.md`](docs/TECH_STACK.md).

## Project layout

```
app/            modular monolith (backend)
  config.py       frozen constants + env-driven settings (single source of tunables)
  enums.py        shared enums (ToolName, IntentType, AMLPattern, RiskLevel, ...)
  schemas.py      shared Pydantic models (Understanding, Context, ExecutionPlan, ...)
  interfaces.py   abstract base classes (Tool, Planner, QueryUnderstanding, Explainer)
  agent/          understanding · planner · executor · tool_set (the "brain")
  tools/          data_loader · filter · eda · feature_engineering · aml_patterns ·
                  anomaly · risk_classifier · explainer · recommender · visualizer
  llm/            provider-agnostic LLM client
  response.py     Response Formatter (assembles the final structured response)
frontend/       React + TypeScript console (Vite) — Dashboard, Analyze, Pipeline, Architecture
ui/             streamlit_app.py — lightweight fallback UI, calls the agent in-process
scripts/        generate_synthetic.py — documented synthetic data generator
tests/          18 test files: planner, executor, filter, features, rules, response, etc.
docs/           architecture, tech stack, requirements checklist, and design docs
data/           raw (cited public data) · sample (committed fixture) · synthetic (planted cases)
```

Directory rationale: [`docs/FOLDER_STRUCTURE.md`](docs/FOLDER_STRUCTURE.md).

## Installation

Requires Python 3.11+ and Node 18+ (only if running the React frontend).

```bash
git clone <this-repo-url>
cd <repo-directory>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in a free LLM key:

```bash
cp .env.example .env
# edit .env — set LLM_PROVIDER and LLM_API_KEY
```

All tunables (AML rule thresholds, risk-scoring weights, IsolationForest parameters, paths)
live in `app/config.py` — there are no magic numbers elsewhere in the codebase. Runtime/secret
values (API keys, ports, log level) come from `.env` via `app/config.py::Settings`.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `groq` | `groq` \| `gemini` \| `ollama` |
| `LLM_API_KEY` | — | free API key (blank for local Ollama) |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | model id for the provider |
| `LLM_TIMEOUT_SECONDS` | `8.0` | timeout before keyword-extractor fallback |
| `LLM_MAX_RETRIES` | `1` | retries on the understanding call |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | optional FastAPI boundary |
| `DATASET_PATH` | `data/sample/transactions.parquet` | dataset to analyse |
| `LOG_LEVEL` | `INFO` | logging verbosity |

## Running locally

**Quickest path (Streamlit):**
```bash
./run.sh
# or manually:
streamlit run ui/streamlit_app.py
```

**React console + API:**
```bash
uvicorn app.main:app --reload      # backend, http://localhost:8000
cd frontend && npm install && npm run dev   # frontend, http://localhost:5173
```

**Tests:**
```bash
pytest
```

## Dataset

**Recommended dataset:** [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)
— synthetic bank transfer / credit card / check data generated from a multi-agent virtual
world model covering the full placement → layering → integration cycle, with a laundering
tag on every transaction. Schema and generation methodology documented at
[IBM/AML-Data](https://github.com/IBM/AML-Data) (license: CDLA-Sharing-1.0). Use the
**HI-Small** variant (`HI-Small_Trans.csv` + `HI-Small_Patterns.txt`).

**Current status (documented honestly):** `scripts/generate_synthetic.py` — intended to
generate a documented synthetic dataset with planted, known structuring/smurfing cases for
validation — is scaffolded but not yet implemented. `data/raw/` and `data/synthetic/` are
currently empty; `data/sample/transactions.parquet` is a small (2,056-row), unlabeled
structural test fixture used to exercise the pipeline during development, not a validated
dataset at realistic scale. The IsolationForest and rule thresholds in `app/config.py` are
reasoned defaults and have not yet been calibrated against labeled data.

All datasets used are from public/open sources only; no proprietary or confidential data is
used anywhere in this repository.

## Disclosures (tools / APIs / AI assistance)

- **LLM:** Groq (Llama 3.3 70B, free tier) — used only for query understanding (intent/entity
  extraction) and optional explanation phrasing. It never computes risk scores or builds the
  execution plan.
- **Open-source libraries:** pandas, numpy, pyarrow, scikit-learn, Plotly, Pydantic, FastAPI,
  Streamlit, React, Vite, Tailwind CSS, Framer Motion, React Router, Axios — see
  `requirements.txt` and `frontend/package.json` for exact versions.
- **AI coding assistance** (Claude) was used throughout this project — for architecture design,
  documentation, code implementation, and this README.
- Dataset: IBM Transactions for Anti Money Laundering (AML), Kaggle/IBM Research — see
  [Dataset](#dataset) above for citation and license.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/AGENT_FLOW.md`](docs/AGENT_FLOW.md),
  [`docs/MODULE_BREAKDOWN.md`](docs/MODULE_BREAKDOWN.md) — architecture detail
- [`docs/REQUIREMENTS_CHECKLIST.md`](docs/REQUIREMENTS_CHECKLIST.md) — every hackathon
  requirement mapped to the component that satisfies it
- [`docs/TECH_STACK.md`](docs/TECH_STACK.md) — technology choices and rejected alternatives
- [`docs/SELF_REVIEW.md`](docs/SELF_REVIEW.md) — a self-critique pass on the design

A separate, detailed write-up covering platform architecture, analysis algorithms, and UI
design in full is provided as part of the submission outside this repository.

## License

MIT — see [`LICENSE`](LICENSE).
