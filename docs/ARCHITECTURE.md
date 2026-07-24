# Architecture — AI-Powered Suspicious Activity Detection

## 1. Guiding principle

The single hardest, most-evaluated requirement is: **the agent must not be a fixed pipeline; different queries must produce different execution plans.** Everything below is organized so that this property is *visible* to a judge, not just claimed.

Second principle (straight from the scope note): **"Simplicity, explainability, and a working end-to-end demo are more important than model complexity."** We optimize for that, not for a production AML stack.

## 2. High-level architecture

A **modular monolith**: one Python process, one deployable, clean module boundaries. The "agent" makes **exactly one LLM call** — to extract a structured *understanding* of the query. A **deterministic planner** maps that understanding to an execution plan over a fixed tool set, and a **deterministic executor** runs only the selected tools, threading a shared context between them. The LLM never touches data, math, or plan construction.

> **Post-review update:** the earlier "LLM proposes the plan → validate → repair → fallback" loop was removed. The fallback router was already a complete planner, so the LLM-planner was redundant and doubled the live-demo failure surface. Planning is now 100% deterministic (see `FINAL_ARCHITECTURE_DECISIONS.md`, D1–D3). This is explicitly permitted: *"a deterministic orchestrated pipeline is acceptable if it behaves like an agent and is clearly query-driven."*

```
                            ┌──────────────────────────────────────────────┐
                            │                 FRONTEND (Streamlit)           │
                            │  chat box · agent trace panel · results · viz  │
                            └───────────────┬───────────────▲────────────────┘
                                            │ query          │ structured response
                                            ▼                │
                            ┌───────────────────────────────────────────────┐
                            │                BACKEND (FastAPI)               │
                            │                                                │
                            │   ┌──────────────────────────────────────┐    │
                            │   │            AGENT CORE                 │    │
   free LLM API ◀───────────┼──▶│  1. Query Understanding (LLM, 1 call) │    │
   (Groq Llama 3.3 70B)     │   │     intent/entities/filters/pattern   │    │
                            │   │  2. Planner (DETERMINISTIC) → plan    │    │
                            │   │  3. Orchestrator / Executor           │    │
                            │   └───────────────┬──────────────────────┘    │
                            │                   │ calls selected tools only  │
                            │                   ▼                            │
                            │   ┌──────────────────────────────────────┐    │
                            │   │        TOOL SET (plain dict)          │    │
                            │   │  DataLoader(+clean) · Filter          │    │
                            │   │  EDA · FeatureEngineering             │    │
                            │   │  AMLPatternDetector · AnomalyDetector │    │
                            │   │  RiskClassifier · Explainer           │    │
                            │   │  Recommender · Visualizer             │    │
                            │   └───────────────┬──────────────────────┘    │
                            │                   ▼                            │
                            │   ┌──────────────────────────────────────┐    │
                            │   │   DATA LAYER                          │    │
                            │   │   pandas (filter/groupby/rolling) +   │    │
                            │   │   parquet/CSV sample dataset          │    │
                            │   │   (loaded + cleaned once at startup)  │    │
                            │   └──────────────────────────────────────┘    │
                            │                   │                            │
                            │                   ▼                            │
                            │        Response Formatter → structured JSON    │
                            └───────────────────────────────────────────────┘
```

## 3. Component responsibilities

| Component | Responsibility (one line) |
|-----------|---------------------------|
| **Query Understanding (QU)** | LLM call → structured `{intent, entities, filters, aml_pattern, needs_eda}`. |
| **Planner (PL)** | **Deterministic** pure-Python mapping of understanding → ordered `ExecutionPlan`, choosing *only* the tools the query needs, and populating each step's `why`. No LLM. |
| **Orchestrator / Executor (EX)** | Runs plan steps in order, passes a shared `Context` (dataframe handle, features, flags) between tools, records a step-by-step **trace**. |
| **Tool Set** | Plain dict `{ToolName: callable}` + a `ToolName` enum. The Planner may only emit names in the enum. (No decorators/schemas — over-built for ~11 fixed tools.) |
| **DataLoader (DL)** | Loads the sample dataset into pandas **and cleans once at load** (dtype coercion, timestamp parsing, dedupe, derived `date`/`hour`); exposes schema + dataset max timestamp for relative-date resolution. Absorbs the former Preprocessor. |
| **Filter (FIL)** | Applies date range / segment / country / txn-type / entity-ID filters → subset. |
| **EDA (EDA)** | Profiling stats + baseline distributions; invoked only when the plan asks. |
| **FeatureEngineering (FE)** | AML features on demand: frequency, rolling sums, amount deviation (z-score), velocity, rapid cash-out. |
| **AMLPatternDetector (AML)** | Deterministic rules for structuring/smurfing/layering (threshold + sub-threshold clustering). |
| **AnomalyDetector (AD)** | IsolationForest (unsupervised) over engineered features → anomaly score. |
| **RiskClassifier (RC)** | Fuses rule hits + anomaly score → low/med/high with context-appropriate thresholds. |
| **Explainer (XP)** | Per-flag natural-language reason, tied to query intent + triggering feature/rule. |
| **Recommender (REC)** | Maps risk level → monitor / review / report. |
| **Visualizer (VIZ)** | Plotly charts (timeline, amount histogram vs threshold, feature contributions). |
| **Response Formatter (RESP)** | Assembles the single structured response object (below). |

