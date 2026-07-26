import { FiBell, FiCommand, FiMenu, FiSearch } from "react-icons/fi";
import type { HealthStatus } from "@/hooks/useHealth";

interface HeaderProps {
  onOpenMobile: () => void;
  health: HealthStatus;
}

/** Top application bar: mobile menu, contextual title, search affordance, live status. */
export default function Header({ onOpenMobile, health }: HeaderProps) {
  const online = health === "online";
  const statusLabel = online ? "Online" : health === "offline" ? "Offline" : "Checking…";
  const statusClass = online
    ? "border-risk-low/30 bg-risk-low/10 text-risk-low"
    : health === "offline"
      ? "border-slate-500/20 bg-slate-500/10 text-slate-400"
      : "border-amber-400/30 bg-amber-400/10 text-amber-300";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-white/10 bg-surface-950/70 px-4 backdrop-blur-xl sm:gap-4 sm:px-6">
      <button
        type="button"
        onClick={onOpenMobile}
        aria-label="Open menu"
        className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/5 text-slate-400 transition hover:text-slate-100 lg:hidden"
      >
        <FiMenu className="h-4 w-4" />
      </button>

      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-slate-100 sm:text-base">Suspicious Activity Detection</h1>
        <p className="hidden text-xs text-slate-500 sm:block">AI-powered AML investigation console</p>
      </div>

      {/* Command search (visual only) */}
      <div className="ml-auto hidden max-w-md flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-500 transition-colors hover:border-white/20 md:flex">
        <FiSearch className="h-4 w-4" />
        <span className="flex-1">Search analyses…</span>
        <span className="chip gap-1 text-slate-500">
          <FiCommand className="h-3 w-3" /> K
        </span>
      </div>

      <button
        type="button"
        aria-label="Notifications"
        className="ml-auto grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/5 text-slate-400 transition hover:text-slate-100 md:ml-0"
      >
        <FiBell className="h-4 w-4" />
      </button>

      <div className={`chip ${statusClass}`}>
        <span className={`h-1.5 w-1.5 rounded-full bg-current ${online ? "animate-pulse" : ""}`} />
        {statusLabel}
      </div>
    </header>
  );
}
