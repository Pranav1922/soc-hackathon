import { lazy, Suspense } from "react";
import { FiBarChart2 } from "react-icons/fi";
import type { ChartSpec } from "@/types/api";
import EmptyState from "@/components/EmptyState";

// Lazy so the Plotly bundle stays out of the initial load and only ships when
// charts are actually rendered. The skeleton doubles as the load fallback.
const ChartCard = lazy(() => import("@/components/ChartCard"));

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="glass overflow-hidden">
          <div className="border-b border-white/5 px-4 py-3">
            <div className="h-4 w-48 animate-pulse rounded bg-white/10" />
            <div className="mt-2 h-3 w-20 animate-pulse rounded bg-white/10" />
          </div>
          <div className="h-72 animate-pulse bg-white/[0.03]" />
        </div>
      ))}
    </div>
  );
}

/** Responsive grid of chart cards (1 col mobile, 2 cols tablet/desktop). */
export default function ChartsGrid({ charts, loading }: { charts: ChartSpec[]; loading: boolean }) {
  if (loading) return <SkeletonGrid />;

  if (charts.length === 0)
    return (
      <EmptyState
        icon={FiBarChart2}
        title="No visualizations were returned."
        description="This query did not produce any charts."
      />
    );

  return (
    <Suspense fallback={<SkeletonGrid />}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {charts.map((chart, i) => (
          <ChartCard key={i} chart={chart} />
        ))}
      </div>
    </Suspense>
  );
}
