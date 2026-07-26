import { useState } from "react";
import type { IconType } from "react-icons";
import { FiArrowRight, FiCheck, FiChevronDown, FiClock, FiLoader, FiSkipForward, FiX } from "react-icons/fi";
import type { ExecutionStatus, ExecutionStep, ToolName, TraceEntry } from "@/types/api";
import JsonBlock from "@/components/JsonBlock";

type StatusKind = ExecutionStatus | "RUNNING";

interface Step {
  order: number;
  tool: ToolName;
  status: StatusKind;
  confidence?: number;
  reason?: string;
  inputs?: Record<string, unknown>;
  trace?: TraceEntry;
  executed: boolean;
}

/** Zip plan + trace (shared `tool` key), then append skipped tools as non-executed steps. */
function buildSteps(plan: ExecutionStep[], trace: TraceEntry[], skipped: ToolName[]): Step[] {
  const steps: Step[] = plan.map((s, i) => {
    const t = trace.find((x) => x.tool === s.tool);
    return {
      order: i + 1,
      tool: s.tool,
      status: t?.status ?? "SUCCESS",
      confidence: s.confidence,
      reason: s.reason,
      inputs: s.inputs,
      trace: t,
      executed: true,
    };
  });
  skipped.forEach((tool) => steps.push({ order: 0, tool, status: "SKIPPED", executed: false }));
  // Number sequentially — skipped steps continue the count after executed ones.
  return steps.map((s, i) => ({ ...s, order: i + 1 }));
}

const STATUS: Record<StatusKind, { label: string; text: string; ring: string; Icon: IconType }> = {
  SUCCESS: { label: "Completed", text: "text-risk-low", ring: "border-risk-low/40 bg-risk-low/10", Icon: FiCheck },
  SKIPPED: { label: "Skipped", text: "text-slate-400", ring: "border-white/15 bg-white/5", Icon: FiSkipForward },
  ERROR: { label: "Failed", text: "text-risk-high", ring: "border-risk-high/40 bg-risk-high/10", Icon: FiX },
  RUNNING: { label: "Running", text: "text-accent", ring: "border-accent/40 bg-accent/10", Icon: FiLoader },
};

function StatusBadge({ status }: { status: StatusKind }) {
  const s = STATUS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${s.ring} ${s.text}`}
    >
      <s.Icon className={`h-3 w-3 ${status === "RUNNING" ? "animate-spin" : ""}`} />
      {s.label}
    </span>
  );
}

const nf = new Intl.NumberFormat("en-US");

/** Vertical timeline: one node per step with status, confidence, reason, metrics. */
function Timeline({ steps }: { steps: Step[] }) {
  return (
    <ol className="space-y-0">
      {steps.map((step, i) => {
        const s = STATUS[step.status];
        const last = i === steps.length - 1;
        return (
          <li key={`${step.tool}-${i}`} className="flex gap-4">
            {/* rail: status node + animated connector */}
            <div className="flex flex-col items-center">
              <span
                className={`z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full border ${s.ring} ${s.text} ${
                  step.status === "SUCCESS" ? "shadow-[0_0_14px_-2px_rgba(16,185,129,0.55)]" : ""
                }`}
              >
                <s.Icon className={`h-4 w-4 ${step.status === "RUNNING" ? "animate-spin" : ""}`} />
              </span>
              {!last && <span className={`my-1 flex-1 ${step.executed ? "flow-connector" : "flow-connector--muted"}`} />}
            </div>
            {/* card */}
            <div className={`glass mb-4 flex-1 p-4 ${step.executed ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-slate-500">#{step.order}</span>
                <span className="font-semibold text-slate-100">{step.tool}</span>
                <StatusBadge status={step.status} />
                {step.confidence !== undefined && (
                  <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent">
                    {Math.round(step.confidence * 100)}% confidence
                  </span>
                )}
              </div>
              {step.reason && <p className="mt-2 text-sm leading-relaxed text-slate-400">{step.reason}</p>}
              {step.trace && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[11px] text-slate-400">
                    {nf.format(step.trace.rows_in)}
                    <FiArrowRight className="h-3 w-3" />
                    {nf.format(step.trace.rows_out)} rows
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[11px] text-slate-400">
                    <FiClock className="h-3 w-3" />
                    {nf.format(step.trace.duration_ms)} ms
                  </span>
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Trace accordion: each step expands to formatted Inputs + Output JSON. */
function TraceAccordion({ steps }: { steps: Step[] }) {
  const [open, setOpen] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const isOpen = open.has(i);
        const s = STATUS[step.status];
        return (
          <div key={`${step.tool}-${i}`} className="glass overflow-hidden">
            <button
              type="button"
              onClick={() => toggle(i)}
              aria-expanded={isOpen}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
            >
              <span className={`h-2 w-2 shrink-0 rounded-full ${s.ring} ${s.text}`} />
              <span className="font-mono text-sm text-slate-100">{step.tool}</span>
              <StatusBadge status={step.status} />
              <FiChevronDown className={`ml-auto h-4 w-4 text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </button>
            <div className={`grid transition-all duration-300 ease-out ${isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
              <div className="overflow-hidden">
                <div className="space-y-3 border-t border-white/5 px-4 py-3">
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">Inputs</p>
                    <JsonBlock value={step.inputs ?? {}} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">Output</p>
                    {step.trace ? (
                      <JsonBlock
                        value={{
                          status: step.trace.status,
                          rows_in: step.trace.rows_in,
                          rows_out: step.trace.rows_out,
                          duration_ms: step.trace.duration_ms,
                        }}
                      />
                    ) : (
                      <p className="text-xs text-slate-500">Not executed — skipped for this query.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SkeletonPipeline() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <div className="h-8 w-8 shrink-0 animate-pulse rounded-full bg-white/10" />
          <div className="glass flex-1 space-y-2 p-4">
            <div className="h-4 w-40 animate-pulse rounded bg-white/10" />
            <div className="h-3 w-3/4 animate-pulse rounded bg-white/10" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface PipelinePanelProps {
  plan: ExecutionStep[];
  trace: TraceEntry[];
  skipped: ToolName[];
  loading: boolean;
}

/** Composes the execution timeline + the expandable trace beneath it. */
export default function PipelinePanel({ plan, trace, skipped, loading }: PipelinePanelProps) {
  if (loading) return <SkeletonPipeline />;
  const steps = buildSteps(plan, trace, skipped);
  if (steps.length === 0) return <p className="text-sm text-slate-500">No execution steps were recorded for this query.</p>;

  return (
    <div className="space-y-6">
      <Timeline steps={steps} />
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Execution Trace</h4>
        <TraceAccordion steps={steps} />
      </div>
    </div>
  );
}
