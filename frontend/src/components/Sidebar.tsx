import { Link, NavLink } from "react-router-dom";
import { AnimatePresence, m } from "framer-motion";
import { FiChevronLeft, FiChevronRight, FiShield, FiX } from "react-icons/fi";
import { NAV_ITEMS } from "@/utils/nav";
import type { HealthStatus } from "@/hooks/useHealth";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  health: HealthStatus;
}

/** Brand mark; the wordmark fades out when collapsed. */
function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-3 px-4 py-5" aria-label="AEGIS home">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent to-accent-deep text-surface-950 shadow-glow">
        <FiShield className="h-5 w-5" />
      </div>
      <AnimatePresence initial={false}>
        {!collapsed && (
          <m.div
            key="wordmark"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden whitespace-nowrap leading-tight"
          >
            <div className="text-sm font-extrabold tracking-tight text-slate-100">AEGIS</div>
            <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">AML Intelligence</div>
          </m.div>
        )}
      </AnimatePresence>
    </Link>
  );
}

function NavItems({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <nav className="flex-1 space-y-1 px-3 py-2">
      {!collapsed && (
        <div className="px-3 pb-2 pt-3 text-[11px] font-semibold uppercase tracking-wider text-slate-600">Workspace</div>
      )}
      {NAV_ITEMS.map(({ label, to, icon: Icon, ready }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/dashboard"}
          onClick={onNavigate}
          className={({ isActive }) =>
            ["nav-link group relative", isActive ? "nav-link-active" : "", collapsed ? "justify-center" : ""].join(" ")
          }
        >
          <Icon className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && <span className="flex-1 truncate">{label}</span>}
          {!collapsed && !ready && (
            <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500">Soon</span>
          )}
          {/* Tooltip while collapsed */}
          {collapsed && (
            <span className="pointer-events-none absolute left-full z-50 ml-3 hidden whitespace-nowrap rounded-md border border-white/10 bg-surface-800 px-2 py-1 text-xs text-slate-100 shadow-soft group-hover:block">
              {label}
              {!ready && " · Soon"}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function Footer({ collapsed, health }: { collapsed: boolean; health: HealthStatus }) {
  const dot =
    health === "online" ? "bg-risk-low animate-pulse" : health === "offline" ? "bg-slate-500" : "bg-amber-400";
  const label =
    health === "online" ? "Backend Connected" : health === "offline" ? "Backend not connected" : "Checking…";
  return (
    <div className="border-t border-white/10 px-4 py-4 text-[11px] text-slate-500">
      <div className={`flex items-center gap-2 ${collapsed ? "justify-center" : ""}`}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
        {!collapsed && <span>{label}</span>}
      </div>
      {!collapsed && <div className="mt-1 text-slate-600">v0.1.0 · AEGIS</div>}
    </div>
  );
}

/**
 * Left navigation. Desktop (≥lg): collapsible rail (280px ↔ 80px, persisted).
 * Mobile: slide-in drawer. Extends the original sidebar — same brand/nav/footer.
 */
export default function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile, health }: SidebarProps) {
  return (
    <>
      {/* Desktop rail */}
      <m.aside
        initial={false}
        animate={{ width: collapsed ? 80 : 280 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-white/10 bg-surface-900/50 backdrop-blur-xl lg:flex"
      >
        <Brand collapsed={collapsed} />
        <NavItems collapsed={collapsed} />
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="mx-3 mb-2 flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 py-2 text-xs font-medium text-slate-400 transition hover:border-accent/40 hover:text-accent"
        >
          {collapsed ? (
            <FiChevronRight className="h-4 w-4" />
          ) : (
            <>
              <FiChevronLeft className="h-4 w-4" /> Collapse
            </>
          )}
        </button>
        <Footer collapsed={collapsed} health={health} />
      </m.aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="lg:hidden">
            <m.div
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
              onClick={onCloseMobile}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            />
            <m.aside
              className="fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-white/10 bg-surface-900/95 backdrop-blur-xl"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.25, ease: "easeInOut" }}
            >
              <div className="flex items-center justify-between pr-2">
                <Brand collapsed={false} />
                <button
                  type="button"
                  onClick={onCloseMobile}
                  aria-label="Close menu"
                  className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-400 transition hover:text-accent"
                >
                  <FiX className="h-4 w-4" />
                </button>
              </div>
              <NavItems collapsed={false} onNavigate={onCloseMobile} />
              <Footer collapsed={false} health={health} />
            </m.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
