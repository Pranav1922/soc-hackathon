# Module Breakdown

Every module. Each tool is a pure-ish function `run(context, params) -> (context, result, trace_entry)` so it is independently testable. Priority: **P0** = demo-critical, **P1** = important, **P2** = stretch. Time estimates assume a 2-person team, and are per-module (not wall-clock).

---

## 1. Query Understanding (QU)
- **Purpose:** Turn NL query into a structured understanding.
- **Responsibilities:** One LLM call with a strict JSON schema; extract intent, entities, filters, AML pattern, `needs_eda`, confidence.
- **Inputs:** raw query string, dataset schema (column names/types).
- **Outputs:** `Understanding{intent, entities[], filters{}, aml_pattern, confidence}`.
- **Internal logic:** System prompt with the tool catalog + few-shot examples of the 3 canonical queries; `response_format=json`; validate with Pydantic; on parse failure → keyword extractor.
- **Dependencies:** LLM client, Pydantic.
- **Complexity:** Medium.
- **Est. dev time:** 4–5h.
- **Priority:** P0.
- **Risks:** LLM returns malformed JSON / wrong intent → mitigated by schema validation + fallback + few-shot.
- **Future:** confidence-calibrated clarifying questions; multilingual queries.

## 2. Planner (PL)  — *deterministic (post-review change)*
- **Purpose:** Convert understanding → ordered `ExecutionPlan` of tool steps.
- **Responsibilities:** Choose which tools, in what order, on which subset; produce `skipped[]` and each step's `why`.
- **Inputs:** `Understanding`, `ToolName` enum.
- **Outputs:** `ExecutionPlan{steps:[{tool, params, why}], skipped[]}`.
- **Internal logic:** **Pure-Python mapping, no LLM.** A small rule set on `intent`/`aml_pattern`/`filters`/`entities` (see `AGENT_FLOW.md §2` and `FINAL_ARCHITECTURE_DECISIONS.md` D1–D3) assembles the step list. Deterministic → identical every run.
- **Dependencies:** QU output, `ToolName` enum.
- **Complexity:** Low-Medium (dropped from Med-High once the LLM was removed).
- **Est. dev time:** 3–4h (was 6–8h).
- **Priority:** P0.
- **Risks:** Over/under-selecting tools → fully covered by golden-plan tests, which now *always pass deterministically*.
- **Future:** re-planning after a tool returns empty; optional LLM "explain my plan" narration for wow (does not construct the plan).

## 3. Orchestrator / Executor (EX)
- **Purpose:** Run the plan, thread context, record trace.
- **Responsibilities:** Sequential step execution; shared `Context`; per-step timing/rowcounts; error isolation.
- **Inputs:** `ExecutionPlan`, `Context`.
- **Outputs:** enriched `Context`, `trace[]`.
- **Internal logic:** for step in plan → `tool.run(ctx, params)`; catch tool error → record + continue with degraded result.
- **Dependencies:** Tool Registry.
- **Complexity:** Low-Medium.
- **Est. dev time:** 3–4h.
- **Priority:** P0.
- **Risks:** one tool failure poisoning the run → per-step try/except.
- **Future:** parallel independent steps; caching by (tool, params).

## 4. Tool Set  — *simplified (post-review change)*
- **Purpose:** The fixed set of callables the deterministic planner may reference.
- **Responsibilities:** map `ToolName` → callable.
- **Inputs:** n/a (module init).
- **Outputs:** `TOOLS: dict[ToolName, Callable]` + a `ToolName` enum.
- **Internal logic:** a plain dict. No decorators, no per-tool schemas, no prompt serialization — those existed to serve an LLM planner that no longer exists.
- **Complexity:** Trivial.
- **Est. dev time:** 0.5h (was 2h).
- **Priority:** P0.
- **Risks:** none material — the enum is the single source of truth for valid tool names.

## 5. DataLoader (DL)
- **Purpose:** Load the sample dataset.
- **Responsibilities:** read parquet/CSV → DuckDB table + pandas handle; expose schema; cache.
- **Inputs:** dataset path.
- **Outputs:** `Context.df`, `Context.duckdb_con`, schema.
- **Internal logic:** load once at startup, keep in memory.
- **Dependencies:** DuckDB, pandas.
- **Complexity:** Low.
- **Est. dev time:** 2h.
- **Priority:** P0.
- **Risks:** dataset too big for RAM → sample to N rows at load.

## 6. ~~Preprocessor~~ — *MERGED into DataLoader (post-review change)*
The cleaning (dtype coercion, timestamp parsing, dedupe, derived `date`/`hour`) is minimal and query-independent, so it runs **once at load** inside DataLoader instead of as a separate per-query tool. Removing it deletes a module and a two-developer merge point for near-zero logic. Requirement **B2** ("apply only preprocessing relevant to the query") is still satisfied — there is barely any preprocessing to be selective about, and no irrelevant preprocessing runs. `schema_map` lives in `config.py` and handles dataset-column differences.

