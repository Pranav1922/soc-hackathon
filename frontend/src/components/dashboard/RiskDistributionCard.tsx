import { FiBarChart2 } from "react-icons/fi";

const TWELFTHS = ["w-0", "w-1/12", "w-2/12", "w-3/12", "w-4/12", "w-5/12", "w-6/12", "w-7/12", "w-8/12", "w-9/12", "w-10/12", "w-11/12", "w-full"];

interface Props {
  bands: { high: number; medium: number; low: number };
  totalFlagged: number;
}

const ROWS = [
  { key: "high", label: "High", bar: "bg-risk-high", text: "text-risk-high" },
  { key: "medium", label: "Medium", bar: "bg-risk-medium", text: "text-risk-medium" },
  { key: "low", label: "Low", bar: "bg-risk-low", text: "text-risk-low" },
] as const;

/**
 * Executive summary of risk posture: flagged entities by band, aggregated across
 * all locally-stored investigations. Pure CSS (twelfth-width bars) — no Plotly.
 */
export default function RiskDistributionCard({ bands, totalFlagged }: Props) {
  const max = Math.max(bands.high, bands.medium, bands.low, 1);

  return (
    <div className="glass h-full p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">Risk Distribution</h3>
        <span className="chip text-slate-500">{totalFlagged} flagged</span>
      </div>

      {totalFlagged === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
          <FiBarChart2 className="h-6 w-6 text-slate-600" />
          <p className="text-sm text-slate-400">No detections stored yet.</p>
          <p className="text-xs text-slate-500">Run investigations to build the risk profile.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {ROWS.map((row) => {
            const count = bands[row.key];
            const pct = totalFlagged ? Math.round((count / totalFlagged) * 100) : 0;
            const width = TWELFTHS[Math.round((count / max) * 12)];
            return (
              <div key={row.key}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className={`font-medium ${row.text}`}>{row.label}</span>
                  <span className="font-mono text-slate-400">
                    {count} · {pct}%
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div className={`h-full rounded-full ${row.bar} ${width} transition-all duration-500`} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
