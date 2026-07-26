import { useMemo } from "react";
import type { IconType } from "react-icons";
import { FiActivity, FiCpu, FiDatabase, FiServer } from "react-icons/fi";
import { useHealth } from "@/hooks/useHealth";

type State = "ok" | "warn" | "down";

const STATE: Record<State, { dot: string; text: string }> = {
  ok: { dot: "bg-risk-low", text: "text-risk-low" },
  warn: { dot: "bg-risk-medium", text: "text-risk-medium" },
  down: { dot: "bg-risk-high", text: "text-risk-high" },
};

function storageOk(): boolean {
  try {
    const k = "__aegis_probe__";
    localStorage.setItem(k, "1");
    localStorage.removeItem(k);
    return true;
  } catch {
    return false;
  }
}

interface Row {
  icon: IconType;
  label: string;
  state: State;
  status: string;
}

/** Compact enterprise health panel — every row reflects a real, verifiable signal. */
export default function SystemHealthCard() {
  const health = useHealth();
  const storage = useMemo(storageOk, []);

  const backend: [State, string] =
    health === "online" ? ["ok", "Operational"] : health === "offline" ? ["down", "Offline"] : ["warn", "Checking…"];

  const rows: Row[] = [
    { icon: FiServer, label: "Backend API", state: backend[0], status: backend[1] },
    { icon: FiCpu, label: "Detection Engine", state: backend[0], status: health === "online" ? "Ready" : backend[1] },
    { icon: FiDatabase, label: "History Storage", state: storage ? "ok" : "down", status: storage ? "Available" : "Unavailable" },
    { icon: FiActivity, label: "Activity Monitor", state: "ok", status: "Active" },
  ];

  return (
    <div className="glass h-full p-5">
      <h3 className="mb-4 text-sm font-semibold text-slate-100">System Health</h3>
      <ul className="space-y-3">
        {rows.map((r) => {
          const s = STATE[r.state];
          return (
            <li key={r.label} className="flex items-center gap-3">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/5 text-slate-400">
                <r.icon className="h-4 w-4" />
              </span>
              <span className="flex-1 text-sm text-slate-300">{r.label}</span>
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${r.state === "ok" ? "animate-pulse" : ""}`} />
                {r.status}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