## 4. Data flow (happy path)

1. User types a query in the UI → `POST /analyze`.
2. **QU** extracts intent/entities/filters/pattern (one LLM call, JSON output).
3. **PL** deterministically builds an `ExecutionPlan` from the understanding (no LLM). If Understanding itself failed, a keyword extractor supplies a degraded understanding first.
4. **EX** runs each step, threading `Context`; unselected tools never execute. Every tool tolerates an **empty subset** and returns a clean "no results" state rather than erroring.
5. Tools write results + a `TraceEntry` (`tool`, `status`, `rows_in/out`, `duration_ms`) — runtime facts, distinct from the planned `ExecutionStep`.
6. **RESP** returns one JSON object; UI renders trace, table, explanations, charts.

## 5. The response contract (single most important artifact)

```jsonc
{
  "query": "Find structuring patterns in the last 30 days",
  "understanding": {
    "intent": "detect_pattern",
    "aml_pattern": "structuring",
    "filters": { "date_range": { "last_days": 30 } },
    "entities": []
  },
  // plan[] = ExecutionStep: what the planner DECIDED (tool, reason, confidence, inputs)
  "plan": [
    { "tool": "DataLoader",         "reason": "Load the transaction dataset",                 "confidence": 1.0,  "inputs": {} },
    { "tool": "Filter",             "reason": "Restrict to transactions from the last 30 days","confidence": 0.98, "inputs": { "date_range": "last_30_days" } },
    { "tool": "FeatureEngineering", "reason": "Build structuring-specific features only",       "confidence": 0.95, "inputs": { "families": ["sub_threshold", "rolling_sum"] } },
    { "tool": "AMLPatternDetector", "reason": "Apply the structuring rule set",                 "confidence": 0.97, "inputs": { "patterns": ["structuring"] } },
    { "tool": "RiskClassifier",     "reason": "Score the flagged accounts",                     "confidence": 1.0,  "inputs": {} },
    { "tool": "Explainer",          "reason": "Generate a reason per flag",                     "confidence": 1.0,  "inputs": {} },
    { "tool": "Recommender",        "reason": "Recommend an escalation action",                 "confidence": 1.0,  "inputs": {} }
  ],
  "skipped": ["EDA", "AnomalyDetector"],
  "results": [
    { "entity_id": "C4521", "risk": "high", "score": 0.91,
      "explanation": "6 cash deposits of $9,200–$9,800 within 4 days, all below the $10,000 CTR threshold (structuring).",
      "action": "report", "evidence": { "txn_ids": ["..."], "rule": "sub_threshold_clustering" } }
  ],
  "charts": [ { "type": "timeline", "spec": "..." } ],
  // trace[] = TraceEntry: what ACTUALLY happened at runtime (status + row counts + timing)
  "trace": [ { "tool": "Filter", "status": "SUCCESS", "rows_in": 100000, "rows_out": 8421, "duration_ms": 12 } ]
}
```

The `plan` + `skipped` fields are what prove "not a fixed pipeline" at a glance — this is the judge-facing centerpiece.

**`plan[]` and `trace[]` are two distinct models — planned intent vs. actual outcome — and must stay separate:**

- **`ExecutionStep`** (planned) — `{ tool: ToolName, reason: str, confidence: float [0..1], inputs: dict }`.
  `reason` = human-readable justification for selecting the tool. `confidence` = planner's confidence (1.0 for deterministic rules; may reflect the Understanding confidence for QU-derived decisions). `inputs` = the exact params the tool will receive (for debugging / UI display — **not** execution output).
- **`TraceEntry`** (actual) — `{ tool: ToolName, status: "SUCCESS" | "SKIPPED" | "ERROR", rows_in: int, rows_out: int, duration_ms: int }`. Runtime information only.

## 6. Technology choices (summary; full justification in `TECH_STACK.md`)

