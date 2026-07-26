import { useMemo, useState } from "react";
import {
  FiChevronDown,
  FiChevronUp,
  FiFilter,
  FiSearch,
  FiShield,
} from "react-icons/fi";
import type { RiskLevel, RiskResult } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";
import RecommendationChip from "@/components/RecommendationChip";
import ScoreBar from "@/components/ScoreBar";
import EmptyState from "@/components/EmptyState";
import InvestigationPanel from "@/components/InvestigationPanel";

type RiskFilter = RiskLevel | "all";
type SortKey = "score" | "entity_id";
type SortDir = "asc" | "desc";

const FILTERS: { key: RiskFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high", label: "High" },
  { key: "medium", label: "Medium" },
  { key: "low", label: "Low" },
];

/** Analyst view of the backend's results[]: filter, search, sort, expand. */
export default function ResultsTable({ results, loading }: { results: RiskResult[]; loading: boolean }) {
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const counts = useMemo(
    () => ({
      all: results.length,
      high: results.filter((r) => r.risk === "high").length,
      medium: results.filter((r) => r.risk === "medium").length,
      low: results.filter((r) => r.risk === "low").length,
    }),
    [results],
  );

  const view = useMemo(() => {
    let out = results;
    if (riskFilter !== "all") out = out.filter((r) => r.risk === riskFilter);
    const q = search.trim().toLowerCase();
    if (q) out = out.filter((r) => r.entity_id.toLowerCase().includes(q));
    const dir = sortDir === "asc" ? 1 : -1;
    return [...out].sort((a, b) =>
      sortKey === "score" ? (a.score - b.score) * dir : a.entity_id.localeCompare(b.entity_id) * dir,
    );
  }, [results, riskFilter, search, sortKey, sortDir]);

  const setSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "entity_id" ? "asc" : "desc");
    }
  };

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  // Investigation panel navigates within the currently displayed (filtered+sorted) view.
  const selectedIndex = selectedId ? view.findIndex((r) => r.entity_id === selectedId) : -1;
  const selected = selectedIndex >= 0 ? view[selectedIndex] : null;
  const goPrev = () => selectedIndex > 0 && setSelectedId(view[selectedIndex - 1].entity_id);
  const goNext = () => selectedIndex >= 0 && selectedIndex < view.length - 1 && setSelectedId(view[selectedIndex + 1].entity_id);

  if (loading) return <SkeletonTable />;

  if (results.length === 0)
    return (
      <EmptyState
        icon={FiShield}
        title="No suspicious entities"
        description="The analysis completed and found no entities meeting the risk threshold. Try a broader query or different filters."
      />
    );

  const sortArrow = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "");

  return (
    <div className="space-y-4">
      {/* Toolbar: search + risk filter + sort */}
      <div className="glass flex flex-col gap-3 p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative flex-1 lg:max-w-xs">
          <FiSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Entity ID…"
            className="w-full rounded-lg border border-white/10 bg-surface-950/60 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/20"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="hidden items-center gap-1.5 text-xs text-slate-500 sm:inline-flex">
            <FiFilter className="h-3.5 w-3.5" /> Risk
          </span>
          <div className="flex rounded-lg border border-white/10 bg-surface-950/40 p-0.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setRiskFilter(f.key)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  riskFilter === f.key ? "bg-accent/15 text-accent" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {f.label}
                <span className="ml-1 text-slate-500">{counts[f.key]}</span>
              </button>
            ))}
          </div>

          <div className="flex rounded-lg border border-white/10 bg-surface-950/40 p-0.5">
            <button
              type="button"
              onClick={() => setSort("score")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                sortKey === "score" ? "bg-accent/15 text-accent" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Score{sortArrow("score")}
            </button>
            <button
              type="button"
              onClick={() => setSort("entity_id")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                sortKey === "entity_id" ? "bg-accent/15 text-accent" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Entity ID{sortArrow("entity_id")}
            </button>
          </div>
        </div>
      </div>

      {view.length === 0 ? (
        <div className="glass px-6 py-12 text-center">
          <p className="text-sm text-slate-400">No entities match the current filters.</p>
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setRiskFilter("all");
            }}
            className="mt-3 text-sm font-medium text-accent hover:underline"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="glass hidden overflow-hidden md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">
                    <button type="button" onClick={() => setSort("entity_id")} className="hover:text-slate-200">
                      Entity ID{sortArrow("entity_id")}
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">
                    <button type="button" onClick={() => setSort("score")} className="hover:text-slate-200">
                      Score{sortArrow("score")}
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">Recommendation</th>
                  <th className="px-4 py-3 font-medium">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {view.map((r) => {
                  const isOpen = expanded.has(r.entity_id);
                  return (
                    <tr
                      key={r.entity_id}
                      onClick={() => setSelectedId(r.entity_id)}
                      title="View investigation"
                      className={`cursor-pointer align-top transition-colors hover:bg-white/[0.03] ${selectedId === r.entity_id ? "bg-accent/[0.06]" : ""}`}
                    >
                      <td className="px-4 py-3 font-mono text-slate-100">{r.entity_id}</td>
                      <td className="px-4 py-3 capitalize text-slate-400">{r.entity_type}</td>
                      <td className="px-4 py-3">
                        <RiskBadge risk={r.risk} />
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar score={r.score} risk={r.risk} />
                      </td>
                      <td className="px-4 py-3">
                        <RecommendationChip action={r.action} />
                      </td>
                      <td className="max-w-md px-4 py-3">
                        <ExplanationCell text={r.explanation} open={isOpen} onToggle={() => toggle(r.entity_id)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="space-y-3 md:hidden">
            {view.map((r) => {
              const isOpen = expanded.has(r.entity_id);
              return (
                <div
                  key={r.entity_id}
                  onClick={() => setSelectedId(r.entity_id)}
                  className={`glass cursor-pointer space-y-3 p-4 transition-colors ${selectedId === r.entity_id ? "border-accent/30" : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sm text-slate-100">{r.entity_id}</span>
                    <RiskBadge risk={r.risk} />
                  </div>
                  <p className="text-xs capitalize text-slate-500">{r.entity_type}</p>
                  <ScoreBar score={r.score} risk={r.risk} />
                  <RecommendationChip action={r.action} />
                  <ExplanationCell text={r.explanation} open={isOpen} onToggle={() => toggle(r.entity_id)} />
                </div>
              );
            })}
          </div>
        </>
      )}

      <InvestigationPanel
        result={selected}
        index={selectedIndex}
        total={view.length}
        onClose={() => setSelectedId(null)}
        onPrev={goPrev}
        onNext={goNext}
      />
    </div>
  );
}

/** Explanation with a first-line preview and expand/collapse toggle. */
function ExplanationCell({ text, open, onToggle }: { text: string; open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation(); // don't open the investigation panel when just expanding text
        onToggle();
      }}
      className="group flex w-full items-start gap-2 text-left"
      aria-expanded={open}
    >
      <span className={`text-sm leading-relaxed text-slate-300 ${open ? "" : "line-clamp-1"}`}>{text}</span>
      {open ? (
        <FiChevronUp className="mt-0.5 h-4 w-4 shrink-0 text-slate-500 group-hover:text-accent" />
      ) : (
        <FiChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-slate-500 group-hover:text-accent" />
      )}
    </button>
  );
}

/** Loading placeholder — pulsing rows. */
function SkeletonTable() {
  return (
    <div className="glass divide-y divide-white/5 overflow-hidden">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-4">
          <div className="h-4 w-24 animate-pulse rounded bg-white/10" />
          <div className="h-5 w-16 animate-pulse rounded-full bg-white/10" />
          <div className="h-2 flex-1 animate-pulse rounded-full bg-white/10" />
          <div className="hidden h-5 w-20 animate-pulse rounded-full bg-white/10 sm:block" />
          <div className="hidden h-4 w-40 animate-pulse rounded bg-white/10 lg:block" />
        </div>
      ))}
    </div>
  );
}
