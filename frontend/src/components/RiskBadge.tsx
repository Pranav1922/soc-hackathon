import type { RiskLevel } from "@/types/api";

const STYLES: Record<RiskLevel, string> = {
  high: "border-risk-high/40 bg-risk-high/10 text-risk-high",
  medium: "border-risk-medium/40 bg-risk-medium/10 text-risk-medium",
  low: "border-risk-low/40 bg-risk-low/10 text-risk-low",
};

/** Colored pill for a risk level: high→red, medium→amber, low→green. */
export default function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${STYLES[risk]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {risk}
    </span>
  );
}
