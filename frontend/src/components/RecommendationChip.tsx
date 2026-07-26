import type { EscalationAction } from "@/types/api";

const STYLES: Record<EscalationAction, string> = {
  monitor: "border-risk-low/40 bg-risk-low/10 text-risk-low",
  review: "border-risk-medium/40 bg-risk-medium/10 text-risk-medium",
  report: "border-risk-high/40 bg-risk-high/10 text-risk-high",
};

const LABELS: Record<EscalationAction, string> = {
  monitor: "Monitor",
  review: "Review",
  report: "Report",
};

/** Colored chip for the recommended escalation action. */
export default function RecommendationChip({ action }: { action: EscalationAction }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${STYLES[action]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[action]}
    </span>
  );
}