## 7. Filter (FIL)
- **Purpose:** Reduce to the query's subset.
- **Responsibilities:** apply date range, segment, country, txn type, amount bounds, entity ID.
- **Inputs:** df, `filters`, `entities`.
- **Outputs:** filtered df + `rows_in/out`.
- **Internal logic:** translate filters → DuckDB WHERE / pandas mask.
- **Complexity:** Low-Medium.
- **Est. dev time:** 3h.
- **Priority:** P0.
- **Risks:** date parsing ("last 30 days" relative to dataset max date, not today) → resolve against dataset max timestamp; document this.

## 8. EDA Tool (EDA)
- **Purpose:** Baseline profiling + distributions, on demand.
- **Responsibilities:** row/null counts, amount distribution, txn/day, top countries, class balance if labeled.
- **Inputs:** df (usually unfiltered).
- **Outputs:** stats dict + chart specs.
- **Internal logic:** pandas `describe`, groupbys; Plotly specs.
- **Complexity:** Low-Medium.
- **Est. dev time:** 3–4h.
- **Priority:** P1 (mandatory feature, but only one plan uses it).
- **Risks:** becoming a time sink → cap to ~5 profile charts.
- **Future:** ydata-profiling as a one-click deep report (stretch).

## 9. Feature Engineering (FE)
- **Purpose:** Build AML features on demand.
- **Responsibilities:** frequency, rolling sums (windowed), amount deviation (per-customer z-score), velocity (txns/time), rapid cash-out (deposit→withdraw within Δt), sub-threshold count (amount just under \$10k).
- **Inputs:** filtered df, requested feature families.
- **Outputs:** feature table keyed by entity/txn.
- **Internal logic:** pandas groupby + rolling; only compute requested families (params from plan).
- **Dependencies:** pandas, numpy.
- **Complexity:** Medium.
- **Est. dev time:** 6–7h (the ML-facing workhorse).
- **Priority:** P0.
- **Risks:** rolling windows slow on large data → precompute sorted per customer; sample.
- **Future:** graph features for layering (fan-in/fan-out).

## 10. AML Pattern Detector (AML)
- **Purpose:** Deterministic rules for named typologies.
- **Responsibilities:** structuring (N sub-\$10k deposits within window), smurfing (many small from/to one account), layering (chained transfers), rapid cash-out.
- **Inputs:** feature table / filtered df, pattern set.
- **Outputs:** rule hits per entity with triggering evidence (txn IDs, values).
- **Internal logic:** explicit thresholds in `config.py` (frozen — see `FINAL_ARCHITECTURE_DECISIONS.md` D6); each hit carries a machine-readable `rule_id` + evidence for the Explainer. **Pinned defaults:**
  - *structuring:* ≥3 cash transactions with amount in **\$8,000–\$9,999** within a rolling **7-day** window per customer (all under the \$10k CTR line).
  - *smurfing:* one account receiving small deposits (< \$3,000) from **≥5 distinct sources** within 7 days.
  - *rapid cash-out:* a withdrawal ≥ **90%** of a deposit amount within **24h** of that deposit.
  - *layering (P2):* ≥3-hop transfer chain draining an account within 72h (pandas self-join).
- **Complexity:** Medium.
- **Est. dev time:** 5–6h.
- **Priority:** P0 (this is where explainability shines).
- **Risks:** thresholds arbitrary → rationale documented (CTR = \$10k) + configurable; **do not tune live during the demo.**
- **Future:** typology library expansion; tunable per jurisdiction.

## 11. Anomaly Detector (AD)
- **Purpose:** Catch unknown/unnamed anomalies.
- **Responsibilities:** fit IsolationForest on engineered features → anomaly score per entity/txn.
- **Inputs:** numeric feature matrix.
- **Outputs:** anomaly score ∈ [0,1], top contributing features.
- **Internal logic:** `StandardScaler` → `IsolationForest(contamination=0.02, random_state=42)` (**fixed seed for reproducible demos**); anomaly score normalized to [0,1]; feature attribution via per-feature deviation from the population median.
- **Dependencies:** scikit-learn.
- **Complexity:** Medium.
- **Est. dev time:** 4h.
- **Priority:** P1 (used by the broad plans). **Secondary to rules** — it's the "ML-based approach" checkbox, not the star.
- **Risks:** unstable scores on tiny subsets → **only run when N ≥ 500**; below that, rules-only and the trace says so. Do not let it override a clear rule hit.
- **Future:** ensemble (LOF + IForest), SHAP attributions (stretch).

