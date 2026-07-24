# Requirements Checklist — Problem Statement 1

**Problem Statement:** AI-Powered Suspicious Activity Detection (AML)
**Source:** `VIT_Campus_Hackathon.docx`

Every explicit requirement extracted from PS1 and the shared hackathon rules. **Nothing is left unmapped.** "Mandatory" = the document states it as a requirement or an evaluated criterion. "Optional" = encouraged / stretch / example-only.

Legend for components (defined in `ARCHITECTURE.md` / `MODULE_BREAKDOWN.md`):
`QU`=Query Understanding, `PL`=Planner (deterministic), `EX`=Orchestrator/Executor, `DL`=Data Loader (includes load-time cleaning; the former `PP`/Preprocessor is merged in), `FIL`=Filter Tool, `EDA`=EDA Tool, `FE`=Feature Engineering, `AML`=AML Pattern Detector, `AD`=Anomaly Detection, `RC`=Risk Classifier, `XP`=Explanation Layer, `REC`=Recommendation, `VIZ`=Visualization, `RESP`=Response Formatter, `UI`=Frontend.

---

## A. Core Agent Requirements

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| A1 | Accept a user instruction / natural-language query | **Mandatory** | UI, QU | "The agent must accept a user instruction or query…" |
| A2 | Autonomously orchestrate calls to internal components/tools | **Mandatory** | PL, EX | "…autonomously orchestrate calls to internal components/tools" |
| A3 | Must **NOT** follow a fixed sequential pipeline | **Mandatory** | PL, EX | "The agent must not follow a fixed sequential pipeline" |
| A4 | Parse query → extract **intent** | **Mandatory** | QU | "…parse the user's natural language query, extract intent…" |
| A5 | Extract **filters** (date range, segment, country, txn type) | **Mandatory** | QU | "Extract intent, filters (date range, segment, country, transaction type)…" |
| A6 | Extract **entities** (e.g., customer ID) | **Mandatory** | QU | "…extract intent, filters, entities…" |
| A7 | Extract **target AML pattern type** | **Mandatory** | QU | "…and pattern types" |
| A8 | Build a **dynamic execution plan** (which tools, what order, what subset) | **Mandatory** | PL | "Build a dynamic execution plan that decides which tools to call, in what order, and on which subset" |
| A9 | **Selective** tool invocation — not every query needs every tool | **Mandatory** | PL, EX | "not every query needs every tool" / "invoking only the tools necessary" |
| A10 | Multiple steps performed automatically after one query | **Mandatory** | EX | "What counts as agentic": "perform multiple steps automatically" |
| A11 | Decide sequence of tool calls based on query / workflow state | **Mandatory** | PL | "What counts as agentic": "decide the sequence of tool/component calls" |
| A12 | Must be more than a single one-shot LLM response | **Mandatory** | PL, EX, tools | "A single one-shot LLM response … is not sufficient" |
| A13 | Deterministic orchestrated pipeline acceptable **if** query-driven | Clarification | PL, EX | "A deterministic orchestrated pipeline is acceptable if it behaves like an agent and is clearly query-driven" |

## B. Data & Preprocessing

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| B1 | Load the dataset | **Mandatory** | DL | "Load the dataset…" |
| B2 | Apply **only** preprocessing relevant to the query | **Mandatory** | DL | "…and apply only the preprocessing relevant to the query" — minimal query-independent cleaning runs once at load; no irrelevant preprocessing runs. |
| B3 | Apply filters to operate on the correct **subset** | **Mandatory** | FIL | "…on which subset"; example: "Apply time filter first" |
| B4 | Batch analysis on a sample dataset (no live streaming) | Scope note | DL | Scope Guidance: "Batch analysis on a sample dataset is sufficient; live streaming … not required" |

