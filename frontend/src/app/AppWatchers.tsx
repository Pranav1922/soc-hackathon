import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import type { ActivityType, HistoryRecord } from "@/types/workflow";
import type { AnalyzeResponse } from "@/types/api";
import { useAnalysis } from "@/context/AnalysisContext";
import { useHistory } from "@/context/HistoryContext";
import { useActivity } from "@/context/ActivityContext";
import { useToast } from "@/context/ToastContext";
import { useHealth } from "@/hooks/useHealth";

function summarize(flagged: number, avgRisk: number, pattern: string | null): string {
  if (flagged === 0) return "No entities flagged.";
  const forPattern = pattern ? ` for ${pattern}` : "";
  return `${flagged} ${flagged === 1 ? "entity" : "entities"} flagged${forPattern}, avg risk ${avgRisk.toFixed(2)}.`;
}

/**
 * Observes the existing shared state (analysis / health / route) and records
 * client-side History + Activity. Renders nothing; touches no existing logic.
 */
export default function AppWatchers() {
  const { response } = useAnalysis();
  const { add } = useHistory();
  const { log } = useActivity();
  const { toast } = useToast();
  const location = useLocation();
  const health = useHealth();

  const lastResponse = useRef<AnalyzeResponse | null>(null);
  const connected = useRef(false);

  // Save a successful investigation to History (once per new response).
  useEffect(() => {
    if (!response || response === lastResponse.current) return;
    lastResponse.current = response;

    const results = response.results;
    const flagged = results.length;
    const avgRisk = flagged ? results.reduce((sum, r) => sum + r.score, 0) / flagged : 0;
    const rawPattern = response.understanding?.aml_pattern ?? null;
    const pattern = rawPattern && rawPattern !== "none" ? rawPattern : null;

    const record: HistoryRecord = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: Date.now(),
      query: response.query,
      intent: response.understanding?.intent ?? null,
      pattern,
      flagged,
      avgRisk,
      summary: summarize(flagged, avgRisk, pattern),
      response,
    };

    add(record);
    log("investigation_completed", `Investigation completed — “${response.query}” · ${flagged} flagged`);
    if (response.charts.length > 0) log("charts_generated", `${response.charts.length} charts generated`);
    toast("Investigation saved to history", "success");
  }, [response, add, log, toast]);

  // Route-based activity for the pages that warrant it.
  useEffect(() => {
    const map: Record<string, [ActivityType, string]> = {
      "/pipeline": ["pipeline_viewed", "Pipeline viewed"],
      "/architecture": ["architecture_viewed", "Architecture viewed"],
      "/history": ["history_opened", "History opened"],
    };
    const entry = map[location.pathname];
    if (entry) log(entry[0], entry[1]);
  }, [location.pathname, log]);

  // Backend connectivity (log once per session on first connect).
  useEffect(() => {
    if (health === "online" && !connected.current) {
      connected.current = true;
      log("backend_connected", "Backend connected");
    }
  }, [health, log]);

  return null;
}
