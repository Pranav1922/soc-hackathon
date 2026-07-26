import type { RiskLevel } from "@/types/api";

const FILL: Record<RiskLevel, string> = {
  high: "bg-risk-high",
  medium: "bg-risk-medium",
  low: "bg-risk-low",
};

const TWELFTHS = ["w-0", "w-1/12", "w-2/12", "w-3/12", "w-4/12", "w-5/12", "w-6/12", "w-7/12", "w-8/12", "w-9/12", "w-10/12", "w-11/12", "w-full"];

/** Horizontal progress bar for a 0–1 risk score. Width snaps to the nearest twelfth (safelisted classes). */
export default function ScoreBar({ score, risk }: { score: number; risk: RiskLevel }) {
  const clamped = Math.max(0, Math.min(1, score));
  const width = TWELFTHS[Math.round(clamped * 12)];
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full min-w-[3rem] max-w-[9rem] overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${FILL[risk]} ${width}`} />
      </div>
      <span className="w-9 shrink-0 text-right font-mono text-xs tabular-nums text-slate-300">
        {score.toFixed(2)}
      </span>
    </div>
  );
}
