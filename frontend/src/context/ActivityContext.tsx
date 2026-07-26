import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ActivityEvent, ActivityType } from "@/types/workflow";
import { loadJSON, saveJSON } from "@/lib/storage";

const KEY = "aegis-activity";
const MAX = 200;

interface ActivityApi {
  items: ActivityEvent[];
  log: (type: ActivityType, message: string) => void;
  clear: () => void;
}

const ActivityContext = createContext<ActivityApi | null>(null);

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ActivityEvent[]>(() => loadJSON<ActivityEvent[]>(KEY, []));
  const startedRef = useRef(false);

  const log = useCallback((type: ActivityType, message: string) => {
    setItems((prev) => {
      const next = [
        { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, timestamp: Date.now(), type, message },
        ...prev,
      ].slice(0, MAX);
      saveJSON(KEY, next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setItems([]);
    saveJSON(KEY, []);
  }, []);

  // Log app start once per page load (ref guards StrictMode double-invoke).
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    log("app_started", "Application started");
  }, [log]);

  const value = useMemo<ActivityApi>(() => ({ items, log, clear }), [items, log, clear]);
  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}

export function useActivity(): ActivityApi {
  const ctx = useContext(ActivityContext);
  if (!ctx) throw new Error("useActivity must be used within an <ActivityProvider>");
  return ctx;
}
