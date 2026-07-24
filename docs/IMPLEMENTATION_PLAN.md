# Implementation Plan — 48-Hour Roadmap

Two people. Phases are **independently testable** and ordered so a working demo exists early and only gets richer. Golden rule: **always have something runnable to show.**

Roles:
- **Dev A — Agent Core & UI:** LLM client, Query Understanding, deterministic Planner, Executor, Tool-set wiring, Response Formatter, Streamlit UI.
- **Dev B — Data, Tools & ML:** DataLoader (incl. load-time cleaning), Filter, Feature Engineering, AML rules, Anomaly Detection, Risk Classifier, Explainer, Recommender, Visualizer.
- Contract between them: the **tool interface** `run(context, params) -> (context, result, trace)` + the **response schema**. Agree on these in Hour 0–1; then work in parallel.

---

## Phase 0 — Setup & contracts (Hour 0–2) · both
- Create public GitHub repo (G1), MIT license, `.gitignore`, `requirements.txt`, `.env.example`, folder structure (see `FOLDER_STRUCTURE.md`).
- Source dataset (below) + write the synthetic/real dataset notes for README (G5/G7).
- Freeze: `Context`, tool interface, `Understanding`, `ExecutionPlan`, response JSON (Pydantic models). Commit stubs.
- **Testable:** repo installs clean; `pytest` runs an empty suite; schemas import.
- **Milestone M0:** repo runnable, contracts frozen.

## Phase 1 — Vertical slice, NO LLM/ML (Hour 2–8) · both
Goal: end-to-end demo using the **deterministic fallback router** only.
- Dev B: DataLoader(load+clean) → Filter → FeatureEngineering(count/amount aggregation) → AMLPatternDetector(structuring threshold rule) → RiskClassifier → Recommender.
- Dev A: deterministic planner (intent+pattern → plan) → Executor → Response Formatter → minimal Streamlit page rendering plan + results table. (This planner is the *final* planner, not a throwaway — there is no separate LLM planner to build later.)
- **Testable:** query "customers with 10+ txns under \$10k" returns a real ranked table with risk + action.
- **Milestone M1 (end of Day 1 morning):** *a working agent demo exists.* Everything after this is upgrade, not risk.

## Phase 2 — Real feature engineering + AML rules (Hour 8–16) · Dev B
- FE families: frequency, rolling sums, amount-deviation z-score, velocity, rapid cash-out, sub-threshold count.
- AML rules: structuring, smurfing, rapid cash-out (layering = P2). Each hit carries evidence + `rule_id`.
- RiskClassifier: weighted fusion + bands; calibrate on sample.
- **Testable:** unit tests on crafted structuring/smurfing fixtures produce expected hits; `pytest tests/test_rules.py` green.
- **Milestone M2:** named-pattern detection with evidence works on the real dataset.

## Phase 3 — LLM understanding + example buttons (Hour 8–16, parallel) · Dev A
- `llm_client` (Groq primary, Gemini/Ollama fallback), one prompt, few-shot for the 3 canonical queries, 8s timeout.
- QU (JSON + Pydantic validate + **keyword-extractor fallback**). The deterministic planner from Phase 1 already consumes this — no separate planner to build.
- Wire the three flagship example-query buttons to carry **pre-parsed understanding** so they work offline.
- **Testable:** golden-plan tests — the 5 example queries each yield the expected tool set + `skipped[]`. Because the planner is deterministic, these pass reliably; keep them green. Separately test that a malformed LLM response falls back to keyword understanding.
- **Milestone M3:** NL-driven dynamic plans; three queries visibly differ; works with the LLM disabled.

