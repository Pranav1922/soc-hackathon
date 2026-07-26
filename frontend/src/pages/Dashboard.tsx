import { Link } from "react-router-dom";
import { m } from "framer-motion";
import {
  FiActivity,
  FiAlertTriangle,
  FiCalendar,
  FiCpu,
  FiDatabase,
  FiFlag,
  FiGitMerge,
  FiLayers,
  FiSearch,
  FiShare2,
  FiShield,
  FiTarget,
  FiUsers,
} from "react-icons/fi";
import { useAnalysis } from "@/context/AnalysisContext";
import { useHistory } from "@/context/HistoryContext";
import { useDashboardData } from "@/hooks/useDashboardData";
import KpiCard from "@/components/KpiCard";
import RiskDistributionCard from "@/components/dashboard/RiskDistributionCard";
import SystemHealthCard from "@/components/dashboard/SystemHealthCard";
import RecentInvestigationsCard from "@/components/dashboard/RecentInvestigationsCard";
import RecentAlertsCard from "@/components/dashboard/RecentAlertsCard";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };

/** Reads a rows metric off the last analysis trace (0 when nothing has run yet). */
function useKpis() {
  const { response } = useAnalysis();
  const trace = response?.trace ?? [];
  const results = response?.results ?? [];
  const rows = (tool: string, field: "rows_in" | "rows_out") => trace.find((t) => t.tool === tool)?.[field] ?? 0;

  const patterns = new Set<string>();
  for (const r of results) {
    const hits = (r.evidence as { rule_hits?: { pattern?: string }[] }).rule_hits ?? [];
    for (const h of hits) if (h.pattern) patterns.add(h.pattern);
  }
  const amlPattern = response?.understanding?.aml_pattern;
  if (patterns.size === 0 && amlPattern && amlPattern !== "none") patterns.add(amlPattern);

  const avgRisk = results.length ? results.reduce((s, r) => s + r.score, 0) / results.length : 0;

  return {
    transactions: rows("DataLoader", "rows_in"),
    customers: rows("FeatureEngineering", "rows_out"),
    flagged: results.length,
    rulesTriggered: patterns.size,
    avgRisk,
  };
}

export default function Dashboard() {
  const kpi = useKpis();
  const data = useDashboardData();
  const { view } = useHistory();

  return (
    <div className="space-y-8">
      {/* Hero */}
      <m.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="glass relative overflow-hidden p-6 sm:p-8"
      >
        <span className="chip border-accent/30 bg-accent/10 text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          SOC · AML Investigation Console
        </span>
        <h1 className="mt-4 bg-gradient-to-b from-white to-slate-400 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent sm:text-4xl">
          AI Financial Crime Intelligence
        </h1>
        <p className="mt-2 text-base text-slate-400 sm:text-lg">Enterprise-grade AML Investigation Platform</p>

        {/* Quick actions */}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/analyze" className="btn-accent">
            <FiSearch className="h-4 w-4" />
            New Investigation
          </Link>
          <Link to="/pipeline" className="btn-outline">
            <FiGitMerge className="h-4 w-4" />
            View Pipeline
          </Link>
          <Link to="/architecture" className="btn-outline">
            <FiShare2 className="h-4 w-4" />
            View Architecture
          </Link>
        </div>
      </m.section>

      {/* Platform overview — persistent metrics derived from History */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Platform Overview</h2>
        <m.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <KpiCard label="Total Investigations" value={data.total} icon={FiLayers} accent="cyan" hint="Saved locally" />
          <KpiCard
            label="Investigations Today"
            value={data.today}
            icon={FiCalendar}
            accent="violet"
            trend={data.yesterday > 0 ? data.todayTrend : undefined}
            trendLabel="vs yesterday"
          />
          <KpiCard
            label="SAR Candidates"
            value={data.sarCandidates}
            icon={FiFlag}
            accent="rose"
            hint="Entities recommended to report"
          />
          <KpiCard
            label="AI Confidence"
            value={data.avgConfidence !== null ? data.avgConfidence * 100 : 0}
            suffix="%"
            icon={FiCpu}
            accent="emerald"
            hint="Avg query-understanding confidence"
            unavailable={data.avgConfidence === null}
          />
        </m.div>
      </section>

      {/* Latest run — metrics from the current in-session investigation */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Latest Run</h2>
        <m.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
        >
          <KpiCard label="Transactions" value={kpi.transactions} icon={FiDatabase} accent="cyan" hint="Analyzed in the last run" />
          <KpiCard label="Customers" value={kpi.customers} icon={FiUsers} accent="violet" hint="Entities feature-engineered" />
          <KpiCard label="Flagged Entities" value={kpi.flagged} icon={FiAlertTriangle} accent="rose" hint="Matched by detection" />
          <KpiCard label="AML Rules Triggered" value={kpi.rulesTriggered} icon={FiTarget} accent="amber" hint="Distinct typologies" />
          <KpiCard label="Average Risk Score" value={kpi.avgRisk} decimals={2} icon={FiActivity} accent="emerald" hint="Across flagged entities" />
          <KpiCard label="AML Rules Active" value={4} icon={FiShield} accent="cyan" hint="Structuring · Smurfing · Rapid cash-out · Layering" />
        </m.div>
      </section>

      {/* Risk posture + system health */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up lg:col-span-2">
          <RiskDistributionCard bands={data.riskBands} totalFlagged={data.totalFlagged} />
        </div>
        <div className="animate-fade-up">
          <SystemHealthCard />
        </div>
      </section>

      {/* Recent investigations + alerts */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up lg:col-span-2">
          <RecentInvestigationsCard records={data.recent} onView={view} />
        </div>
        <div className="animate-fade-up">
          <RecentAlertsCard alerts={data.alerts} />
        </div>
      </section>
    </div>
  );
}
