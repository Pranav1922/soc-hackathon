# Competitive Advantages

Assume hundreds of teams build the same "EDA → IsolationForest → risk score" pipeline with a chat box. This document lists **24 features** that separate us, ranked by **ROI** (judge + demo impact ÷ effort × risk). Ratings: Difficulty/Time/Risk = Low/Med/High; Impact = ★ (1–5).

The bar to clear: most teams will fail the "not a fixed pipeline" requirement and show a black-box score. Our wins come from making **reasoning visible** and **explanations auditable** — the two highest-scoring axes in this rubric.

---

## Ranked feature table (highest ROI → lowest)

| # | Feature | Difficulty | Time | Judge Impact | Demo Impact | Risk | Worth Building? |
|---|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **Live Agent Decision Trace panel** (shows plan, tools invoked, tools *skipped*, why, rowcounts) | Low | 3h | ★★★★★ | ★★★★★ | Low | **YES — core** |
| 2 | **Three-query demo that visibly changes the plan** (structuring / threshold / single-entity) | Low | 2h | ★★★★★ | ★★★★★ | Low | **YES — core** |
| 3 | **Evidence-grounded explanations** ("6 deposits \$9.2k–\$9.8k under \$10k CTR") — numbers from code, never LLM | Med | 4h | ★★★★★ | ★★★★ | Low | **YES — core** |
| 4 | **Deterministic planning + keyword-understanding fallback** (demo survives LLM outage/rate-limit; only 1 LLM call to fail) | Low | 2h | ★★★ | ★★★★★ | Low | **YES** |
| 4b | **Benford's-Law check** on transaction amounts (cheap, credible AML statistical signal) | Low | 2h | ★★★★ | ★★★ | Low | **YES (P1)** |
| 5 | **Hybrid detection** (transparent rules for named typologies + IsolationForest for unknowns) | Med | 5h | ★★★★ | ★★★★ | Low | **YES** |
| 6 | **Planted synthetic cases** so the demo always finds real, explainable positives | Low | 3h | ★★★ | ★★★★★ | Low | **YES** |
| 7 | **Escalation as a SAR-style action** with justification (monitor/review/report + why) | Low | 2h | ★★★★ | ★★★ | Low | **YES** |
| 8 | **Amount-vs-\$10k-CTR histogram** — one glance shows structuring clustering just under the line | Low | 2h | ★★★★ | ★★★★ | Low | **YES** |
| 9 | **Golden-plan tests** shown live (query → expected plan) proving "dynamic, not fixed" | Low | 2h | ★★★★ | ★★★ | Low | **YES** |
| 10 | **Human-in-the-loop clarifying question** when a query is ambiguous | Med | 4h | ★★★★ | ★★★★ | Med | **YES (P1)** |
| 11 | **Natural-language case summary per customer** (agent writes the analyst's note) | Med | 3h | ★★★★ | ★★★★ | Med | **YES (P1)** |
| 12 | **Smurfing/layering network graph** (fan-in/fan-out of a ring) | Med | 5h | ★★★★★ | ★★★★★ | Med | **YES if ahead (P1/P2)** |
| 13 | **Downloadable SAR draft / CSV of flags** (regulator-shaped output) | Low | 3h | ★★★ | ★★★ | Low | **YES (P1)** |
| 14 | **Risk-score distribution + threshold calibration view** (shows we controlled false positives) | Med | 3h | ★★★★ | ★★★ | Med | **YES (P1)** |
| 15 | **Confidence + "why this plan" from the planner** (agent explains its own routing) | Med | 3h | ★★★★ | ★★★★ | Med | **YES (P1)** |
| 16 | **Multi-provider LLM w/ local Ollama fallback** (offline-capable, reproducible for judges) | Med | 3h | ★★★ | ★★★ | Med | **YES (P1)** |
| 17 | **Feature-attribution bars for anomalies** ("velocity + amount deviation drove this") | Med | 3h | ★★★★ | ★★★ | Med | **Maybe (P1)** |
| 18 | **Comparative query** ("compare risk in India vs UK") → two-subset plan | Med | 4h | ★★★ | ★★★ | Med | **Maybe (P2)** |
| 19 | **PyOD ensemble** (LOF + IForest) for detector robustness | Med | 4h | ★★ | ★★ | Med | **Maybe (P2)** |
| 20 | **SHAP explanations** on the anomaly model | High | 5h | ★★★ | ★★ | High | **Skip unless ahead (P2)** |
| 21 | **React/Next.js custom UI** | High | 10h | ★★ | ★★★ | High | **Skip (P2 only)** |
| 22 | **Feedback loop** (analyst marks false positive → threshold adjusts) | High | 6h | ★★★ | ★★ | High | **Skip** |
| 23 | **Real-time streaming ingestion** | High | 8h | ★ | ★ | High | **Skip — scope note says batch is fine** |
| 24 | **Fine-tuned/custom deep model** | High | 12h | ★★ | ★ | High | **Skip — no labels, no time, deprioritized by rubric** |

---

## Top 5 — the biggest competitive edge in 48h

1. **Live Agent Decision Trace panel (#1).** The single strongest differentiator. It turns the abstract "agentic" requirement into something a judge *sees*: the plan, the tools chosen, the tools *skipped*, and the reason for each. Almost no other team will visualize the reasoning — most show only final flags.

2. **Three-query demo that visibly re-plans (#2).** In the 2-minute video, run structuring → threshold → single-entity and let the trace panel change each time. This is the exact behavior the rubric rewards, demonstrated in 30 seconds.

3. **Evidence-grounded explanations (#3).** "6 cash deposits of \$9.2k–\$9.8k within 4 days, all below the \$10k CTR threshold" — with the numbers computed in code, not narrated by an LLM. Compliance-credible, auditable, and directly answers the top-weighted "explainability" axis.

4. **Hybrid detection (#5).** Rules explain the *named* typologies with crisp reasons; IsolationForest catches the *unknown*. The rubric explicitly allows hybrid — we use it as a strength, covering both "we can explain it" and "we can find novel anomalies."

5. **Deterministic planning + fallback understanding (#4).** Unsexy but decisive: planning is pure Python and the only LLM call (understanding) has a keyword fallback, so the demo works even if the free API rate-limits mid-presentation. A working demo beats an ambitious broken one every time — and it satisfies the doc's "deterministic orchestrated pipeline is acceptable" clause.

## What we deliberately will NOT build
Streaming (#23), custom/fine-tuned models (#24), a feedback-learning loop (#22), and a from-scratch React UI (#21, unless far ahead). Each is high effort, high risk, and satisfies **no requirement** the chosen design doesn't already meet. Time saved goes into calibration, explanations, and the trace panel — where the marks actually are.

## The one-line pitch for the deck
> *"Most teams built a fixed AML pipeline with a chatbot. We built an agent that reads your question, plans a different tool path for each one, and shows you exactly what it decided, why, and the evidence behind every flag."*
