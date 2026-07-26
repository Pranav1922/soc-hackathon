import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { IconType } from "react-icons";
import {
  FiActivity,
  FiBarChart2,
  FiCheckCircle,
  FiClock,
  FiDownload,
  FiGitMerge,
  FiPower,
  FiRotateCcw,
  FiSearch,
  FiServer,
  FiShare2,
  FiTrash2,
} from "react-icons/fi";
import type { ActivityType } from "@/types/workflow";
import { useActivity } from "@/context/ActivityContext";
import { useToast } from "@/context/ToastContext";
import { relativeTime, absoluteTime } from "@/lib/time";
import EmptyState from "@/components/EmptyState";

type Category = "Investigation" | "Navigation" | "Export" | "System";

const META: Record<ActivityType, { icon: IconType; cls: string; category: Category }> = {
  app_started: { icon: FiPower, cls: "text-slate-400 border-white/15 bg-white/5", category: "System" },
  backend_connected: { icon: FiServer, cls: "text-risk-low border-risk-low/40 bg-risk-low/10", category: "System" },
  investigation_started: { icon: FiSearch, cls: "text-accent border-accent/40 bg-accent/10", category: "Investigation" },
  investigation_completed: { icon: FiCheckCircle, cls: "text-risk-low border-risk-low/40 bg-risk-low/10", category: "Investigation" },
  charts_generated: { icon: FiBarChart2, cls: "text-purple-300 border-purple-400/40 bg-purple-400/10", category: "Investigation" },
  pipeline_viewed: { icon: FiGitMerge, cls: "text-sky-300 border-sky-400/40 bg-sky-400/10", category: "Navigation" },
  architecture_viewed: { icon: FiShare2, cls: "text-sky-300 border-sky-400/40 bg-sky-400/10", category: "Navigation" },
  history_opened: { icon: FiClock, cls: "text-sky-300 border-sky-400/40 bg-sky-400/10", category: "Navigation" },
  investigation_restored: { icon: FiRotateCcw, cls: "text-accent border-accent/40 bg-accent/10", category: "Investigation" },
  investigation_deleted: { icon: FiTrash2, cls: "text-risk-high border-risk-high/40 bg-risk-high/10", category: "Investigation" },
  history_cleared: { icon: FiTrash2, cls: "text-risk-high border-risk-high/40 bg-risk-high/10", category: "System" },
  activity_cleared: { icon: FiTrash2, cls: "text-risk-high border-risk-high/40 bg-risk-high/10", category: "System" },
  export: { icon: FiDownload, cls: "text-risk-medium border-risk-medium/40 bg-risk-medium/10", category: "Export" },
};

const FILTERS: (Category | "All")[] = ["All", "Investigation", "Navigation", "Export", "System"];

export default function Activity() {
  const { items, clear, log } = useActivity();
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Category | "All">("All");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((e) => {
      if (filter !== "All" && META[e.type].category !== filter) return false;
      if (q && !`${e.message} ${e.type}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [items, search, filter]);

  const onClear = () => {
    if (items.length === 0) return;
    clear();
    log("activity_cleared", "Activity cleared");
    toast("Activity cleared", "success");
  };

  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <h2 className="text-2xl font-bold tracking-tight text-slate-100">Activity Timeline</h2>
        <p className="mt-1 text-sm text-slate-400">A live, local record of what's happened in this session. {items.length} events.</p>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={FiActivity}
          title="No activity yet"
          description="As you run investigations and navigate the console, meaningful events are recorded here automatically."
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
          <div className="glass flex flex-col gap-3 p-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative flex-1 lg:max-w-xs">
              <FiSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search activity…"
                aria-label="Search activity"
                className="w-full rounded-lg border border-white/10 bg-surface-950/60 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-lg border border-white/10 bg-surface-950/40 p-0.5" role="tablist" aria-label="Filter activity">
                {FILTERS.map((f) => (
                  <button
                    key={f}
                    type="button"
                    role="tab"
                    aria-selected={filter === f}
                    onClick={() => setFilter(f)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      filter === f ? "bg-accent/15 text-accent" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={onClear}
                className="inline-flex items-center gap-2 rounded-xl border border-risk-high/30 bg-risk-high/10 px-3 py-2 text-xs font-semibold text-risk-high transition hover:bg-risk-high/20"
              >
                <FiTrash2 className="h-4 w-4" />
                Clear
              </button>
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="glass px-6 py-12 text-center text-sm text-slate-400">No activity matches your filters.</div>
          ) : (
            <ol className="space-y-0">
              {filtered.map((e, i) => {
                const meta = META[e.type];
                const Icon = meta.icon;
                const last = i === filtered.length - 1;
                return (
                  <li key={e.id} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <span className={`z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full border ${meta.cls}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      {!last && <span className="my-1 w-px flex-1 bg-white/10" />}
                    </div>
                    <div className="glass mb-3 flex-1 p-3.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm text-slate-200">{e.message}</p>
                        <time
                          className="shrink-0 text-xs text-slate-500"
                          dateTime={new Date(e.timestamp).toISOString()}
                          title={absoluteTime(e.timestamp)}
                        >
                          {relativeTime(e.timestamp)}
                        </time>
                      </div>
                      <span className={`mt-1.5 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${meta.cls}`}>
                        {meta.category}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
