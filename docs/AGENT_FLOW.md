# Agent Flow — Reasoning & Dynamic Execution Plans

This document shows the agent's end-to-end reasoning and, critically, that **different queries produce different execution plans**.

## 1. The reasoning pipeline

```
User Query
   │
   ▼
Intent Detection        ── classify: eda | detect_pattern | threshold_rule | single_entity | compare
   │
   ▼
Entity Extraction       ── customer IDs, account IDs, merchant, country
   │
   ▼
Filter Extraction       ── date range, segment, txn type, amount thresholds
   │
   ▼
AML Pattern Tagging     ── structuring | smurfing | layering | rapid_cash_out | none
   │
   ▼
Planner                 ── select tools + order + target subset  → ExecutionPlan
   │                        (DETERMINISTIC pure-Python mapping — no LLM here)
   ▼
Tool Selection          ── keep only necessary tools; record `skipped[]`
   │
   ▼
Execution               ── run steps, thread shared Context, record trace
   │
   ▼
Reasoning / Scoring     ── rules + anomaly score → RiskClassifier → low/med/high
   │
   ▼
Explanation             ── NL reason per flag, tied to intent + triggering rule/feature
   │
   ▼
Recommendation          ── monitor / review / report
   │
   ▼
Final Structured Response  ── understanding + plan + skipped + results + charts + trace
```

## 2. How the plan is chosen (decision logic)

The Planner is a **deterministic function** of `intent` + `aml_pattern` + `filters` + `entities`. There is no LLM in this step, so the mapping is fully testable (golden-plan tests) and identical every run. The rules:

- `DataLoader` is always first.
- `Filter` is included **iff** any filter or entity was extracted.
- `EDA` is included **only** when `intent == eda` (broad exploration). Skipped otherwise.
- `FeatureEngineering` includes **only** the feature families the pattern needs (structuring → sub-threshold + rolling sums; rapid_cash_out → velocity + cash-out; etc.).
- `AMLPatternDetector` runs when a named pattern is present.
- `AnomalyDetector` runs when `intent` is broad/unknown or `aml_pattern == none` (find-the-unknown). Skipped for pure threshold-rule and named-pattern-only queries unless requested.
- `RiskClassifier` + `Explainer` + `Recommender` run whenever any flag is produced.
- `Visualizer` runs unless the query is a single scalar answer.

## 3. Example execution plans (proof of dynamic behavior)

### Example 1 — "Find structuring patterns in the last 30 days"
Intent `detect_pattern`, pattern `structuring`, filter `last_30_days`.

```
DataLoader → Filter(last 30d) → FeatureEngineering(structuring features)
          → AMLPatternDetector(structuring) → RiskClassifier
          → Explainer → Recommender → Visualizer
SKIPPED: EDA, AnomalyDetector
```
Why: pattern is named and specific → no need for broad EDA or generic anomaly model.

### Example 2 — "Which customers made 10+ transactions under $10,000?"
Intent `threshold_rule`, pattern `structuring` (implied), no ML.

```
DataLoader → FeatureEngineering(count + amount aggregation, via DuckDB GROUP BY)
          → AMLPatternDetector(threshold rule: count>=10 AND amount<10000)
          → RiskClassifier → Explainer → Recommender → Visualizer(table + histogram)
SKIPPED: EDA, AnomalyDetector, Filter(no date/segment filter)
```
Why: a crisp SQL aggregation answers it; ML would be theater.

### Example 3 — "Is customer ID 4521 suspicious?"
Intent `single_entity`, entity `C4521`.

```
DataLoader → Filter(entity = C4521) → FeatureEngineering(on-demand, that customer)
          → AMLPatternDetector(all rules, single customer) → RiskClassifier
          → Explainer → Recommender
SKIPPED: EDA, AnomalyDetector (full population), Visualizer(optional small chart only)
```
Why: single-entity lookup; no population-wide EDA or global anomaly pass.

### Example 4 — "Analyse this dataset for suspicious activity"
Intent `eda` + broad detection, no filter.

```
DataLoader(load+clean) → EDA(profiling + baseline) → FeatureEngineering(all families)
          → AnomalyDetector(IsolationForest, full set) → AMLPatternDetector(all rules)
          → RiskClassifier → Explainer → Recommender → Visualizer(dashboard)
SKIPPED: nothing — this is the only path that uses the full toolchain.
```
(Cleaning happens once inside DataLoader at startup, so there is no separate Preprocessor step in any plan.)
Why: broad, open-ended → the one case where full EDA + anomaly detection is justified.

### Example 5 — "Flag high-risk customers in India using velocity"
Intent `detect_pattern`, pattern `rapid_cash_out`/velocity, filter `country=IN`.

```
DataLoader → Filter(country=IN) → FeatureEngineering(velocity + rapid_cash_out)
          → AnomalyDetector(on velocity features) → RiskClassifier(high only)
          → Explainer → Recommender → Visualizer
SKIPPED: EDA, structuring rules
```

### Contrast table

| Query | Filter | EDA | FE families | AML rules | Anomaly ML | Viz |
|-------|:---:|:---:|---|:---:|:---:|:---:|
| Structuring, 30d | ✅ time | ❌ | structuring | ✅ | ❌ | ✅ |
| 10+ under \$10k | ❌ | ❌ | aggregation | ✅ | ❌ | ✅ |
| Customer 4521 | ✅ entity | ❌ | on-demand | ✅ | ❌ | small |
| Analyse dataset | ❌ | ✅ | all | ✅ | ✅ | ✅ |
| Velocity, India | ✅ country | ❌ | velocity | ❌ | ✅ | ✅ |

Five queries → five distinct plans. This table is worth putting on a slide.

## 4. Human-in-the-loop (optional differentiator)

If QU confidence is low or a required filter is missing (e.g., "find suspicious activity last month" with no dataset date column matched), the agent returns a **clarifying question** instead of guessing. Not required by PS1 (it's a PS2 requirement) — implemented as a differentiator. See `COMPETITIVE_ADVANTAGES.md`.

## 5. Failure / fallback paths

**LLM understanding fails (rate-limit, timeout >8s, malformed JSON):**
```
LLM understanding unavailable
        │
        ▼
Keyword extractor builds a degraded understanding from the query
        │
        ▼
Deterministic planner + executor proceed normally; response marks understanding="fallback"
```
Planning and execution are always deterministic, so only this one call can ever need a fallback.

**Query legitimately matches nothing (empty subset after filter):**
```
Filter → 0 rows
        │
        ▼
Downstream tools short-circuit to a clean "no results" state
        │
        ▼
Response explains WHY (e.g., "0 transactions in the last 30 days; dataset ends 2023-06-01")
```

**Flagship demo buttons:** the three example queries ship with pre-parsed understanding, so they route correctly even with the LLM fully offline. The demo never hard-fails.
