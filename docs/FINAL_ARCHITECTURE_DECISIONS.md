# FINAL Architecture Decisions — Single Source of Truth

**Status: FROZEN before implementation.** These decisions must not change during the 48-hour build. If reality forces a change, edit *this* file first and note why — never let code and this document drift. Everything here reflects the pre-implementation panel review (`SELF_REVIEW.md` + the review that produced this file).

Each decision: **ID · Decision · Why · Do-not-do.**

---

## D0 — Problem & scope
- **Decision:** Build only **Problem Statement 1 — AI-Powered Suspicious Activity Detection (AML)**. Batch analysis on a sample dataset. No streaming.
- **Why:** PS1 is the chosen statement; the scope note explicitly permits batch and prioritizes "simplicity, explainability, and a working end-to-end demo over model complexity."
- **Do-not-do:** No live ingestion, no production hardening, no PS2 features.

## D1 — The agent is: **1 LLM call → deterministic planner → deterministic executor**
- **Decision:** Exactly **one LLM call**, for Query Understanding. The Planner and Executor are pure deterministic Python.
- **Why:** The LLM-planner was redundant (the deterministic router was already a full planner) and doubled the live-demo failure surface. Determinism makes the hardest-graded requirement (dynamic-but-correct planning) testable and stable. Explicitly blessed by: *"a deterministic orchestrated pipeline is acceptable if it behaves like an agent and is clearly query-driven."*
- **Do-not-do:** Do NOT let the LLM construct or reorder the plan. Do NOT add a second LLM call to the critical path.

## D2 — Query Understanding contract (the one LLM call)
- **Decision:** Input = query string + dataset schema. Output = validated `Understanding{intent, entities[], filters{}, aml_pattern, needs_eda, confidence}`. Pydantic-validated JSON. 8-second timeout. On failure/malformed/timeout → **keyword-extractor fallback** produces a degraded understanding.
- **intent ∈** `{eda, detect_pattern, threshold_rule, single_entity, compare}`.
- **aml_pattern ∈** `{structuring, smurfing, layering, rapid_cash_out, none}`.
- **Why:** One typed contract lets both developers work independently; the fallback removes the single hard LLM dependency.
- **Do-not-do:** No free-form LLM output consumed downstream; everything passes through the schema.

## D3 — Deterministic planning rules (frozen)
- **Decision:** The plan is a pure function of the understanding:
  - `DataLoader` always first (loads + cleans once).
  - `Filter` iff any filter or entity is present.
  - `EDA` **only** when `intent == eda`.
  - `FeatureEngineering` computes **only** the families the pattern needs.
  - `AMLPatternDetector` runs when a named pattern is present (or all rules for `single_entity`/`eda`).
  - `AnomalyDetector` runs when `intent ∈ {eda}` or `aml_pattern == none` **and** subset size N ≥ 500.
  - `RiskClassifier` + `Explainer` + `Recommender` run whenever any flag is produced.
  - `Visualizer` runs unless the answer is a single scalar.
- **Why:** Deterministic, testable (golden-plan tests), and directly demonstrates selective invocation.
- **Do-not-do:** No tool runs unconditionally "just in case." `skipped[]` must be populated and shown.

## D4 — Tools are a fixed set behind an enum
- **Decision:** `ToolName` enum + `TOOLS: dict[ToolName, Callable]`. Every tool has the signature `run(context, params) -> (context, result, trace_entry)`. Tools tolerate empty input.
- **Why:** Simple, testable, and the enum is the single source of truth for valid tool names (no drift). Uniform signature enables the executor loop and parallel development.
- **Do-not-do:** No decorator registry, no per-tool JSON schemas, no dynamic tool discovery. Over-built for ~11 fixed tools.

## D5 — Tool inventory (final)
`DataLoader(+clean)` · `Filter` · `EDA` · `FeatureEngineering` · `AMLPatternDetector` · `AnomalyDetector` · `RiskClassifier` · `Explainer` · `Recommender` · `Visualizer` · `ResponseFormatter`.
- **Preprocessor is MERGED into DataLoader** (clean once at load). **No standalone Preprocessor tool.**
- **Why:** Minimal, each tool justifies itself; the merge removes a module and a merge point.
- **Do-not-do:** Don't re-split cleaning into its own per-query tool.

