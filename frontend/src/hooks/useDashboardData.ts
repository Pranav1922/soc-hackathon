import { useMemo } from "react";
import type { HistoryRecord } from "@/types/workflow";
import { useHistory } from "@/context/HistoryContext";

export interface DashboardData {
  total: number;
  today: number;
  yesterday: number;
  todayTrend: "up" | "down" | "none";
  riskBands: { high: number; medium: number; low: number };
  totalFlagged: number;
  sarCandidates: number;
  avgConfidence: number | null; // 0–1, mean query-understanding confidence
  avgDurationMs: number | null; // mean total pipeline execution time
  recent: HistoryRecord[]; // latest 5
  alerts: { id: string; pattern: string; timestamp: number }[]; // latest 5 with a detected pattern
  detailedCount: number; // records that still carry a full response
}

function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/**
 * Derives executive dashboard metrics purely from saved History — nothing is
 * fabricated. Risk/SAR/confidence/duration are computed only from records that
 * still carry a full response; counts come from all records.
 */
export function useDashboardData(): DashboardData {
  const { items } = useHistory();

  return useMemo(() => {
    const todayStart = startOfDay(Date.now());
    const yesterdayStart = todayStart - 86_400_000;

    const today = items.filter((r) => r.timestamp >= todayStart).length;
    const yesterday = items.filter((r) => r.timestamp >= yesterdayStart && r.timestamp < todayStart).length;
    const todayTrend = today > yesterday ? "up" : today < yesterday ? "down" : "none";

    const bands = { high: 0, medium: 0, low: 0 };
    let totalFlagged = 0;
    let sar = 0;
    let confSum = 0;
    let confN = 0;
    let durSum = 0;
    let durN = 0;
    let detailed = 0;

    for (const r of items) {
      if (!r.response) continue;
      detailed++;
      for (const res of r.response.results) {
        totalFlagged++;
        bands[res.risk]++;
        if (res.action === "report") sar++;
      }
      const c = r.response.understanding?.confidence;
      if (typeof c === "number") {
        confSum += c;
        confN++;
      }
      durSum += r.response.trace.reduce((s, t) => s + t.duration_ms, 0);
      durN++;
    }

    const alerts = items
      .filter((r): r is HistoryRecord & { pattern: string } => !!r.pattern)
      .slice(0, 5)
      .map((r) => ({ id: r.id, pattern: r.pattern, timestamp: r.timestamp }));

    return {
      total: items.length,
      today,
      yesterday,
      todayTrend,
      riskBands: bands,
      totalFlagged,
      sarCandidates: sar,
      avgConfidence: confN ? confSum / confN : null,
      avgDurationMs: durN ? durSum / durN : null,
      recent: items.slice(0, 5),
      alerts,
      detailedCount: detailed,
    };
  }, [items]);
}
