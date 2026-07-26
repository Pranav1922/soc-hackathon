import axios, { AxiosError } from "axios";
import type { AnalyzeRequest, AnalyzeResponse } from "@/types/api";

/**
 * Single reusable Axios layer for the frozen backend. Only POST /analyze is used.
 * Dev: baseURL "/api" → Vite proxy strips /api → http://localhost:8000.
 * Prod: set VITE_API_BASE_URL to the backend origin.
 */
const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  timeout: 60_000, // broad EDA/detection queries can take a few seconds; leave headroom
  headers: { "Content-Type": "application/json" },
});

/** Lightweight liveness probe against the existing GET /health endpoint. */
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await http.get("/health", { timeout: 4000, signal });
    return res.status === 200;
  } catch {
    return false;
  }
}

/** Discriminated failure kinds so the UI can react without re-parsing Axios internals. */
export type AnalyzeErrorKind = "canceled" | "timeout" | "network" | "validation" | "server" | "unknown";

export interface AnalyzeError {
  kind: AnalyzeErrorKind;
  message: string;
  status?: number;
  /** Raw backend body for validation (422) / server (500) errors, if any. */
  detail?: unknown;
}

/** FastAPI 422 body: { detail: [{ loc, msg, type }, ...] }. */
function firstValidationMessage(data: unknown): string | undefined {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
    if (typeof detail === "string") return detail;
  }
  return undefined;
}

function toAnalyzeError(err: unknown): AnalyzeError {
  if (axios.isCancel(err)) {
    return { kind: "canceled", message: "Request canceled." };
  }
  if (err instanceof AxiosError) {
    if (err.code === "ECONNABORTED") {
      return { kind: "timeout", message: "The analysis timed out. Try a narrower query." };
    }
    if (!err.response) {
      return { kind: "network", message: "Cannot reach the analysis service." };
    }
    const { status, data } = err.response;
    if (status === 422) {
      return {
        kind: "validation",
        status,
        message: firstValidationMessage(data) ?? "The query was rejected by the server.",
        detail: data,
      };
    }
    return {
      kind: "server",
      status,
      message: `Analysis failed (HTTP ${status}).`,
      detail: data,
    };
  }
  return { kind: "unknown", message: "An unexpected error occurred." };
}

/** True for the shape produced by {@link analyze} on failure. */
export function isAnalyzeError(e: unknown): e is AnalyzeError {
  return !!e && typeof e === "object" && "kind" in e && "message" in e;
}

/**
 * Run one analysis. Pass an AbortSignal to cancel in-flight requests.
 * Rejects with an {@link AnalyzeError} (never a raw Axios error).
 */
export async function analyze(query: string, signal?: AbortSignal): Promise<AnalyzeResponse> {
  const body: AnalyzeRequest = { query };
  try {
    const { data } = await http.post<AnalyzeResponse>("/analyze", body, { signal });
    return data;
  } catch (err) {
    throw toAnalyzeError(err);
  }
}
