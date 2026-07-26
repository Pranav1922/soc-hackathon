import type { IconType } from "react-icons";
import { m } from "framer-motion";
import { FiMinus, FiTrendingDown, FiTrendingUp } from "react-icons/fi";
import AnimatedNumber from "@/components/AnimatedNumber";

type Accent = "cyan" | "violet" | "amber" | "rose" | "emerald";
type Trend = "up" | "down" | "none";

const ACCENT: Record<Accent, string> = {
  cyan: "text-accent",
  violet: "text-purple-300",
  amber: "text-risk-medium",
  rose: "text-risk-high",
  emerald: "text-risk-low",
};

const TREND: Record<Trend, { cls: string; Icon: IconType }> = {
  up: { cls: "text-risk-low border-risk-low/30 bg-risk-low/10", Icon: FiTrendingUp },
  down: { cls: "text-risk-high border-risk-high/30 bg-risk-high/10", Icon: FiTrendingDown },
  none: { cls: "text-slate-400 border-white/10 bg-white/5", Icon: FiMinus },
};

interface KpiCardProps {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  icon: IconType;
  accent?: Accent;
  hint?: string;
  /** Show a period-over-period trend chip (only pass when honestly computed). */
  trend?: Trend;
  trendLabel?: string;
  /** Render "Unavailable" instead of a number when the metric can't be computed. */
  unavailable?: boolean;
}

/** Premium KPI tile with a count-up value, optional trend chip, and a hover glow. */
export default function KpiCard({
  label,
  value,
  decimals = 0,
  prefix,
  suffix,
  icon: Icon,
  accent = "cyan",
  hint,
  trend,
  trendLabel,
  unavailable = false,
}: KpiCardProps) {
  const T = trend ? TREND[trend] : null;
  return (
    <m.div
      variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }}
      whileHover={{ y: -4 }}
      className="glass p-5 transition-shadow duration-300 hover:border-accent/30 hover:shadow-glow-lg"
    >
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
        <div className={`grid h-9 w-9 place-items-center rounded-lg bg-white/5 ${ACCENT[accent]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      {unavailable ? (
        <p className="mt-3 text-lg font-semibold text-slate-500">Unavailable</p>
      ) : (
        <div className="mt-3 flex items-center gap-2">
          <p className="text-3xl font-bold tracking-tight text-slate-100">
            {prefix}
            <AnimatedNumber value={value} decimals={decimals} />
            {suffix}
          </p>
          {T && (
            <span className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${T.cls}`}>
              <T.Icon className="h-3 w-3" />
              {trendLabel}
            </span>
          )}
        </div>
      )}
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </m.div>
  );
}