## C. Analytical Capabilities (invoked selectively)

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| C1 | Automated EDA (profiling + visualization) to learn baseline | **Mandatory** | EDA, VIZ | Objective: "Performs automated exploratory data analysis (EDA)…" |
| C2 | Run EDA **selectively**; skip for targeted/single-entity queries | **Mandatory** | PL, EDA | "Run EDA selectively when broad exploration is needed; skip it for targeted or single-entity queries" |
| C3 | Create AML features on demand | **Mandatory** | FE | "Create AML features on demand, such as transaction frequency, rolling sums, amount deviation, velocity, and rapid cash-out patterns" |
| C3a | — transaction frequency | **Mandatory** | FE | same |
| C3b | — rolling sums | **Mandatory** | FE | same |
| C3c | — amount deviation | **Mandatory** | FE | same |
| C3d | — velocity | **Mandatory** | FE | same |
| C3e | — rapid cash-out patterns | **Mandatory** | FE | same |
| C4 | Detect anomalous / suspicious patterns | **Mandatory** | AD, AML | Objective: "Detects anomalous transaction patterns indicative of money laundering" |
| C5 | Detect **structuring / smurfing** specifically | **Mandatory** | AML | Objective + Business Summary name structuring, smurfing, layering |
| C6 | Anomaly detection via ML, statistical, rule-based, **or hybrid** | **Mandatory** | AD | "Applies anomaly detection (e.g., any ML-based approach, rule based or Hybrid)" |
| C7 | Aggregation + threshold rule path (no ML required) | **Mandatory** | FE, AML | Example: "Which customers made 10+ transactions under \$10,000?" → "aggregation and threshold rule directly; ML … not required" |
| C8 | Single-entity lookup & on-demand risk for one customer | **Mandatory** | FIL, RC | Example: "Is customer ID 4521 suspicious?" → "single-entity lookup … compute risk on-demand for that customer only" |

## D. Scoring, Classification, Explanation, Action

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| D1 | Generate a **risk score or flag** per transaction/customer | **Mandatory** | RC | Objective: "Generates a risk score or flag per transaction/customer" |
| D2 | Classify results as **low / medium / high** risk | **Mandatory** | RC | "Classify results as low, medium, or high-risk using context-appropriate thresholds" |
| D3 | Context-appropriate thresholds | **Mandatory** | RC, PL | same as D2 |
| D4 | **Human-readable explanation** per flag | **Mandatory** | XP | "Generate a human-readable explanation for each flag" |
| D5 | Explanation **tied to the original query intent + AML pattern** | **Mandatory** | XP | "…tied to the query" / "tied to the original query intent and detected AML pattern" |
| D6 | Recommend escalation action: **monitor / review / report** | **Mandatory** | REC | "Recommend the next action: monitor, review, or report" |

## E. Output & Presentation

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| E1 | Return results in a **structured, judge-inspectable** format | **Mandatory** | RESP | "Return results in a structured format that is easy for a judge to inspect" |
| E2 | Show **what the agent decided and why** (query-aware execution summary) | **Mandatory** | RESP, EX | "including what the agent decided and why" / "A query-aware execution summary showing the user request, the filters/entities detected, and the tools the agent decided to invoke" |
| E3 | Return **top** suspicious transactions/customers | **Mandatory** | RESP, RC | "Top suspicious transactions or customers returned by the selected analysis path" |
| E4 | Risk level for each flagged item | **Mandatory** | RESP, RC | "Risk level for each flagged item" |
| E5 | Explanation for each flag, tied to intent + pattern | **Mandatory** | RESP, XP | "Explanation for each flag, tied to the original query intent and detected AML pattern" |
| E6 | Suggested escalation action per item | **Mandatory** | RESP, REC | "Suggested escalation action such as monitor / review / report" |
| E7 | Supporting **charts, tables, or metrics** for reviewer confidence | **Mandatory** | VIZ | "Supporting charts, tables, or metrics for reviewer confidence" |
| E8 | Human-in-the-loop clarification when input is ambiguous | Optional* | QU, UI | Not required in PS1 (it is a PS2 requirement); implement as a differentiator only |

