import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  FiClock,
  FiDownload,
  FiEye,
  FiRepeat,
  FiSearch,
  FiTrash2,
} from "react-icons/fi";
import type { HistoryRecord } from "@/types/workflow";
import { useHistory } from "@/context/HistoryContext";
import { useActivity } from "@/context/ActivityContext";
import { useToast } from "@/context/ToastContext";
import { useAnalysis } from "@/context/AnalysisContext";
import { downloadBlob, downloadJSON, historyToCSV } from "@/lib/export";
import { relativeTime } from "@/lib/time";
import EmptyState from "@/components/EmptyState";

function riskBand(v: number): { label: string; cls: string } {
  if (v >= 0.66) return { label: "high", cls: "text-risk-high" };
  if (v >= 0.33) return { label: "medium", cls: "text-risk-medium" };
  return { label: "low", cls: "text-risk-low" };
}

function IconBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent"
    >
      {children}
    </button>
  );
}

export default function History() {
  const { items, remove, clear, view } = useHistory();
  const { log } = useActivity();
  const { toast } = useToast();
  const { analyze } = useAnalysis();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  // Newest first is guaranteed by the store (add prepends); apply search only.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((r) => [r.query, r.intent, r.pattern, r.summary].filter(Boolean).join(" ").toLowerCase().includes(q));
  }, [items, search]);

  const onDelete = (r: HistoryRecord) => {
    remove(r.id);
    log("investigation_deleted", `Deleted “${r.query}”`);
    toast("History entry deleted", "success");
  };
  const onClearAll = () => {
    if (items.length === 0) return;
    clear();
    log("history_cleared", "History cleared");
    toast("History cleared", "success");
  };
  const onCSV = () => {
    downloadBlob("aegis-history.csv", historyToCSV(items), "text/csv");
    log("export", "Exported history to CSV");
    toast("CSV export complete", "success");
  };
  const onJson = (r: HistoryRecord) => {
    downloadJSON(`investigation-${r.id}.json`, r.response ?? r);
    log("export", `Downloaded JSON “${r.query}”`);
    toast("Download started", "success");
  };
  const onDuplicate = (r: HistoryRecord) => {
    void analyze(r.query);
    toast("Re-running investigation…", "info");
    navigate("/analyze");
  };

  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <h2 className="text-2xl font-bold tracking-tight text-slate-100">Investigation History</h2>
        <p className="mt-1 text-sm text-slate-400">
          Every completed investigation, saved locally in your browser. {items.length} stored.
        </p>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={FiClock}
          title="No investigations yet"
          description="Investigations you run are saved here automatically — search, re-open, duplicate, or export them anytime."
          action={
            <Link to="/analyze" className="btn-accent">
              <FiSearch className="h-4 w-4" />
              Start an investigation
            </Link>
          }
        />
      ) : (
        <>
          {/* Toolbar */}
          <div className="glass flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1 sm:max-w-xs">
              <FiSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search history…"
                aria-label="Search history"
                className="w-full rounded-lg border border-white/10 bg-surface-950/60 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div className="flex items-center gap-2">
              <button type="button" onClick={onCSV} className="btn-outline px-3 py-2 text-xs">
                <FiDownload className="h-4 w-4" />
                Download CSV
              </button>
              <button
                type="button"
                onClick={onClearAll}
                className="inline-flex items-center gap-2 rounded-xl border border-risk-high/30 bg-risk-high/10 px-3 py-2 text-xs font-semibold text-risk-high transition hover:bg-risk-high/20"
              >
                <FiTrash2 className="h-4 w-4" />
                Delete all
              </button>
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="glass px-6 py-12 text-center">
              <p className="text-sm text-slate-400">No history matches “{search}”.</p>
              <button type="button" onClick={() => setSearch("")} className="mt-3 text-sm font-medium text-accent hover:underline">
                Clear search
              </button>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="glass hidden overflow-x-auto md:block">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Time</th>
                      <th className="px-4 py-3 font-medium">Query</th>
                      <th className="px-4 py-3 font-medium">Intent</th>
                      <th className="px-4 py-3 font-medium">Pattern</th>
                      <th className="px-4 py-3 font-medium">Risk</th>
                      <th className="px-4 py-3 font-medium">Flagged</th>
                      <th className="px-4 py-3 text-right font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {filtered.map((r) => {
                      const band = riskBand(r.avgRisk);
                      return (
                        <tr key={r.id} className="transition-colors hover:bg-white/[0.02]">
                          <td className="whitespace-nowrap px-4 py-3 text-slate-400">{relativeTime(r.timestamp)}</td>
                          <td className="max-w-xs px-4 py-3">
                            <span className="block truncate font-medium text-slate-100">{r.query}</span>
                            <span className="block truncate text-xs text-slate-500">{r.summary}</span>
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 capitalize text-slate-400">{r.intent ?? "—"}</td>
                          <td className="whitespace-nowrap px-4 py-3 capitalize text-slate-400">{r.pattern ?? "none"}</td>
                          <td className={`whitespace-nowrap px-4 py-3 font-mono ${band.cls}`}>
                            <span className="inline-flex items-center gap-1.5">
                              <span className="h-1.5 w-1.5 rounded-full bg-current" />
                              {r.avgRisk.toFixed(2)}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-300">{r.flagged}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-1.5">
                              <IconBtn label="View investigation" onClick={() => view(r)}>
                                <FiEye className="h-4 w-4" />
                              </IconBtn>
                              <IconBtn label="Duplicate investigation" onClick={() => onDuplicate(r)}>
                                <FiRepeat className="h-4 w-4" />
                              </IconBtn>
                              <IconBtn label="Download JSON" onClick={() => onJson(r)}>
                                <FiDownload className="h-4 w-4" />
                              </IconBtn>
                              <IconBtn label="Delete entry" onClick={() => onDelete(r)}>
                                <FiTrash2 className="h-4 w-4" />
                              </IconBtn>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="space-y-3 md:hidden">
                {filtered.map((r) => {
                  const band = riskBand(r.avgRisk);
                  return (
                    <div key={r.id} className="glass space-y-3 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <span className="min-w-0 truncate font-medium text-slate-100">{r.query}</span>
                        <span className="shrink-0 text-xs text-slate-500">{relativeTime(r.timestamp)}</span>
                      </div>
                      <p className="text-xs text-slate-500">{r.summary}</p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span className="capitalize">{r.intent ?? "—"}</span>·<span className="capitalize">{r.pattern ?? "none"}</span>·
                        <span className={`font-mono ${band.cls}`}>risk {r.avgRisk.toFixed(2)}</span>·
                        <span className="font-mono">{r.flagged} flagged</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <IconBtn label="View investigation" onClick={() => view(r)}>
                          <FiEye className="h-4 w-4" />
                        </IconBtn>
                        <IconBtn label="Duplicate investigation" onClick={() => onDuplicate(r)}>
                          <FiRepeat className="h-4 w-4" />
                        </IconBtn>
                        <IconBtn label="Download JSON" onClick={() => onJson(r)}>
                          <FiDownload className="h-4 w-4" />
                        </IconBtn>
                        <IconBtn label="Delete entry" onClick={() => onDelete(r)}>
                          <FiTrash2 className="h-4 w-4" />
                        </IconBtn>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