## Phase 4 — EDA, Anomaly Detection, Explainer, Viz (Hour 16–30) · both
- Dev B: EDA tool (profiling + baseline charts); IsolationForest anomaly detector + feature attribution; Explainer templates (+ optional LLM polish); Visualizer (timeline, histogram-vs-\$10k, feature bars, risk distribution).
- Dev A: wire EDA/AD into planner selection; render charts, expandable per-flag explanations, and the trace panel in the UI; example-query buttons.
- **Testable:** "Analyse this dataset" runs the *full* toolchain; single-entity query skips EDA/AD; charts render; each flag shows a factual explanation tied to its rule.
- **Milestone M4 (end of Day 2 morning):** feature-complete against all mandatory requirements.

## Phase 5 — Hardening, calibration, polish (Hour 30–40) · both
- Calibrate risk constants (avoid all-high) and **freeze them**. Fix IsolationForest seed. Error handling per tool. **Empty-result path**: every tool returns cleanly on 0 rows and the UI shows "no flags found + why". Loading states in UI. Risk badges.
- Verify each requirement in `REQUIREMENTS_CHECKLIST.md` end-to-end.
- Write README (G4/G5/G8): problem, dataset + citations, approach, tech stack, setup, usage, disclosures. One-command setup verified on a clean clone.
- **Testable:** clean-clone → follow README → demo works. Full `pytest` green.
- **Milestone M5:** submission-ready system + README.

## Phase 6 — Deliverables & buffer (Hour 40–48) · both
- 2-slide deck (solution, architecture diagram, the 5-query plan-contrast table, differentiators) — G9.
- Record 2-min video: three different queries → three different plans → explanations + escalation (G10).
- Final commits, confirm no banned references (G3), confirm individual commit traceability (G12).
- Deploy to Streamlit Cloud/HF Spaces; put the link in README.
- **Buffer** for the inevitable last-hour bug.
- **Milestone M6:** submitted.

---

## Critical path
`Contracts (P0) → Vertical slice (P1) → FE+Rules (P2) & LLM Planner (P3) → Explainer+Viz (P4) → README+Video (P5/P6)`

The **LLM Planner + the 5 golden-plan tests** and the **AML rules + Explainer** are the two must-not-slip strands — they carry the two highest-scoring requirements (dynamic planning, explainability). Protect them; cut stretch goals before them.

## Must-have vs nice-to-have vs stretch

**Must-have (P0 — cut nothing here):** dynamic LLM planning + fallback, selective tool execution, structuring/threshold/single-entity paths, risk bands, evidence-based explanations, escalation, structured response with trace, at least a table + one chart, README.

**Nice-to-have (P1):** full EDA dashboard, IsolationForest anomaly path, richer Plotly dashboard, human-in-the-loop clarifying question.

**Stretch (P2 — only if ahead):** React/Next.js UI, SHAP attributions, layering graph view, PyOD ensemble, Docker image, network graph of smurfing rings, downloadable SAR draft. (See `COMPETITIVE_ADVANTAGES.md`.)

## Dataset decision (do in Phase 0)
- **Primary option:** a public AML transactions dataset (e.g., IBM "Transactions for Anti-Money Laundering" / PaySim / SAML-D on Kaggle) — cite source in README (G5/G6).
- **Fallback:** synthetic generator with documented schema (customer_id, txn_id, timestamp, amount, type, counterparty, country) that *seeds known structuring/smurfing cases* so the demo reliably finds them (G7). Document schema, assumptions, generation logic in README.
- **Recommendation:** ship the **synthetic generator regardless** — it guarantees the demo has planted, explainable positives, which de-risks the video. Use a real dataset alongside it for credibility.

## Risk register (top 5)
1. **LLM misplans / rate-limits mid-demo** → schema validation + deterministic fallback + local Ollama option. (Mitigated in P1/P3.)
2. **Over-flagging (everything "high")** → calibrate on sample in P5; show risk distribution chart.
3. **Time sink in UI polish** → freeze one-page layout from the response contract; polish only in P5.
4. **Dataset dates make "last 30 days" empty** → resolve relative dates against dataset max timestamp; document.
5. **Integration slips because contracts drifted** → single source of truth: tool registry generates the planner catalog; response Pydantic model shared by API + UI.
