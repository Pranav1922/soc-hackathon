import type { AMLPattern, AnalyzeResponse, IntentType } from "@/types/api";

/** A saved investigation (client-side only — never sent to the backend). */
export interface HistoryRecord {
  id: string;
  timestamp: number; // epoch ms
  query: string;
  intent: IntentType | null;
  pattern: AMLPattern | null;
  flagged: number;
  avgRisk: number;
  summary: string;
  /** Full response for local reconstruction; may be dropped under storage pressure. */
  response?: AnalyzeResponse;
}

export type ActivityType =
  | "app_started"
  | "backend_connected"
  | "investigation_started"
  | "investigation_completed"
  | "charts_generated"
  | "pipeline_viewed"
  | "architecture_viewed"
  | "history_opened"
  | "investigation_deleted"
  | "history_cleared"
  | "activity_cleared"
  | "investigation_restored"
  | "export";

export interface ActivityEvent {
  id: string;
  timestamp: number;
  type: ActivityType;
  message: string;
}
