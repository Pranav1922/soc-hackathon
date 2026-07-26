import { FiAlertCircle } from "react-icons/fi";
import type { AnalyzeError } from "@/services/api";

/** Human-readable heading per failure kind (message text comes from the error). */
const TITLES: Record<AnalyzeError["kind"], string> = {
  canceled: "Request canceled",
  timeout: "Request timed out",
  network: "Connection problem",
  validation: "Invalid query",
  server: "Server error",
  unknown: "Something went wrong",
};

/** Presentational error panel driven by an {@link AnalyzeError} from useAnalyze. */
export default function ErrorBanner({ error, onRetry }: { error: AnalyzeError; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="glass flex items-start gap-3 border-risk-high/30 bg-risk-high/[0.06] p-4 animate-fade-up"
    >
      <FiAlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-risk-high" />
      <div className="flex-1 space-y-0.5">
        <p className="text-sm font-semibold text-slate-100">{TITLES[error.kind]}</p>
        <p className="text-sm text-slate-400">{error.message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="chip shrink-0 hover:border-accent/40 hover:text-accent"
        >
          Retry
        </button>
      )}
    </div>
  );
}