\*E8 is explicitly required only in PS2. For PS1 it is a **competitive advantage**, not mandatory — see `COMPETITIVE_ADVANTAGES.md`.

## F. Architecture Requirements (named tools)

| # | Requirement | M/O | Component(s) | Doc Reference |
|---|-------------|-----|--------------|---------------|
| F1 | **EDA Tool** (profiling + visualization) | **Mandatory** | EDA, VIZ | "Expected Agent Architecture: EDA Tool" |
| F2 | **Feature Engineering Tool** (model/rule-ready AML features) | **Mandatory** | FE | "Feature Engineering Tool" |
| F3 | **Anomaly Detection Tool** (ML/statistical/rules/hybrid) | **Mandatory** | AD | "Anomaly Detection Tool" |
| F4 | **Risk Classification Tool** (scores→categories via model and/or business logic) | **Mandatory** | RC | "Risk Classification Tool" |
| F5 | **Explanation Component / Rule Layer** (concise NL reasons) | **Mandatory** | XP | "Explanation Component / Rule Layer" |
| F6 | Agent **coordinates** these capabilities (visible agentic flow) | **Mandatory** | PL, EX | "clearly show an agentic flow where the agent coordinates the following capabilities" |

## G. Submission & Compliance Rules (shared)

| # | Requirement | M/O | Owner | Doc Reference |
|---|-------------|-----|-------|---------------|
| G1 | Public GitHub repo, created at start, frequent commits, full history | **Mandatory** | Team | Submission Requirements → Code repository |
| G2 | Repo runnable with clear setup steps | **Mandatory** | Team, README | "Ensure it is runnable with setup steps" |
| G3 | **No** "SG / Societe Generale / SocGen / SGGSC" references anywhere | **Mandatory** | Team | "Do not use … related references anywhere" |
| G4 | README: problem statement, dataset info, solution approach, tech stack, setup, usage | **Mandatory** | README | Submission Requirements → README.md |
| G5 | **All datasets + sources cited** in README | **Mandatory** | README | Dataset Sourcing + README requirements |
| G6 | Datasets from public/open sources only; no proprietary/copyrighted data | **Mandatory** | Team | Dataset Sourcing |
| G7 | Synthetic data allowed **if** schema/assumptions/generation logic documented | Conditional | README, DL | "Teams may use synthetic data … clearly documented" |
| G8 | Disclose all external tools, APIs, AI assistance in README | **Mandatory** | README | Permitted Tools & Technologies |
| G9 | Presentation deck — **max 2 slides** (solution, architecture, key tech, differentiator) | **Mandatory** | Team | Submission → Presentation deck |
| G10 | **2-minute** video demo, clear audio + screen | **Mandatory** | Team | Submission → video demo |
| G11 | All work original, created during the window | **Mandatory** | Team | Code of Conduct |
| G12 | Individual contributions traceable (commits/branches) | **Mandatory** | Team | Code of Conduct |
| G13 | Be able to explain/demo the entire solution in Round 2 | **Mandatory** | Team | Code of Conduct |
| G14 | Do not share problem statement publicly during contest | **Mandatory** | Team | IP & Confidentiality |

---

## Coverage Summary

- **All Objective bullets** (EDA, anomaly detection, ML/rule/hybrid, risk score/flag, explanation, escalation) → A–F. ✅
- **All Minimum Functional Requirements** → A, B, C, D. ✅
- **All 3 worked query examples** (structuring/30d, 10+ under \$10k, customer 4521) → A3, A8, A9, C5, C7, C8. ✅
- **All 5 named architecture tools** → F1–F5. ✅
- **All Recommended Outputs** → E1–E7. ✅
- **All submission/compliance rules** → G. ✅

No requirement in PS1 is unmapped. Items flagged Optional (E8) are deliberately scoped as differentiators, not skipped requirements.
