import type { IconType } from "react-icons";

interface StatCardProps {
  label: string;
  value: string;
  icon: IconType;
  hint?: string;
  accent?: "cyan" | "rose" | "amber" | "emerald";
}

const ACCENT: Record<NonNullable<StatCardProps["accent"]>, string> = {
  cyan: "text-accent",
  rose: "text-risk-high",
  amber: "text-risk-medium",
  emerald: "text-risk-low",
};

/** Compact KPI tile used on the dashboard. Purely presentational. */
export default function StatCard({ label, value, icon: Icon, hint, accent = "cyan" }: StatCardProps) {
  return (
    <div className="glass glass-hover animate-fade-up p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-slate-100">{value}</p>
        </div>
        <div className={`grid h-9 w-9 place-items-center rounded-lg bg-white/5 ${ACCENT[accent]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      {hint && <p className="mt-3 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