## 12. Risk Classifier (RC)
- **Purpose:** Fuse signals → low/med/high.
- **Responsibilities:** combine rule hits (weighted) + anomaly score → risk band with context-appropriate thresholds.
- **Inputs:** rule hits, anomaly score, intent context.
- **Outputs:** `risk`, numeric `score`, contributing signals.
- **Internal logic:** **frozen deterministic formula** (see `FINAL_ARCHITECTURE_DECISIONS.md` D7). Default:
  `score = min(1.0, 0.6·rule_severity + 0.4·anomaly_score)` where `rule_severity ∈ {0, 0.5, 0.8, 1.0}` by strongest rule hit, and `anomaly_score ∈ [0,1]` (0 if AnomalyDetector didn't run).
  Bands: `score ≥ 0.75 → high`, `0.45–0.75 → medium`, `< 0.45 → low`. **A confirmed rule hit floors the band at medium** regardless of anomaly score.
- **Complexity:** Low-Medium.
- **Est. dev time:** 3h.
- **Priority:** P0.
- **Risks:** everything scores "high" (over-flagging) → calibrate the constants on the sample in Phase 5; show score distribution; **freeze constants before the demo.**
- **Future:** learn weights from any available labels.

## 13. Explainer (XP)
- **Purpose:** Human-readable reason per flag, tied to query intent + pattern.
- **Responsibilities:** template a factual sentence from rule evidence / top anomaly features; optional LLM polish.
- **Inputs:** flag record (rule_id, evidence, features), query intent.
- **Outputs:** explanation string + structured evidence.
- **Internal logic:** **template-only in the P0 build** — a deterministic sentence built from `rule_id` + evidence values; it never hallucinates because the LLM isn't involved. **LLM polish is P1**, strictly constrained to rephrase the template with the same injected numbers, plus a check that those numbers survive the rewrite (else fall back to the template).
- **Dependencies:** none for P0; LLM client optional (P1).
- **Complexity:** Low-Medium.
- **Est. dev time:** 3–4h.
- **Priority:** P0 (top-scoring axis).
- **Risks:** LLM invents numbers → mitigated by shipping template-only first; polish is additive and validated.
- **Future:** narrative case summaries per customer.

## 14. Recommender (REC)
- **Purpose:** Map risk → escalation action.
- **Responsibilities:** low→monitor, medium→review, high→report (SAR-style), with reason.
- **Inputs:** risk level + signals.
- **Outputs:** action + short justification.
- **Complexity:** Low.
- **Est. dev time:** 1–2h.
- **Priority:** P0.
- **Risks:** trivial mapping looks thin → tie to rule severity, not just band.

## 15. Visualizer (VIZ)
- **Purpose:** Charts/tables for reviewer confidence.
- **Responsibilities:** timeline of flagged txns, amount histogram vs \$10k line, per-customer feature bars, risk-distribution.
- **Inputs:** results, features.
- **Outputs:** Plotly figure specs.
- **Dependencies:** Plotly.
- **Complexity:** Low-Medium.
- **Est. dev time:** 4h.
- **Priority:** P1.
- **Risks:** over-polishing charts → fixed set of 3–4 templates.

## 16. Response Formatter (RESP)
- **Purpose:** Assemble the single structured response (see `ARCHITECTURE.md §5`).
- **Responsibilities:** merge understanding + plan + skipped + results + charts + trace.
- **Inputs:** `Context`, plan, trace.
- **Outputs:** one JSON object.
- **Complexity:** Low.
- **Est. dev time:** 2h.
- **Priority:** P0.

## 17. Frontend (UI)
- **Purpose:** Chat + agent-trace + results + charts.
- **Responsibilities:** query box, render plan/skipped panel, results table with risk badges, expandable explanations, embedded charts, example-query buttons.
- **Inputs:** response JSON.
- **Outputs:** rendered app.
- **Dependencies:** Streamlit, Plotly.
- **Complexity:** Medium.
- **Est. dev time:** 6–8h.
- **Priority:** P0.
- **Risks:** UI polish eats time → start from the response contract, one-page layout.
- **Future:** React/Next.js custom UI (stretch).

## 18. Backend API (FastAPI)
- **Purpose:** `POST /analyze`, `GET /schema`, `GET /examples`.
- **Complexity:** Low.
- **Est. dev time:** 2–3h.
- **Priority:** P0.
- **Note:** If time is tight, Streamlit can call the agent in-process and FastAPI becomes optional — but keeping the API boundary makes the "API interaction" requirement explicit and enables the React stretch goal.

---

## Rough effort roll-up (P0 only) — *revised after review*
QU 5 + PL 3.5 + EX 4 + ToolSet 0.5 + DL 3 (incl. cleaning) + FIL 3 + FE 7 + AML 6 + RC 3 + XP 4 + REC 2 + RESP 2 + UI 7 + API 3 ≈ **53 person-hours** (down from ~60: deterministic planner −4h, plain tool set −1.5h, Preprocessor folded in). Two people over 48h ≈ 60–70 focused hours → P0 now fits with **more** margin; P1 (EDA, AD, VIZ polish, LLM explanation polish) fills the rest; P2 are stretch. The freed hours go to calibration + the trace panel, where the marks are.
