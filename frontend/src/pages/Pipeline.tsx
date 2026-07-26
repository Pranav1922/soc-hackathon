import { Link } from "react-router-dom";
import { FiGitMerge, FiSearch } from "react-icons/fi";
import { useAnalysis } from "@/context/AnalysisContext";
import PipelinePanel from "@/components/PipelinePanel";
import EmptyState from "@/components/EmptyState";

/**
 * Dedicated Pipeline route. Shows the execution timeline + trace from the most
 * recent analysis (shared via AnalysisContext) — the same PipelinePanel rendered
 * on the Analyze page. No new data-fetching or logic lives here.
 */
export default function Pipeline() {
  const { response, loading } = useAnalysis();

  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <h2 className="text-xl font-bold tracking-tight text-slate-100">Pipeline</h2>
        <p className="text-sm text-slate-400">
          Execution timeline and trace from your most recent analysis.
        </p>
      </div>

      {!loading && !response ? (
        <EmptyState
          icon={FiGitMerge}
          title="No pipeline yet"
          description="Run an analysis to view the execution pipeline."
          action={
            <Link to="/analyze" className="btn-accent">
              <FiSearch className="h-4 w-4" />
              Go to Analyze
            </Link>
          }
        />
      ) : (
        <section className="animate-fade-up">
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
