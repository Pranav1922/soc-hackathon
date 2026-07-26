import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface SearchApi {
  open: boolean;
  setOpen: (v: boolean) => void;
  query: string;
  setQuery: (v: string) => void;
}

const SearchContext = createContext<SearchApi | null>(null);

/** Owns global-search open state and the ⌘K / Ctrl+K shortcut. */
export function SearchProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo<SearchApi>(() => ({ open, setOpen, query, setQuery }), [open, query]);
  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch(): SearchApi {
  const ctx = useContext(SearchContext);
  if (!ctx) throw new Error("useSearch must be used within a <SearchProvider>");
  return ctx;
}
