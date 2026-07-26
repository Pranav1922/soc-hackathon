import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { m } from "framer-motion";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import { useHealth } from "@/hooks/useHealth";

const COLLAPSE_KEY = "aegis-sidebar-collapsed";

/**
 * App shell: collapsible sidebar + sticky header + scrollable routed content.
 * Sidebar collapse persists to localStorage; each route fades/slides in.
 */
export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const health = useHealth();
  const location = useLocation();

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, String(collapsed));
  }, [collapsed]);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        health={health}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onOpenMobile={() => setMobileOpen(true)} health={health} />
        <main className="flex-1 overflow-x-hidden px-4 py-6 sm:px-6 lg:px-8">
          <m.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="mx-auto w-full max-w-7xl"
          >
            <Outlet />
          </m.div>
        </main>
      </div>
    </div>
  );
}
