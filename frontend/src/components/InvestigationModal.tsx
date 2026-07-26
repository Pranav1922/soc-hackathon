import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { m } from "framer-motion";
import { FiArchive, FiCopy, FiDownload, FiPrinter, FiX } from "react-icons/fi";
import type { HistoryRecord } from "@/types/workflow";
import { useToast } from "@/context/ToastContext";
import { useActivity } from "@/context/ActivityContext";
import { copyText, downloadJSON, printInvestigation } from "@/lib/export";
import { absoluteTime } from "@/lib/time";
import ResultsTable from "@/components/ResultsTable";
import ChartsGrid from "@/components/ChartsGrid";
import PipelinePanel from "@/components/PipelinePanel";
import EmptyState from "@/components/EmptyState";

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-200">{value}</span>
    </span>
  );
}

/** Read-only reconstruction of a stored investigation (client-side only). */
export default function InvestigationModal({ record, onClose }: { record: HistoryRecord; onClose: () => void }) {
  const { toast } = useToast();
  const { log } = useActivity();
  const panelRef = useRef<HTMLDivElement>(null);
  const res = record.response;

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    log("investigation_restored", `Reopened “${record.query}”`);
    toast("Investigation restored", "info");
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("overflow-hidden");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("overflow-hidden");
      prev?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCopy = async () => {
    const ok = await copyText(JSON.stringify(res ?? record, null, 2));
    toast(ok ? "Investigation copied" : "Copy failed", ok ? "success" : "error");
    if (ok) log("export", `Copied investigation “${record.query}”`);
  };
  const onJson = () => {
    downloadJSON(`investigation-${record.id}.json`, res ?? record);
    toast("Download started", "success");
    log("export", `Downloaded JSON “${record.query}”`);
  };
  const onPrint = () => {
    if (printInvestigation(record)) log("export", `Printed “${record.query}”`);
    else toast("Enable pop-ups to print the summary", "error");
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
      <m.div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      />
      <m.div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Investigation: ${record.query}`}
        tabIndex={-1}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="glass relative z-10 my-2 w-full max-w-5xl bg-surface-900/95 outline-none"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-white/10 bg-surface-900/95 px-5 py-4 backdrop-blur-xl">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wider text-slate-500">Investigation</p>
            <h3 className="truncate text-lg font-semibold text-slate-100">“{record.query}”</h3>
            <p className="mt-0.5 text-xs text-slate-500">{absoluteTime(record.timestamp)}</p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <button type="button" onClick={onCopy} title="Copy investigation" aria-label="Copy investigation" className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent">
              <FiCopy className="h-4 w-4" />
            </button>
            <button type="button" onClick={onJson} title="Download JSON" aria-label="Download JSON" className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent">
              <FiDownload className="h-4 w-4" />
            </button>
            <button type="button" onClick={onPrint} title="Print summary" aria-label="Print summary" className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent">
              <FiPrinter className="h-4 w-4" />
            </button>
            <button type="button" onClick={onClose} title="Close" aria-label="Close" className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent">
              <FiX className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-6 p-5">
          <div className="flex flex-wrap gap-2">
            <Chip label="Intent" value={record.intent ?? "—"} />
            <Chip label="Pattern" value={record.pattern ?? "none"} />
            <Chip label="Flagged" value={String(record.flagged)} />
            <Chip label="Avg risk" value={record.avgRisk.toFixed(2)} />
          </div>

          {res ? (
            <>
              <section className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Results</h4>
                <ResultsTable results={res.results} loading={false} />
              </section>
              <section className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Visualizations</h4>
                <ChartsGrid charts={res.charts} loading={false} />
              </section>
              <section className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Execution Pipeline</h4>
                <PipelinePanel plan={res.plan} trace={res.trace} skipped={res.skipped} loading={false} />
              </section>
            </>
          ) : (
            <EmptyState
              icon={FiArchive}
              title="Full reconstruction unavailable"
              description={`This older entry was trimmed to save space, so the results and charts can't be reopened locally. Stored summary: ${record.summary}`}
            />
          )}
        </div>
      </m.div>
    </div>,
    document.body,
  );
}
