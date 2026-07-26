import { useEffect, useMemo, useRef, useState } from "react";
import type { IconType } from "react-icons";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { m } from "framer-motion";
import { FiActivity, FiClock, FiCornerDownLeft, FiSearch, FiTarget } from "react-icons/fi";
import { useSearch } from "@/context/SearchContext";
import { useHistory } from "@/context/HistoryContext";
import { useActivity } from "@/context/ActivityContext";
import { useAnalysis } from "@/context/AnalysisContext";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { relativeTime } from "@/lib/time";

interface Item {
  key: string;
  group: "Current" | "History" | "Activity";
  icon: IconType;
  title: string;
  subtitle: string;
  onSelect: () => void;
}

const LIMIT = 6;

/** Command-palette search over History, Activity, and the current investigation. */
export default function GlobalSearch() {
  const { open, setOpen, query, setQuery } = useSearch();
  const history = useHistory();
  const activity = useActivity();
  const { response } = useAnalysis();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  useFocusTrap(panelRef, open);

  const close = () => setOpen(false);

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase();
    const match = (...parts: (string | number | null | undefined)[]) =>
      !q || parts.filter(Boolean).join(" ").toLowerCase().includes(q);

    const out: Item[] = [];

    if (response && match(response.query, response.understanding?.intent, response.understanding?.aml_pattern)) {
      out.push({
        key: "current",
        group: "Current",
        icon: FiTarget,
        title: response.query,
        subtitle: `Active investigation · ${response.results.length} flagged`,
        onSelect: () => {
          navigate("/analyze");
          close();
        },
      });
    }

    for (const r of history.items) {
      if (out.filter((i) => i.group === "History").length >= LIMIT) break;
      if (match(r.query, r.intent, r.pattern, r.summary)) {
        out.push({
          key: `h-${r.id}`,
          group: "History",
          icon: FiClock,
          title: r.query,
          subtitle: `${r.intent ?? "—"} · ${r.flagged} flagged · ${relativeTime(r.timestamp)}`,
          onSelect: () => {
            history.view(r);
            close();
          },
        });
      }
    }

    for (const a of activity.items) {
      if (out.filter((i) => i.group === "Activity").length >= LIMIT) break;
      if (match(a.message, a.type)) {
        out.push({
          key: `a-${a.id}`,
          group: "Activity",
          icon: FiActivity,
          title: a.message,
          subtitle: relativeTime(a.timestamp),
          onSelect: () => {
            navigate("/activity");
            close();
          },
        });
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, response, history.items, activity.items]);

  useEffect(() => setActive(0), [query, open]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 20);
      return () => clearTimeout(t);
    }
  }, [open]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(items.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      items[active]?.onSelect();
    }
  };

  let renderedGroup = "";

  return createPortal(
    <div className="fixed inset-0 z-[55] flex items-start justify-center p-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Global search">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />
      <m.div
        ref={panelRef}
        initial={{ opacity: 0, y: -12, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
        className="glass relative z-10 w-full max-w-xl overflow-hidden bg-surface-900/95"
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
          <FiSearch className="h-4 w-4 shrink-0 text-slate-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search history, activity, current investigation…"
            aria-label="Search query"
            className="flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
          />
          <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500">Esc</kbd>
        </div>

        <div className="max-h-[52vh] overflow-y-auto py-2" role="listbox">
          {items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">No matches found.</p>
          ) : (
            items.map((item, i) => {
              const showHeader = item.group !== renderedGroup;
              renderedGroup = item.group;
              const Icon = item.icon;
              const isActive = i === active;
              return (
                <div key={item.key}>
                  {showHeader && (
                    <p className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600">{item.group}</p>
                  )}
                  <button
                    type="button"
                    role="option"
                    aria-selected={isActive}
                    onMouseEnter={() => setActive(i)}
                    onClick={item.onSelect}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                      isActive ? "bg-accent/10" : "hover:bg-white/5"
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-accent" : "text-slate-500"}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-slate-100">{item.title}</span>
                      <span className="block truncate text-xs text-slate-500">{item.subtitle}</span>
                    </span>
                    {isActive && <FiCornerDownLeft className="h-3.5 w-3.5 shrink-0 text-slate-500" />}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </m.div>
    </div>,
    document.body,
  );
}
