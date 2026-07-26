import { useEffect, useState } from "react";
import { checkHealth } from "@/services/api";

export type HealthStatus = "checking" | "online" | "offline";

/** Pings GET /health on mount and on an interval; reports backend reachability. */
export function useHealth(intervalMs = 30_000): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const ping = async () => {
      const ok = await checkHealth(controller.signal);
      if (alive) setStatus(ok ? "online" : "offline");
    };
    void ping();
    const timer = setInterval(() => void ping(), intervalMs);
    return () => {
      alive = false;
      clearInterval(timer);
      controller.abort();
    };
  }, [intervalMs]);

  return status;
}
