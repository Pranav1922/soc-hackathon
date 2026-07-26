import { useEffect, useRef, useState } from "react";
import { FiDownload, FiMaximize2, FiMinimize2 } from "react-icons/fi";
import type { Config, Data, Layout } from "plotly.js";
import type { ChartSpec } from "@/types/api";
import { Plot, Plotly } from "@/lib/plotly";

// Presentation-only defaults for props the backend spec leaves unset (backgrounds,
// font, autosize). Spec-provided layout keys win via the spread, so anything the
// backend specified — axes, shapes, annotations, colors — is rendered as received.
const THEME_LAYOUT: Partial<Layout> = {
  autosize: true,
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#cbd5e1", family: "Inter, system-ui, sans-serif", size: 12 },
  margin: { l: 52, r: 24, t: 16, b: 44 },
  colorway: ["#22d3ee", "#38bdf8", "#f59e0b", "#f43f5e", "#10b981", "#a78bfa"],
  legend: { bgcolor: "rgba(0,0,0,0)" },
};

const CONFIG: Partial<Config> = { responsive: true, displaylogo: false, displayModeBar: false };

function humanize(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Reusable card wrapping a single backend chart: title, type, download + fullscreen. */
export default function ChartCard({ chart }: { chart: ChartSpec }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const gdRef = useRef<HTMLElement | null>(null);
  const [isFull, setIsFull] = useState(false);

  const spec = chart.spec as { data?: Data[]; layout?: Partial<Layout> };
  const data = spec.data ?? [];
  const layout = { ...THEME_LAYOUT, ...(spec.layout ?? {}) };

  const download = () => {
    if (!gdRef.current) return;
    void Plotly.downloadImage(gdRef.current, {
      format: "png",
      filename: chart.title || chart.type || "chart",
      width: 1280,
      height: 720,
    });
  };

  const toggleFull = () => {
    const el = cardRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  useEffect(() => {
    const onFs = () => {
      setIsFull(document.fullscreenElement === cardRef.current);
      // Fullscreen doesn't always emit a window resize — nudge Plotly to refit.
      if (gdRef.current) setTimeout(() => Plotly.Plots.resize(gdRef.current as HTMLElement), 60);
    };
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  return (
    <div
      ref={cardRef}
      className="glass flex flex-col overflow-hidden bg-surface-900/60 transition-all duration-300 hover:border-accent/25 hover:shadow-soft"
    >
      <div className="flex items-start justify-between gap-3 border-b border-white/5 px-4 py-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-slate-100">{chart.title || "Untitled chart"}</h4>
          {chart.type && (
            <span className="mt-1 inline-flex rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-500">
              {humanize(chart.type)}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={download}
            title="Download PNG"
            aria-label="Download PNG"
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent"
          >
            <FiDownload className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={toggleFull}
            title={isFull ? "Exit fullscreen" : "Fullscreen"}
            aria-label={isFull ? "Exit fullscreen" : "Fullscreen"}
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:border-accent/40 hover:text-accent"
          >
            {isFull ? <FiMinimize2 className="h-4 w-4" /> : <FiMaximize2 className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <div className="min-h-[18rem] flex-1 bg-surface-950/30 p-2">
        <Plot
          data={data}
          layout={layout}
          config={CONFIG}
          useResizeHandler
          className="h-full w-full"
          onInitialized={(_fig, gd) => (gdRef.current = gd)}
        />
      </div>
    </div>
  );
}
