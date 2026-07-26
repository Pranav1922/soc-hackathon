import { Link } from "react-router-dom";
import { FiChevronRight, FiEye, FiSearch } from "react-icons/fi";
import type { HistoryRecord } from "@/types/workflow";
import { relativeTime } from "@/lib/time";

function riskBand(v: number): { label: string; cls: string } {
  if (v >= 0.66) return { label: "High", cls: "text-risk-high" };
  if (v >= 0.33) return { label: "Medium", cls: "text-risk-medium" };
  return { label: "Low", cls: "text-risk-low" };
}

function confidencePct(r: HistoryRecord): string {
  const c = r.response?.understanding?.confidence;
  return typeof c === "number" ? `${Math.round(c * 100)}%` : "—";
}

interface Props {
  records: HistoryRecord[];
  onView: (r: HistoryRecord) => void;
}

/** Latest five investigations from History; a row reopens that investigation. */
export default function RecentInvestigationsCard({ records, onView }: Props) {
  return (
    <div className="glass h-full overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
        <h3 className="text-sm font-semibold text-slate-100">Recent Investigations</h3>
        {records.length > 0 && (
          <Link to="/history" className="text-xs font-medium text-accent hover:underline">
            View all
          </Link>
        )}
      </div>

      {records.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/10 bg-white/5 text-accent">
            <FiSearch className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-100">No investigations yet</p>
            <p className="mt-1 text-xs text-slate-400">Run your first analysis to populate this panel.</p>
          </div>
          <Link to="/analyze" className="btn-accent">
            <FiSearch className="h-4 w-4" />
            New Investigation
          </Link>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Time</th>
                  <th className="px-5 py-2.5 font-medium">Query</th>
                  <th className="px-5 py-2.5 font-medium">Pattern</th>
                  <th className="px-5 py-2.5 font-medium">Risk</th>
                  <th className="px-5 py-2.5 font-medium">Confidence</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {records.map((r) => {
                  const band = riskBand(r.avgRisk);
                  const flagged = r.flagged > 0;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => onView(r)}
                      title="View investigation"
                      className="cursor-pointer transition-colors hover:bg-white/[0.03]"
                    >
                      <td className="whitespace-nowrap px-5 py-3 text-slate-400">{relativeTime(r.timestamp)}</td>
                      <td className="max-w-[16rem] px-5 py-3">
                        <span className="block truncate font-medium text-slate-100">{r.query}</span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 capitalize text-slate-400">{r.pattern ?? "none"}</td>
                      <td className={`whitespace-nowrap px-5 py-3 font-medium ${band.cls}`}>
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />
                          {band.label}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 font-mono text-slate-300">{confidencePct(r)}</td>
                      <td className="whitespace-nowrap px-5 py-3">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                            flagged
                              ? "border-risk-medium/30 bg-risk-medium/10 text-risk-medium"
                              : "border-risk-low/30 bg-risk-low/10 text-risk-low"
                          }`}
                        >
                          {flagged ? "Flagged" : "Clear"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onView(r);
                          }}
                          aria-label={`View investigation: ${r.query}`}
                          className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent"
                        >
                          <FiEye className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <ul className="divide-y divide-white/5 md:hidden">
            {records.map((r) => {
              const band = riskBand(r.avgRisk);
              return (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => onView(r)}
                    className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-white/[0.03]"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-100">{r.query}</span>
                      <span className="mt-0.5 block text-xs text-slate-500">
                        {relativeTime(r.timestamp)} · <span className={band.cls}>{band.label}</span> · {r.flagged} flagged
                      </span>
                    </span>
                    <FiChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
