import { FiAlertTriangle, FiPlay, FiSearch, FiShield, FiUsers } from "react-icons/fi";
import StatCard from "@/components/StatCard";
import EmptyState from "@/components/EmptyState";

/**
 * Empty dashboard (Phase 1). Placeholder KPI tiles + an empty "run an analysis"
 * panel. No data is fetched yet — the analyze flow lands in Phase 3.
 */
export default function Dashboard() {
  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div className="flex flex-col gap-2 animate-fade-up sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100">Overview</h2>
          <p className="text-sm text-slate-400">
            Run a natural-language query to detect suspicious activity across the transaction dataset.
          </p>
        </div>
        <button type="button" disabled className="btn-accent">
          <FiPlay className="h-4 w-4" />
          New Analysis
        </button>
      </div>

      {/* KPI row (placeholder values until Phase 4/5) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Analyses Run" value="—" icon={FiSearch} hint="This session" />
        <StatCard label="Flagged Entities" value="—" icon={FiUsers} accent="amber" />
        <StatCard label="High Risk" value="—" icon={FiAlertTriangle} accent="rose" />
        <StatCard label="Rules Active" value="4" icon={FiShield} accent="emerald" hint="Structuring · Smurfing · Rapid cash-out · Layering" />
      </div>

      {/* Empty state */}
      <EmptyState
        icon={FiSearch}
        title="No analysis yet"
        description="Ask a question like “Find suspicious structuring” or “Analyze customer C12345”. Results, explanations, and charts will appear here."
        action={
          <button type="button" disabled className="btn-accent">
            <FiPlay className="h-4 w-4" />
            Start your first analysis
          </button>
        }
      />
    </div>
  );
}