| Layer | Choice | One-line reason |
|-------|--------|-----------------|
| Language | Python 3.11 | ML + data + web in one language. |
| Backend | FastAPI | Async, typed, trivial JSON APIs, auto docs. |
| Frontend | Streamlit | Fastest path to a data+chat+chart demo in 48h. |
| Agent brain | Groq API, Llama 3.3 70B (free tier) | One call: query→understanding JSON. Fast, free, good JSON adherence. Keyword fallback if it fails. |
| Data | pandas + parquet | pandas covers filter/groupby/rolling. **DuckDB removed** post-review: `groupby().agg()` is equally correct, and a second data idiom across two devs wasn't worth the surface. |
| ML | scikit-learn IsolationForest | Unsupervised, no labels needed, 5-line fit/predict. |
| Rules | Plain Python | Structuring/smurfing rules are transparent + explainable. |
| Viz | Plotly | Interactive, embeds in Streamlit, screenshots well. |
| Explanation | Templated + LLM narration | Deterministic core + fluent phrasing. |
| Tests | pytest | Golden-plan tests prove routing per query. |
| Deploy | Streamlit Community Cloud / HF Spaces / local | Free, one-command. |

## 7. Design decisions

1. **LLM understands, code plans and executes.** The single LLM call produces only a structured understanding; the deterministic planner and executor do everything else. This kills hallucinated numbers *and* hallucinated plans, keeping every result reproducible and explainable (the top evaluated axis).
2. **Tool set as a hard boundary.** The planner can only emit names in the `ToolName` enum; nothing else can run. Reliability for a live demo.
2b. **Empty results are a first-class state**, not an error — every tool returns cleanly on 0 rows, and relative dates ("last 30 days") resolve against the dataset's max timestamp, never `today`.
2c. **Flagship example-query buttons carry pre-parsed understanding**, so the three demo queries run correctly even with the LLM fully offline.
3. **Hybrid detection by design.** Rules catch the *named* patterns (structuring/smurfing) with crisp explanations; IsolationForest catches the *unknown* anomalies. The requirement explicitly allows "hybrid" — we use it as a feature, not a hedge.
4. **Planning is always deterministic; only Understanding can need a fallback.** If the LLM is rate-limited/offline, a keyword extractor produces a degraded understanding and the deterministic planner proceeds unchanged. Single point of LLM failure, cleanly contained. Demo never dies.
5. **Trace is a first-class output**, not a debug log. It *is* the deliverable "what the agent decided and why."
6. **One process.** No message brokers, no containers-of-containers. A `/analyze` call is synchronous and returns in seconds on a sample dataset.

## 8. Alternatives considered & rejected

**Architecture A — LLM-Planner + Deterministic Executor (CHOSEN).**
Real agentic planning, but execution is deterministic and demo-safe. Best balance of judge appeal, explainability, and 48h feasibility.

**Architecture B — Pure rule/keyword router (no LLM planning).**
*Rejected as the primary design* because it reads as scripted and undersells "agentic" — but **retained as the fallback layer** inside A. Cheap and reliable; not impressive alone.

**Architecture C — Fully autonomous agent framework (LangGraph / LangChain tool-calling loop).**
*Rejected.* It maximizes buzzword density but: (a) autonomous multi-turn tool loops are flaky live and hard to make land in a 2-minute video; (b) hidden reasoning *reduces* explainability, our highest-scoring axis; (c) framework overhead costs hours we don't have; (d) it satisfies no requirement that A doesn't already satisfy more controllably. Autonomy we don't need is risk we can't afford.

**Also rejected outright (over-engineering for 48h):** Kafka/streaming (scope note says batch is fine), microservices (one team, one process), a graph database for layering (a pandas self-join covers the demo), a fine-tuned/custom model (labels + time we don't have; IsolationForest + rules is enough), Kubernetes/Airflow (nothing to schedule).

## 9. Why this fits a 48-hour, 2-person hackathon

- **Parallelizable:** Dev A owns Agent Core (QU/PL/EX + UI); Dev B owns Tools + Data + ML. The tool registry contract lets them work independently and integrate late.
- **Every module is independently testable** — a tool is a pure function `(context, params) -> (context, result)`.
- **Vertical slice on day 1:** loader → filter → rule detector → classifier → response gives a working demo before any LLM/ML is added, so there is always something to show.
- **No infra rabbit holes.** Free APIs, free hosting, local-runnable.

## 10. Trade-offs accepted

| Trade-off | Why it's acceptable here |
|-----------|--------------------------|
| Streamlit UI (less custom than React) | Saves ~a day; demo quality is high enough; React is a stretch goal. |
| IsolationForest over SHAP-heavy models | Explanation comes mainly from rules + feature attribution; SHAP is a stretch. |
| Batch, not streaming | The problem statement explicitly says batch is sufficient. |
| LLM can occasionally misplan | Schema validation + deterministic fallback contain the blast radius. |
| Single process, in-memory | Sample dataset fits in RAM; no persistence needed for a demo. |

## 11. Why judges will appreciate this design

- The **agent decision trace** directly answers "show what the agent decided and why" — most teams will only show final flags.
- **Three different queries visibly produce three different plans** in the demo — the exact behavior the rubric rewards.
- **Rule-based explanations are auditable** ("6 deposits of \$9.2k–\$9.8k under the \$10k CTR line") — compliance-credible, not a black box.
- It's **obviously runnable and honest** — code computes the numbers, the LLM only routes and narrates.