## D6 — AML rule thresholds (frozen in `config.py`)
- **structuring:** ≥ **3** cash transactions with amount in **\$8,000–\$9,999**, within a rolling **7-day** window, per customer.
- **smurfing:** one account receiving deposits < **\$3,000** from **≥ 5 distinct sources** within **7 days**.
- **rapid_cash_out:** a withdrawal ≥ **90%** of a deposit, within **24h** of that deposit.
- **layering (P2 only):** ≥ **3-hop** transfer chain draining an account within **72h**.
- **CTR reference line:** **\$10,000** (rationale for "just under" logic).
- **Why:** Concrete, explainable, domain-credible; prevents the two developers from diverging.
- **Do-not-do:** **Do not tune these live during the demo.** Change only in `config.py`, before recording.

## D7 — Risk scoring is a frozen deterministic formula
- **Decision:** `score = min(1.0, 0.6·rule_severity + 0.4·anomaly_score)`, where `rule_severity ∈ {0, 0.5, 0.8, 1.0}` by strongest rule hit and `anomaly_score ∈ [0,1]` (0 if AnomalyDetector didn't run). Bands: `≥0.75 high`, `0.45–0.75 medium`, `<0.45 low`. **A confirmed rule hit floors the band at medium.** Constants calibrated on the sample in Phase 5, then frozen.
- **Why:** Determinism + explainability; avoids the "everything is high" failure and lets the Explainer cite exact contributions.
- **Do-not-do:** No opaque scoring; no per-run randomness in the classifier.

## D8 — Detection is hybrid; rules are primary, ML is secondary
- **Decision:** Deterministic rules (D6) are the headline detector and own the explanations. `IsolationForest(contamination=0.02, random_state=42)` on scaled features is the "ML-based approach," run only when N ≥ 500, and never overrides a clear rule hit.
- **Why:** Rules give auditable, compliance-grade reasons (top-scoring axis); IForest satisfies the ML requirement and catches unknown anomalies cheaply. Fixed seed = reproducible demo.
- **Do-not-do:** No labelled/deep/fine-tuned models. Don't make the demo's headline flags depend on IForest.

## D9 — Explanations are template-first
- **Decision:** P0 explanations are **deterministic templates** built from `rule_id` + evidence values (never hallucinated). LLM phrasing polish is **P1**, constrained to rephrase with the same numbers injected, validated that the numbers survive (else fall back to template).
- **Why:** Explainability is the highest-weighted axis and must be trustworthy; templates can't invent numbers.
- **Do-not-do:** Don't ship LLM-authored numbers. Don't block the demo on LLM narration.

## D10 — Data layer: pandas only
- **Decision:** pandas + parquet. Sample dataset loaded + cleaned once at startup, held in memory. Relative dates ("last 30 days") resolve against the **dataset's max timestamp**, not `today`.
- **Why:** pandas covers filter/groupby/rolling; DuckDB added a second idiom and a dependency for invisible benefit. Relative-date resolution prevents empty demos.
- **Do-not-do:** **No DuckDB, no SQL DB server.** Don't compute "last N days" from the wall clock.

## D11 — Empty results are a first-class state
- **Decision:** Every tool returns cleanly on 0 rows; the response has an explicit "no flags found + why" path (e.g., "0 transactions after the 30-day filter; dataset ends 2023-06-01").
- **Why:** A blank or crashed panel on stage is a demo-killer.
- **Do-not-do:** Don't assume non-empty subsets anywhere.

## D12 — The Response Contract (frozen shape)
- **Decision:** One JSON object: `{query, understanding, plan[], skipped[], results[], charts[], trace[]}` (full shape in `ARCHITECTURE.md §5`). Defined once in `schemas.py` (Pydantic), shared by executor, API, and UI. Each result carries `risk`, `score`, `explanation`, `action`, `evidence`.
- **`plan[]` and `trace[]` are two SEPARATE models — planned intent vs. actual outcome — and must never be merged:**
  - **`ExecutionStep`** (planned): `{ tool: ToolName, reason: str, confidence: float [0..1], inputs: dict }`. `reason` = why the tool was selected; `confidence` = planner confidence (1.0 for deterministic rules, may reflect Understanding confidence for QU-derived decisions); `inputs` = exact params passed to the tool, for debugging / UI visualization only (**not** execution output).
  - **`TraceEntry`** (actual runtime): `{ tool: ToolName, status: "SUCCESS"|"SKIPPED"|"ERROR", rows_in: int, rows_out: int, duration_ms: int }`. Runtime information only.
- **Why:** The `plan` + `skipped` + `trace` fields are the deliverable "what the agent decided and why" — the judge-facing centerpiece and the proof of "not a fixed pipeline." Separating planned `ExecutionStep` from actual `TraceEntry` keeps intent auditable independently of outcome.
- **Do-not-do:** No parallel/duplicate response shapes. Do NOT fold runtime fields into `ExecutionStep` or planning fields into `TraceEntry`. UI reads only this object.

## D13 — Frontend: Streamlit, in-process by default
- **Decision:** Streamlit calls the agent **in-process**. FastAPI (`/analyze`) is **optional**, built only if the React stretch happens. UI shows: query box, example buttons, plan/skipped panel, results table with risk badges, expandable explanations, charts, trace.
- **Why:** Fewer moving parts live; fastest path to a strong data+chat+chart demo.
- **Do-not-do:** Don't run two servers for the demo. Don't spend day-1 hours on custom React.

## D14 — Demo safety: flagship example buttons carry pre-parsed understanding
- **Decision:** The three canonical queries (structuring/30d, 10+ under \$10k, customer 4521) ship with hardcoded `Understanding`, so they route correctly with the LLM fully offline.
- **Why:** Guarantees the recorded demo and Round-2 live demo never hard-fail on an API hiccup.
- **Do-not-do:** Don't let the flagship demo depend on a live API call.

## D15 — Dataset: synthetic generator (planted cases) + cited public dataset
- **Decision:** Ship a documented synthetic generator that seeds known structuring/smurfing customers (guaranteed explainable positives), alongside a cited public AML dataset. Schema, assumptions, generation logic documented in README.
- **Why:** Planted cases de-risk the demo; a real dataset adds credibility. Required by rules G5/G6/G7.
- **Do-not-do:** No proprietary/copyrighted data. Don't rely solely on a real dataset whose positives you can't guarantee.

## D16 — LLM provider is swappable, free-tier, offline-capable
- **Decision:** `llm/client.py` interface; **Groq Llama 3.3 70B** primary, Gemini Flash + local **Ollama** fallbacks. Keys via `.env` (gitignored); `.env.example` committed.
- **Why:** Free (rules permit), fast, reproducible for judges, offline-capable.
- **Do-not-do:** Don't require a paid key to run the repo. Don't commit secrets.

## D17 — Team split & shared-file discipline
- **Decision:** Dev A = agent core (understanding, planner, executor, tool-set wiring, response formatter, UI). Dev B = data + tools + ML. **`schemas.py` and `config.py` are frozen in Phase 0**; changes to them require a quick sync. Tool wiring lives in one `tool_set.py` dict Dev B owns; executor iterates plan-by-name so it needn't change per tool.
- **Why:** Removes the main merge-conflict hotspots; enables late integration.
- **Do-not-do:** Don't edit shared contract files unilaterally mid-build.

## D18 — Testing floor (must stay green)
- **Decision:** `test_planner.py` (5 example queries → expected tools + `skipped[]`), `test_rules.py` (crafted structuring/smurfing fixtures), `test_features.py` (rolling/velocity/z-score), `test_end_to_end.py` (response shape + empty-result path).
- **Why:** These prove the two highest-scoring requirements (dynamic planning + explainable detection) and catch regressions cheaply.
- **Do-not-do:** Don't merge with `test_planner.py` red.

## D19 — Compliance guardrails (non-negotiable)
- **Decision:** Public GitHub repo from hour 0, frequent commits, MIT license, one-command setup, README with dataset citations + tool/AI disclosures. **Zero** "SG / Societe Generale / SocGen / SGGSC" references anywhere. Individual contributions traceable via commits.
- **Why:** Direct submission rules G1–G14; violating any is disqualifying.
- **Do-not-do:** No banned references. No un-cited data. No private repo.

## D20 — Explicitly NOT building (guard against scope creep)
Streaming, microservices, Kafka/Spark/Airflow/K8s, custom/fine-tuned/deep models, LangGraph/LangChain, DuckDB/SQL server, a from-scratch React UI (unless far ahead), SHAP-everywhere, an analyst feedback-learning loop.
- **Why:** Each is high effort/risk and satisfies no requirement the frozen design doesn't already meet.
- **Do-not-do:** Don't add any of these without editing D20 and justifying it against the clock.

---

### Change log
- **v1 (pre-implementation):** Removed LLM-planner (→ deterministic), removed DuckDB (→ pandas), merged Preprocessor into DataLoader, simplified registry (→ enum+dict), pinned rule thresholds (D6) + risk formula (D7), made explanations template-first (D9), added empty-result state (D11) + offline example buttons (D14), defaulted Streamlit in-process (D13).
- **v1.1 (pre-skeleton refinement):** D12 only — enriched `ExecutionStep` to `{tool, reason, confidence, inputs}` and kept `TraceEntry` (`{tool, status, rows_in, rows_out, duration_ms}`) as a strictly separate runtime model. No architectural, technology, module, or planning-logic changes.
