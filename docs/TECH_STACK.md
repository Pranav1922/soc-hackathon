# Tech Stack — Choices & Rejections

Rule: **every technology must earn its place.** No tech is added for résumé value. Chosen for a 2-person, 48-hour build optimizing demo + explainability.

---

## Frontend — **Streamlit**
- **Why:** Fastest way to ship chat + data tables + interactive charts in one file, in Python (same language as the agent). Free hosting on Streamlit Community Cloud. Screenshots/records cleanly for the 2-min video.
- **Rejected:**
  - *React/Next.js* — better-looking, but ~1 day of extra work for a demo-only UI. Kept as a **stretch goal**.
  - *Gradio* — great for single-model demos, weaker for multi-panel dashboards (trace + table + charts).
  - *Dash* — more boilerplate than Streamlit for the same result.

## Backend — **FastAPI**
- **Why:** Typed, async, auto-generated `/docs`, trivial JSON endpoints, integrates with Pydantic (which we already use for plan/understanding schemas). Makes the "API interaction" requirement explicit.
- **Rejected:**
  - *Flask* — fine, but no native async / typed request models; more manual validation.
  - *Django* — ORM/admin/migrations we don't need; heavy for one endpoint.

## Data layer — **pandas + Parquet** *(DuckDB removed post-review)*
- **Why:** pandas does all of it — filtering, groupbys, rolling-window feature math. The "10+ transactions under \$10,000" aggregation is a one-line `groupby().agg()` — equally correct, and judges won't read the query engine. Parquet for a compact sample dataset.
- **DuckDB removed:** it added a second data idiom (SQL vs pandas) across two developers for a marginal, invisible benefit. Cutting it removes a dependency and a merge point with zero requirement loss.
- **Rejected:**
  - *DuckDB* — see above; nice tool, wrong ROI here.
  - *PostgreSQL/MySQL* — needs a server + schema migrations; batch analysis on a sample file doesn't need a DB server.
  - *SQLite/Spark* — a server / cluster we don't need; scope note says batch on a sample is enough.

## Agent framework — **Custom thin orchestrator (no heavy framework)**
- **Why:** The understanding→(deterministic)planner→executor loop is ~150 lines and we need full control over the plan and the trace (our headline artifact). A custom layer keeps reasoning *visible*, which frameworks hide. With planning deterministic, there is even less reason for a framework.
- **Rejected:**
  - *LangChain / LangGraph* — powerful but heavy; autonomous loops are flaky on stage and obscure the reasoning we want to showcase; framework churn costs debugging hours. (Full rationale in `ARCHITECTURE.md §8`.)
  - *CrewAI / AutoGen* — multi-agent framing adds coordination overhead with no requirement demanding it.

## LLM — **Groq API · Llama 3.3 70B (free tier)** (primary)
- **Why:** Free, and Groq's inference is extremely fast → low demo latency. Good at JSON-structured output for our understanding schema. Used for **exactly one call (Query Understanding)** plus optional explanation phrasing (P1) — never for computing numbers and never for constructing the plan.
- **Backup / alternatives:** Google Gemini 1.5/2.0 Flash (generous free tier) and a **local Ollama (Llama 3.1 8B)** fallback so the demo works offline. Config-swappable provider.
- **Rejected:**
  - *Paid OpenAI/Anthropic as the required dependency* — the rules allow free APIs; we shouldn't require a paid key to run the repo (hurts reproducibility for judges).
- **Note:** Model IDs / provider config are documented in the README; the LLM is behind a small `llm_client` interface so any provider slots in.

## ML libraries — **scikit-learn (IsolationForest) + numpy**
- **Why:** IsolationForest is unsupervised (no labels needed — realistic for AML), 5 lines to fit/predict, well understood, easy to explain via feature deviation. numpy/pandas for feature math.
- **Optional add:** *PyOD* for a second detector (LOF) as an ensemble — P2 stretch.
- **Rejected:**
  - *XGBoost/deep models* — need labels + tuning time; the scope note explicitly deprioritizes model complexity.
  - *TensorFlow/PyTorch* — no justification at this scale; heavy install.
  - *Graph ML (PyG) for layering* — attractive but a rabbit hole; a pandas self-join demonstrates layering for the demo.

## Visualization — **Plotly**
- **Why:** Interactive, embeds natively in Streamlit, exports clean images for the deck/video. One library covers timelines, histograms, bar charts.
- **Rejected:**
  - *matplotlib/seaborn* — static; fine for EDA thumbnails but Plotly is more demo-friendly (kept only if a quick static chart is faster somewhere).
  - *D3.js* — enormous effort for marginal benefit in 48h.

## Explainability — **Rule-evidence templates + LLM narration (+ optional feature attribution)**
- **Why:** Deterministic templates own all facts/numbers (auditable, never hallucinated); the LLM only rephrases into fluent English. For ML flags, per-feature deviation gives "which feature made this anomalous."
- **Optional add:** *SHAP* on the IsolationForest for richer attributions — P2 stretch (SHAP can be slow/fiddly, so it's not on the critical path).
- **Rejected as required:** SHAP-only explanations — too slow/fragile to depend on live; and rules give clearer compliance-grade reasons.

## Validation / schemas — **Pydantic**
- **Why:** Enforces the `Understanding` and `ExecutionPlan` JSON contracts, turning "LLM returned junk" into a caught error → fallback. Already ships with FastAPI.

## Testing — **pytest**
- **Why:** Golden-plan tests (query → expected tool plan) are the cheapest proof of the "dynamic, not fixed pipeline" requirement. Plus unit tests for rule detectors on crafted structuring cases.
- **Rejected:** heavier test frameworks — unnecessary.

## Deployment — **Streamlit Community Cloud / Hugging Face Spaces / local `run` script**
- **Why:** Free, one-command, publicly shareable link for judges; local run for the offline fallback.
- **Rejected:**
  - *Docker/Kubernetes* — a Dockerfile is a nice-to-have for reproducibility (P2), but K8s/orchestration is pure over-engineering here.
  - *AWS/GCP paid infra* — no need; free tiers cover it.

## Dev tooling — **uv or pip + `requirements.txt`, ruff (lint), python-dotenv (keys)**
- **Why:** Fast reproducible installs, one-command setup (a G2 requirement), secrets out of the repo.

---

## One-glance summary

| Concern | Pick | Runner-up rejected because |
|---|---|---|
| Frontend | Streamlit | React = +1 day for demo-only UI |
| Backend | FastAPI | Flask = no typed/async |
| Data | pandas + parquet | DuckDB/Postgres = needless surface/server |
| Agent | Custom orchestrator, **deterministic planner** | LangGraph = flaky + opaque |
| LLM | Groq Llama 3.3 70B (free), **1 call** | Paid API hurts reproducibility |
| ML | sklearn IsolationForest | XGBoost/DL = needs labels/time |
| Viz | Plotly | D3 = huge effort |
| Explain | Templates + LLM | SHAP-only = slow/fragile live |
| Test | pytest | — |
| Deploy | Streamlit Cloud / HF / local | K8s = over-engineering |
