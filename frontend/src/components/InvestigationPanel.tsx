import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { FiChevronLeft, FiChevronRight, FiUser, FiX } from "react-icons/fi";
import type { RiskResult } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";
import RecommendationChip from "@/components/RecommendationChip";
import ScoreBar from "@/components/ScoreBar";
import JsonBlock from "@/components/JsonBlock";

interface InvestigationPanelProps {
  result: RiskResult | null;
  index: number;
  total: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      {children}
    </div>
  );
}

/**
 * Slide-in investigation panel (side panel on desktop, full-width drawer on mobile).
 * Renders only fields already present on the RiskResult — nothing inferred.
 */
export default function InvestigationPanel({ result, index, total, onClose, onPrev, onNext }: InvestigationPanelProps) {
  const open = result !== null;
  // Keep the last selection visible through the slide-out so content doesn't blank mid-animation.
  const [snap, setSnap] = useState<{ result: RiskResult; index: number; total: number } | null>(null);
  useEffect(() => {
    if (result) setSnap({ result, index, total });
  }, [result, index, total]);

  const current = result ? { result, index, total } : snap;
  const hasPrev = current ? current.index > 0 : false;
  const hasNext = current ? current.index >= 0 && current.index < current.total - 1 : false;

  // Keyboard navigation + body scroll lock while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft" && hasPrev) onPrev();
      else if (e.key === "ArrowRight" && hasNext) onNext();
    };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("overflow-hidden");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("overflow-hidden");
    };
  }, [open, hasPrev, hasNext, onClose, onPrev, onNext]);

  const navBtn =
    "inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-accent/40 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/10 disabled:hover:text-slate-300";

  // Portal to <body> so `position: fixed` resolves against the viewport, not a
  // transformed ancestor (the animate-fade-up sections establish a containing block).
  return createPortal(
    <div className={`fixed inset-0 z-50 ${open ? "" : "pointer-events-none"}`} aria-hidden={!open}>
      {/* backdrop */}
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0"}`}
      />
      {/* panel */}
      <aside
        role="dialog"
        aria-label="Investigation details"
        className={`absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-white/10 bg-surface-900/95 shadow-2xl backdrop-blur-xl transition-transform duration-300 ease-out ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {/* header + navigation */}
        <div className="sticky top-0 z-10 border-b border-white/10 bg-surface-900/95 backdrop-blur-xl">
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-500">Investigation</p>
              <p className="text-sm font-semibold text-slate-100">Entity details</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close investigation"
              className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent"
            >
              <FiX className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center justify-between border-t border-white/5 px-5 py-2.5">
            <button type="button" onClick={onPrev} disabled={!hasPrev} className={navBtn}>
              <FiChevronLeft className="h-3.5 w-3.5" /> Prev
            </button>
            <span className="text-xs text-slate-500">
              {current && current.index >= 0 ? `${current.index + 1} of ${current.total}` : ""}
            </span>
            <button type="button" onClick={onNext} disabled={!hasNext} className={navBtn}>
              Next <FiChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* body */}
        {current && (
          <div key={current.result.entity_id} className="animate-fade-up flex-1 space-y-6 overflow-y-auto p-5">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/5 text-accent">
                <FiUser className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate font-mono text-lg font-semibold text-slate-100">{current.result.entity_id}</p>
                <p className="text-xs capitalize text-slate-500">{current.result.entity_type}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Section label="Risk">
                <RiskBadge risk={current.result.risk} />
              </Section>
              <Section label="Recommendation">
                <RecommendationChip action={current.result.action} />
              </Section>
            </div>

            <Section label="Risk Score">
              <ScoreBar score={current.result.score} risk={current.result.risk} />
            </Section>

            <Section label="Explanation">
              <p className="text-sm leading-relaxed text-slate-300">{current.result.explanation}</p>
            </Section>

            <Section label="Evidence">
              <JsonBlock value={current.result.evidence} />
            </Section>
          </div>
        )}
      </aside>
    </div>,
    document.body,
  );
}
