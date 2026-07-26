import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { FiActivity, FiMessageSquare, FiSearch, FiTarget, FiTrendingUp } from "react-icons/fi";
import { useAnalysis } from "@/context/AnalysisContext";
import { useActivity } from "@/context/ActivityContext";
import Spinner from "@/components/Spinner";
import ErrorBanner from "@/components/ErrorBanner";
import InfoCard from "@/components/InfoCard";
import ResultsTable from "@/components/ResultsTable";
import PipelinePanel from "@/components/PipelinePanel";
import ChartsGrid from "@/components/ChartsGrid";

const EXAMPLES = ["Find suspicious structuring", "Analyze customer C12345", "Show rapid cash-out patterns"];

/** snake_case / lowercase enum value → "Title Case" for display. */
function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Phase 3 Analyze screen: submit a natural-language query and show the backend's
 * *understanding* only (query, intent, AML pattern, confidence). Results/charts
 * are intentionally not rendered yet — they land in later phases.
 */
export default function Analyze() {
  const [query, setQuery] = useState("");
  const { analyze, loading, error, response } = useAnalysis();
  const { log } = useActivity();

  const runAnalyze = () => {
    const q = query.trim();
    if (q && !loading) {
      log("investigation_started", `Investigation started — “${q}”`);
      void analyze(q);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    runAnalyze();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      runAnalyze();
    }
  };

  const understanding = response?.understanding ?? null;
  const canSubmit = query.trim().length > 0 && !loading;

  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <h2 className="text-2xl font-bold tracking-tight text-slate-100">Analyze</h2>
        <p className="mt-1 text-sm text-slate-400">
          Describe suspicious activity in plain language. The agent interprets intent before running detection.
        </p>
      </div>

      {/* Query form */}
      <form onSubmit={onSubmit} className="glass animate-fade-up space-y-4 p-5">
        <label htmlFor="query" className="sr-only">
          Investigation query
        </label>
        <textarea
          id="query"
          rows={4}
          value={query}
          disabled={loading}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Describe the suspicious activity you want to investigate..."
          className="w-full resize-y rounded-xl border border-white/10 bg-surface-950/60 px-4 py-3 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={loading}
                onClick={() => setQuery(ex)}
                className="chip hover:border-accent/40 hover:text-accent disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
          <button type="submit" disabled={!canSubmit} className="btn-accent">
            {loading ? (
              <>
                <Spinner /> Analyzing…
              </>
            ) : (
              <>
                <FiSearch className="h-4 w-4" /> Analyze
              </>
            )}
          </button>
        </div>
      </form>

      {error && <ErrorBanner error={error} onRetry={runAnalyze} />}

      {/* Understanding only — no results/charts in Phase 3 */}
      {understanding && (
        <section className="animate-fade-up space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Understanding</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <InfoCard
              className="md:col-span-2 xl:col-span-4"
              label="Query"
              value={response?.query}
              icon={FiMessageSquare}
              accent="slate"
            />
            <InfoCard label="Intent" value={titleCase(understanding.intent)} icon={FiTarget} accent="cyan" />
            <InfoCard
              label="AML Pattern"
              value={understanding.aml_pattern === "none" ? "None detected" : titleCase(understanding.aml_pattern)}
              icon={FiActivity}
              accent={understanding.aml_pattern === "none" ? "slate" : "amber"}
            />
            <InfoCard
              label="Confidence"
              value={`${Math.round(understanding.confidence * 100)}%`}
              icon={FiTrendingUp}
              accent="emerald"
            />
          </div>
        </section>
      )}

      {/* Results — skeleton while loading, then the analyst table (or empty state) */}
      {(loading || response) && (
        <section className="animate-fade-up space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Results</h3>
            {response && (
              <span className="text-xs text-slate-500">
                {response.results.length} {response.results.length === 1 ? "entity" : "entities"}
              </span>
            )}
          </div>
          <ResultsTable results={response?.results ?? []} loading={loading} />
        </section>
      )}

      {/* Visualizations — every chart from response.charts, rendered as received */}
      {(loading || response) && (
        <section className="animate-fade-up space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Visualizations</h3>
            {response && response.charts.length > 0 && (
              <span className="text-xs text-slate-500">
                {response.charts.length} {response.charts.length === 1 ? "chart" : "charts"}
              </span>
            )}
          </div>
          <ChartsGrid charts={response?.charts ?? []} loading={loading} />
        </section>
      )}

      {/* Execution pipeline — timeline + trace from response.plan / response.trace */}
      {(loading || response) && (
        <section className="animate-fade-up space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Execution Pipeline</h3>
          <PipelinePanel
            plan={response?.plan ?? []}
            trace={response?.trace ?? []}
            skipped={response?.skipped ?? []}
            loading={loading}
          />
        </section>
      )}
    </div>
  );
}
