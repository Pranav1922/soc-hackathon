import { FiBell, FiShield } from "react-icons/fi";
import { relativeTime } from "@/lib/time";

const PATTERN: Record<string, string> = {
  structuring: "border-risk-medium/40 bg-risk-medium/10 text-risk-medium",
  smurfing: "border-purple-400/40 bg-purple-400/10 text-purple-300",
  layering: "border-sky-400/40 bg-sky-400/10 text-sky-300",
  rapid_cash_out: "border-risk-high/40 bg-risk-high/10 text-risk-high",
};

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface Props {
  alerts: { id: string; pattern: string; timestamp: number }[];
}

/** Compact alerts feed derived from detected AML patterns in History. */
export default function RecentAlertsCard({ alerts }: Props) {
  return (
    <div className="glass h-full p-5">
      <div className="mb-4 flex items-center gap-2">
        <FiBell className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-slate-100">Recent Alerts</h3>
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
          <FiShield className="h-6 w-6 text-risk-low" />
          <p className="text-sm text-slate-400">No pattern alerts.</p>
          <p className="text-xs text-slate-500">Detected AML typologies will surface here.</p>
        </div>
      ) : (
        <ul className="space-y-2.5">
          {alerts.map((a) => (
            <li key={a.id} className="flex items-center gap-3">
              <span
                className={`shrink-0 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                  PATTERN[a.pattern] ?? "border-white/10 bg-white/5 text-slate-300"
                }`}
              >
                {titleCase(a.pattern)}
              </span>
              <span className="flex-1 text-sm text-slate-300">detected</span>
              <span className="shrink-0 text-xs text-slate-500">{relativeTime(a.timestamp)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
