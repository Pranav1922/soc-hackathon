# Folder Structure

Scalable but not bloated — a modular monolith. Each directory maps to a component in `ARCHITECTURE.md`. No code here, just the layout and the reason each directory exists.

```
soc-hackathon/
├── README.md                  # G4: problem, dataset+citations, approach, stack, setup, usage, disclosures
├── requirements.txt           # pinned deps (one-command install, G2)
├── .env.example               # LLM_API_KEY, LLM_PROVIDER — real .env is gitignored
├── .gitignore
├── LICENSE                    # MIT
├── run.sh                     # one-command launch (satisfies "runnable with setup steps")
│
├── docs/                      # this planning blueprint (architecture, requirements, plan, …)
│
├── data/
│   ├── raw/                   # downloaded public dataset (gitignored if large; source cited in README)
│   ├── sample/                # small committed sample so the repo runs out-of-the-box
│   └── synthetic/             # generator output with planted, explainable AML cases
│
├── app/                       # ← the modular monolith (single deployable)
│   │
│   ├── main.py                # FastAPI entrypoint (OPTIONAL): /analyze, /schema, /examples
│   ├── config.py              # FROZEN constants: $10k CTR, rule thresholds, risk formula, schema_map, LLM cfg
│   ├── schemas.py             # Pydantic: Context, Understanding, ExecutionPlan, Response
│   │
│   ├── agent/                 # THE BRAIN — coordination logic
│   │   ├── understanding.py   # Query Understanding (LLM, 1 call) + keyword-extractor fallback
│   │   ├── planner.py         # DETERMINISTIC planner: understanding → ExecutionPlan (no LLM)
│   │   ├── executor.py        # Orchestrator: runs plan, threads Context, records trace
│   │   └── tool_set.py        # ToolName enum + {ToolName: callable} dict (plain, no decorators)
│   │
│   ├── tools/                 # THE HANDS — each tool = run(context, params) -> (context, result, trace)
│   │   ├── data_loader.py     # load + clean once (absorbs the former preprocessor)
│   │   ├── filter_tool.py
│   │   ├── eda.py
│   │   ├── feature_engineering.py
│   │   ├── aml_patterns.py    # structuring/smurfing/layering rules + evidence
│   │   ├── anomaly.py         # IsolationForest + feature attribution
│   │   ├── risk_classifier.py
│   │   ├── explainer.py       # evidence templates (+ optional LLM narration)
│   │   ├── recommender.py     # monitor / review / report
│   │   └── visualizer.py      # Plotly chart specs
│   │
│   ├── llm/
│   │   └── client.py          # provider-agnostic LLM wrapper (Groq / Gemini / Ollama)
│   │
│   └── response.py            # Response Formatter: assemble final structured JSON
│
├── ui/
│   └── streamlit_app.py       # chat box · plan/skipped panel · results table · charts · trace
│
├── scripts/
│   └── generate_synthetic.py  # documented synthetic data generator (schema + planted cases)
│
└── tests/
    ├── test_planner.py        # GOLDEN-PLAN TESTS: 5 example queries → expected tools + skipped[]
    ├── test_rules.py          # structuring/smurfing fixtures → expected hits
    ├── test_features.py       # rolling sums / velocity / z-score correctness
    └── test_end_to_end.py     # query string → full response contract shape
```

## Why each directory exists

| Directory | Reason it exists |
|-----------|------------------|
| `docs/` | The blueprint; also doubles as Round-2 explanation material (G13). |
| `data/raw` `data/sample` `data/synthetic` | Separate provenance: cited public data, a tiny committed sample so judges can run instantly, and planted synthetic cases that guarantee explainable demo positives. |
| `app/` | The single deployable monolith — the whole point of "no microservices." |
| `app/agent/` | Isolates the reasoning/coordination (the graded "agentic" core) from the tools it calls. Dev A's territory. |
| `app/tools/` | One file per tool; the `tool_set` dict lets the planner pick any subset. Dev B's territory. Adding a typology later = one file + one `ToolName` enum line (future extensibility). |
| `app/llm/` | LLM behind one interface so provider swaps don't touch agent logic (and enables the offline fallback). |
| `ui/` | Presentation separated from logic — swap Streamlit for React (stretch) without touching `app/`. |
| `scripts/` | One-off tooling (data gen) kept out of the runtime path. |
| `tests/` | `test_planner.py` is the proof of the headline requirement; keep it green. |

## Separation of concerns (the load-bearing boundaries)
- **agent/ never computes numbers; tools/ never decide the plan.** The LLM lives in **only one place**: `agent/understanding.py` (and optionally `tools/explainer.py` for P1 phrasing). `agent/planner.py` is deterministic.
- **`ToolName` enum in `tool_set.py` is the single source of truth** for what tools exist — the planner may only emit those names.
- **`schemas.py` and `config.py` are shared contracts** — frozen in Phase 0. `config.py` holds every tunable constant so nobody hardcodes thresholds in two places.
