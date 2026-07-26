import { useState } from "react";
import type { IconType } from "react-icons";
import { m } from "framer-motion";
import {
  FiBarChart2,
  FiCheckSquare,
  FiClipboard,
  FiCpu,
  FiFileText,
  FiGrid,
  FiMessageSquare,
  FiPlay,
  FiShield,
  FiSliders,
  FiTarget,
} from "react-icons/fi";

type Layer = "input" | "ai" | "engine" | "ml" | "rule" | "output";

interface Node {
  id: string;
  title: string;
  short: string;
  detail: string;
  icon: IconType;
  layer: Layer;
}

const LAYER: Record<Layer, { label: string; text: string; ring: string; dot: string }> = {
  input: { label: "Input", text: "text-accent", ring: "border-accent/40 bg-accent/10", dot: "bg-accent" },
  ai: { label: "AI", text: "text-purple-300", ring: "border-purple-400/40 bg-purple-400/10", dot: "bg-purple-300" },
  engine: { label: "Orchestration", text: "text-sky-300", ring: "border-sky-400/40 bg-sky-400/10", dot: "bg-sky-300" },
  ml: { label: "ML", text: "text-risk-medium", ring: "border-risk-medium/40 bg-risk-medium/10", dot: "bg-risk-medium" },
  rule: { label: "Rules", text: "text-risk-medium", ring: "border-risk-medium/40 bg-risk-medium/10", dot: "bg-risk-medium" },
  output: { label: "Output", text: "text-risk-low", ring: "border-risk-low/40 bg-risk-low/10", dot: "bg-risk-low" },
};

const NODES: Node[] = [
  {
    id: "user-query",
    title: "User Query",
    short: "A natural-language investigation request.",
    detail:
      "The analyst asks a question in plain English — e.g. “Find suspicious structuring” or “Analyze customer C12345”. No query language, filters, or SQL required; intent is inferred downstream.",
    icon: FiMessageSquare,
    layer: "input",
  },
  {
    id: "llm-understanding",
    title: "LLM Query Understanding",
    short: "Parse intent, entities, filters, and target pattern.",
    detail:
      "A single LLM call extracts the intent, entities, date/amount filters, and the AML pattern of interest. If the LLM is unavailable, a deterministic keyword extractor takes over — so the platform stays offline-safe and never blocks an investigation.",
    icon: FiCpu,
    layer: "ai",
  },
  {
    id: "planner",
    title: "Planner",
    short: "Builds a deterministic tool plan.",
    detail:
      "From the understanding, a rule-based planner decides which tools to run and in what order. It is fully deterministic — no LLM in the loop — and prunes tools that aren't relevant to the query, which appear as “skipped” in the pipeline.",
    icon: FiClipboard,
    layer: "engine",
  },
  {
    id: "execution-engine",
    title: "Execution Engine",
    short: "Runs the planned tools in sequence.",
    detail:
      "The executor runs each planned step in order, threading data through the pipeline and recording a trace — rows in/out, duration, and status — for every tool, giving full transparency into how a conclusion was reached.",
    icon: FiPlay,
    layer: "engine",
  },
  {
    id: "feature-engineering",
    title: "Feature Engineering",
    short: "Builds the AML features detection needs.",
    detail:
      "Raw transactions are aggregated into entity-level features — rolling sums, sub-threshold deposit counts, source diversity, and velocity — the signals the rules and the anomaly model rely on.",
    icon: FiSliders,
    layer: "engine",
  },
  {
    id: "aml-detector",
    title: "AML Pattern Detector",
    short: "Applies deterministic AML typology rules.",
    detail:
      "Frozen rules detect structuring, smurfing, layering, and rapid cash-out — e.g. ≥3 cash deposits of $8,000–$9,999 within a 7-day window to stay under the $10,000 CTR line. Matching entities are flagged with the exact evidence.",
    icon: FiTarget,
    layer: "rule",
  },
  {
    id: "risk-classifier",
    title: "Risk Classifier",
    short: "Scores and bands each flagged entity.",
    detail:
      "Rule severity is combined with an Isolation Forest anomaly score into a single 0–1 risk score, then each entity is banded low, medium, or high — a hybrid of deterministic rules and unsupervised ML.",
    icon: FiShield,
    layer: "ml",
  },
  {
    id: "explainer",
    title: "Explainer",
    short: "Generates evidence-grounded reasons.",
    detail:
      "Every flag gets a plain-language explanation citing the specific transactions, amounts, and thresholds involved — so a reviewer can understand and defend the decision, not just see a score.",
    icon: FiFileText,
    layer: "engine",
  },
  {
    id: "recommender",
    title: "Recommender",
    short: "Recommends an escalation action.",
    detail:
      "Based on the risk band and rule severity, each flag is assigned a recommended action — monitor, review, or report — aligning the output with a real compliance workflow.",
    icon: FiCheckSquare,
    layer: "engine",
  },
  {
    id: "visualizer",
    title: "Visualizer",
    short: "Produces native Plotly figures.",
    detail:
      "The visualizer builds timelines, amount distributions against the CTR threshold, and per-entity risk-signal breakdowns as native Plotly specs — rendered verbatim by the frontend for reviewer confidence.",
    icon: FiBarChart2,
    layer: "engine",
  },
  {
    id: "dashboard",
    title: "Dashboard",
    short: "The explorable investigation console.",
    detail:
      "The React console renders everything the analyst needs to act — the parsed understanding, a filterable results table, interactive charts, the execution pipeline, and a per-entity investigation panel.",
    icon: FiGrid,
    layer: "output",
  },
];

