import { Link } from "react-router-dom";
import { m } from "framer-motion";
import {
  FiActivity,
  FiAlertTriangle,
  FiArrowRight,
  FiDatabase,
  FiGitMerge,
  FiSearch,
  FiShare2,
  FiShield,
  FiTarget,
  FiUsers,
} from "react-icons/fi";
import { useAnalysis } from "@/context/AnalysisContext";
import KpiCard from "@/components/KpiCard";
import EmptyState from "@/components/EmptyState";

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
    hasData: response !== null,
  };
}

export default function Dashboard() {
  const { response } = useAnalysis();
  const kpi = useKpis();

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

      {/* KPIs */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Key Metrics</h2>
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

      {/* Latest analysis summary / empty state */}
      {response && response.understanding ? (
        <section className="glass animate-fade-up p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Latest investigation</p>
              <p className="mt-1 truncate text-lg font-semibold text-slate-100">“{response.query}”</p>
              <p className="mt-1 text-sm text-slate-400">
                Intent <span className="text-slate-300">{response.understanding.intent}</span> · Pattern{" "}
                <span className="text-slate-300">{response.understanding.aml_pattern}</span> · {kpi.flagged} flagged
              </p>
            </div>
            <Link to="/analyze" className="btn-outline shrink-0">
              View results
              <FiArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      ) : (
        <EmptyState
          icon={FiSearch}
          title="No analysis yet"
          description="Ask a question like “Find suspicious structuring” or “Analyze customer C12345”. Results, explanations, and charts will appear here."
          action={
            <Link to="/analyze" className="btn-accent">
              <FiSearch className="h-4 w-4" />
              Start your first analysis
            </Link>
          }
        />
      )}
    </div>
  );
}
