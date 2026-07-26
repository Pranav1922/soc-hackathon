/**
 * TypeScript mirror of the frozen FastAPI contract (POST /analyze).
 * Field names/types are taken 1:1 from the backend OpenAPI schema — do not invent
 * or rename fields. `inputs`/`evidence`/`spec` are free-form objects on the backend.
 */

// ── enums (string values exactly as the backend emits) ───────────────────────
export type IntentType = "eda" | "detect_pattern" | "threshold_rule" | "single_entity" | "compare";
export type AMLPattern = "structuring" | "smurfing" | "layering" | "rapid_cash_out" | "none";
export type RiskLevel = "low" | "medium" | "high";
export type EscalationAction = "monitor" | "review" | "report";
export type ExecutionStatus = "SUCCESS" | "SKIPPED" | "ERROR";
export type ToolName =
  | "DataLoader"
  | "Filter"
  | "EDA"
  | "FeatureEngineering"
  | "AMLPatternDetector"
  | "AnomalyDetector"
  | "RiskClassifier"
  | "Explainer"
  | "Recommender"
  | "Visualizer"
  | "ResponseFormatter";

// ── request ──────────────────────────────────────────────────────────────────
export interface AnalyzeRequest {
  query: string;
  example_id?: string | null;
}

// ── understanding ────────────────────────────────────────────────────────────
export interface DateRange {
  last_days: number | null;
  start: string | null; // ISO date
  end: string | null; // ISO date
}

export interface Filters {
  date_range: DateRange | null;
  country: string | null;
  segment: string | null;
  transaction_type: string | null;
  min_amount: number | null;
  max_amount: number | null;
}

export interface Understanding {
  intent: IntentType;
  entities: string[];
  filters: Filters;
  aml_pattern: AMLPattern;
  needs_eda: boolean;
  confidence: number;
}

// ── plan / trace / results / charts ──────────────────────────────────────────
export interface ExecutionStep {
  tool: ToolName;
  reason: string;
  confidence: number;
  inputs: Record<string, unknown>;
}

export interface RiskResult {
  entity_id: string;
  entity_type: string;
  risk: RiskLevel;
  score: number;
  explanation: string;
  action: EscalationAction;
  evidence: Record<string, unknown>;
}

/** `spec` is a native Plotly figure ({ data, layout }) — rendered as-is in Phase 7. */
export interface ChartSpec {
  type: string;
  title: string;
  spec: Record<string, unknown>;
}

export interface TraceEntry {
  tool: ToolName;
  status: ExecutionStatus;
  rows_in: number;
  rows_out: number;
  duration_ms: number;
}

// ── response (all fields are always present in the serialized payload) ────────
export interface AnalyzeResponse {
  query: string;
  understanding: Understanding | null;
  plan: ExecutionStep[];
  skipped: ToolName[];
  results: RiskResult[];
  charts: ChartSpec[];
  trace: TraceEntry[];
}
