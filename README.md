# AI-Powered Suspicious Activity Detection

An agentic AML (Anti-Money Laundering) analysis system. A user asks a natural-language
question about transaction data; the agent **understands** the query, **plans a different
tool path for each question**, executes only the tools it needs, and returns explainable,
evidence-grounded risk flags with escalation recommendations — plus a visible trace of
*what it decided and why*.

> Built for a 48-hour campus hackathon (Problem Statement 1). Architecture is frozen —
> see [`docs/FINAL_ARCHITECTURE_DECISIONS.md`](docs/FINAL_ARCHITECTURE_DECISIONS.md).
> This repository currently contains the **production-quality foundation** (structure,
> config, shared models, enums, interfaces). Business logic is implemented in later phases
> (see the roadmap below).

---

## Problem statement

Traditional rule-based AML systems drown compliance teams in false positives while
sophisticated techniques (structuring, smurfing, layering) slip through. The goal is an
autonomous agent that learns baseline behaviour, detects suspicious patterns, produces
explainable risk assessments, and recommends an escalation action (monitor / review / report).

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
  understanding. Planning and execution are pure, deterministic, and testable.
- **Hybrid detection:** deterministic AML rules (structuring / smurfing / rapid cash-out)
  are primary and own the explanations; IsolationForest is the secondary "unknown-anomaly"
  detector.
- **Explainability first:** explanations are template-built from real evidence values, never
  hallucinated.
- **Different queries produce different plans** — the `plan[]` + `skipped[]` fields prove the
  system is not a fixed pipeline.

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/AGENT_FLOW.md`](docs/AGENT_FLOW.md).

### Tech stack
Python 3.11 · pandas + pyarrow · scikit-learn · Plotly · Streamlit · FastAPI (optional) ·
Pydantic · Groq (Llama 3.3 70B, free tier) with Gemini/Ollama fallbacks · pytest.
Rationale + rejected alternatives: [`docs/TECH_STACK.md`](docs/TECH_STACK.md).

## Project layout

```
app/            modular monolith
  config.py       frozen constants + env-driven settings (single source of tunables)
  enums.py        shared enums (ToolName, IntentType, AMLPattern, RiskLevel, ...)
  schemas.py      shared Pydantic models (Understanding, Context, ExecutionPlan, ...)
  interfaces.py   abstract base classes (Tool, Planner, QueryUnderstanding, Explainer)
  agent/          understanding · planner · executor · tool_set (the "brain")
  tools/          data_loader · filter · eda · feature_engineering · aml_patterns ·
                  anomaly · risk_classifier · explainer · recommender · visualizer
  llm/            provider-agnostic LLM client
  response.py     Response Formatter (assembles the final structured response)
ui/             streamlit_app.py (calls the agent in-process)
scripts/        generate_synthetic.py (documented synthetic data generator)
tests/          golden-plan / rules / features / end-to-end
data/           raw (cited public data) · sample (committed) · synthetic (planted cases)
```
Directory rationale: [`docs/FOLDER_STRUCTURE.md`](docs/FOLDER_STRUCTURE.md).

## Installation

Requires Python 3.11+.

```bash
git clone <this-repo-url>
cd soc-hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in a free LLM key:

```bash
cp .env.example .env
# edit .env — set LLM_PROVIDER and LLM_API_KEY
```

All tunables live in `app/config.py` (thresholds, IsolationForest params, risk formula,
paths). Runtime/secret values come from `.env` via `app/config.py::Settings`.

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

```bash
./run.sh
# or manually:
streamlit run ui/streamlit_app.py
```

The optional API (only needed for a custom frontend) will run via:

```bash
uvicorn app.main:app --reload
```

Run the tests:

```bash
pytest
```

## Implementation roadmap

Phased plan in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). Current status:

- [x] **Phase 0** — Project foundation: structure, config, shared models, enums, interfaces *(this commit)*
- [ ] **Phase 1** — Vertical slice (deterministic path, no LLM/ML): DataLoader → Filter → FeatureEngineering (aggregation) → AMLPatternDetector (threshold) → RiskClassifier → Recommender → minimal UI
- [ ] **Phase 2** — Feature engineering + AML rule engine (structuring / smurfing / rapid cash-out)
- [ ] **Phase 3** — LLM Query Understanding + keyword fallback + flagship example buttons
- [ ] **Phase 4** — EDA, IsolationForest anomaly detection, Explainer, Visualizer
- [ ] **Phase 5** — Calibration, empty-result hardening, README polish
- [ ] **Phase 6** — Deck, 2-minute video, deployment

## Data sources

The synthetic generator (`scripts/generate_synthetic.py`) produces documented transaction
data with planted, explainable AML cases. Any public dataset used (e.g. Kaggle AML
transaction datasets) will be **cited here with its source and license** before use.
_TODO: add dataset citations + synthetic schema/assumptions when the data layer lands (D15)._

## Disclosures (tools / APIs / AI assistance)

- **LLM:** Groq (Llama 3.3 70B), used only for query understanding and optional explanation
  phrasing — never for computing risk numbers.
- **AI coding assistance** was used to scaffold and plan this repository.
- _All external APIs and datasets will be listed here per hackathon rules._

## License

MIT — see [`LICENSE`](LICENSE).