export default function Architecture() {
  const [selectedId, setSelectedId] = useState<string>(NODES[0].id);
  const selected = NODES.find((n) => n.id === selectedId) ?? NODES[0];
  const SelectedIcon = selected.icon;
  const selLayer = LAYER[selected.layer];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="animate-fade-up">
        <h2 className="text-2xl font-bold tracking-tight text-slate-100">System Architecture</h2>
        <p className="mt-1 text-sm text-slate-400">
          The end-to-end agent pipeline — from a natural-language question to an explainable investigation. Select any
          stage to see what it does.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {/* Flow */}
        <ol className="space-y-0">
          {NODES.map((node, i) => {
            const layer = LAYER[node.layer];
            const active = node.id === selectedId;
            const NodeIcon = node.icon;
            const last = i === NODES.length - 1;
            return (
              <li key={node.id} className="flex flex-col items-stretch">
                <m.button
                  type="button"
                  onClick={() => setSelectedId(node.id)}
                  whileHover={{ y: -2 }}
                  aria-pressed={active}
                  className={`glass group flex items-center gap-4 p-4 text-left transition-all duration-300 hover:border-accent/40 hover:shadow-glow-lg ${
                    active ? "border-accent/50 shadow-glow-lg ring-1 ring-accent/30" : ""
                  }`}
                >
                  <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl border ${layer.ring} ${layer.text}`}>
                    <NodeIcon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-100">{node.title}</span>
                      <span className={`hidden rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider sm:inline-flex ${layer.ring} ${layer.text}`}>
                        {layer.label}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-sm text-slate-400">{node.short}</p>
                  </div>
                  <span className="font-mono text-xs text-slate-600">{String(i + 1).padStart(2, "0")}</span>
                </m.button>
                {!last && (
                  <div className="flex h-7 items-center justify-center">
                    <span className="flow-connector h-full" />
                  </div>
                )}
              </li>
            );
          })}
        </ol>

        {/* Detail panel */}
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <m.div
            key={selected.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="glass p-6"
          >
            <div className="flex items-center gap-3">
              <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl border ${selLayer.ring} ${selLayer.text}`}>
                <SelectedIcon className="h-6 w-6" />
              </span>
              <div>
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${selLayer.ring} ${selLayer.text}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${selLayer.dot}`} />
                  {selLayer.label}
                </span>
                <h3 className="mt-1 text-lg font-semibold text-slate-100">{selected.title}</h3>
              </div>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-slate-300">{selected.detail}</p>
            <p className="mt-4 border-t border-white/5 pt-4 text-xs text-slate-500">
              Stage {NODES.findIndex((n) => n.id === selected.id) + 1} of {NODES.length} · the backend contract and
              execution are unchanged — this view only explains the flow.
            </p>
          </m.div>
        </aside>
      </div>
    </div>
  );
}
