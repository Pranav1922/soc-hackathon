import { useCallback, useEffect, useRef, useState } from "react";
import { analyze as analyzeRequest, isAnalyzeError, type AnalyzeError } from "@/services/api";
import type { AnalyzeResponse } from "@/types/api";

export interface UseAnalyze {
  analyze: (query: string) => Promise<void>;
  loading: boolean;
  error: AnalyzeError | null;
  response: AnalyzeResponse | null;
  reset: () => void;
}

/**
 * React entry point for POST /analyze. Owns loading/error/response state and
 * cancels any in-flight request when a new one starts or the component unmounts.
 */
export function useAnalyze(): UseAnalyze {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<AnalyzeError | null>(null);
  const [response, setResponse] = useState<AnalyzeResponse | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const analyze = useCallback(async (query: string) => {
    controllerRef.current?.abort(); // supersede any in-flight request
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const data = await analyzeRequest(query, controller.signal);
      if (!controller.signal.aborted) setResponse(data);
    } catch (err) {
      // A cancel is an intentional supersede — don't surface it as an error.
      if (isAnalyzeError(err) && err.kind === "canceled") return;
      setError(isAnalyzeError(err) ? err : { kind: "unknown", message: "An unexpected error occurred." });
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setLoading(false);
    setError(null);
    setResponse(null);
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []); // abort on unmount

  return { analyze, loading, error, response, reset };
}
