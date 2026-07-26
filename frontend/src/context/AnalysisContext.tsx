import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import { useAnalyze, type UseAnalyze } from "@/hooks/useAnalyze";

/**
 * Holds a single shared analysis session so every route (Analyze, Pipeline, …)
 * reads the same last response — no duplicated fetch/state logic. The value is
 * exactly the existing useAnalyze() hook, lifted above the routes.
 */
const AnalysisContext = createContext<UseAnalyze | null>(null);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const analysis = useAnalyze();
  return <AnalysisContext.Provider value={analysis}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): UseAnalyze {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within an <AnalysisProvider>");
  return ctx;
}
