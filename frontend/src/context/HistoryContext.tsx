import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { HistoryRecord } from "@/types/workflow";
import { loadJSON, saveJSON } from "@/lib/storage";

const KEY = "aegis-history";
const MAX = 25; // cap entries
const FULL = 8; // keep the full response for the newest N (older keep metadata only)

interface HistoryApi {
  items: HistoryRecord[];
  add: (record: HistoryRecord) => void;
  remove: (id: string) => void;
  clear: () => void;
  viewing: HistoryRecord | null;
  view: (record: HistoryRecord) => void;
  closeView: () => void;
}

const HistoryContext = createContext<HistoryApi | null>(null);

/** Persist with graceful degradation: if storage is full, drop older full responses. */
function persist(records: HistoryRecord[]): HistoryRecord[] {
  if (saveJSON(KEY, records)) return records;
  const trimmed = records.map((r, i) => (i < FULL ? r : { ...r, response: undefined }));
  if (saveJSON(KEY, trimmed)) return trimmed;
  const metaOnly = records.map((r) => ({ ...r, response: undefined }));
  saveJSON(KEY, metaOnly);
  return metaOnly;
}

export function HistoryProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<HistoryRecord[]>(() => loadJSON<HistoryRecord[]>(KEY, []));
  const [viewing, setViewing] = useState<HistoryRecord | null>(null);

  const add = useCallback((record: HistoryRecord) => {
    setItems((prev) => persist([record, ...prev].slice(0, MAX)));
  }, []);

  const remove = useCallback((id: string) => {
    setItems((prev) => persist(prev.filter((r) => r.id !== id)));
  }, []);

  const clear = useCallback(() => {
    setItems(persist([]));
  }, []);

  const view = useCallback((record: HistoryRecord) => setViewing(record), []);
  const closeView = useCallback(() => setViewing(null), []);

  const value = useMemo<HistoryApi>(
    () => ({ items, add, remove, clear, viewing, view, closeView }),
    [items, add, remove, clear, viewing, view, closeView],
  );

  return <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>;
}

export function useHistory(): HistoryApi {
  const ctx = useContext(HistoryContext);
  if (!ctx) throw new Error("useHistory must be used within a <HistoryProvider>");
  return ctx;
}
