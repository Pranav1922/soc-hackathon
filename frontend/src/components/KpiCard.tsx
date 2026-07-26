import type { IconType } from "react-icons";
import { m } from "framer-motion";
import AnimatedNumber from "@/components/AnimatedNumber";

type Accent = "cyan" | "violet" | "amber" | "rose" | "emerald";

const ACCENT: Record<Accent, string> = {
  cyan: "text-accent",
  violet: "text-purple-300",
  amber: "text-risk-medium",
  rose: "text-risk-high",
  emerald: "text-risk-low",
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
}

/** Premium KPI tile with a count-up value and a hover glow. */
export default function KpiCard({
  label,
  value,
  decimals = 0,
  prefix,
  suffix,
  icon: Icon,
  accent = "cyan",
  hint,
}: KpiCardProps) {
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
      <p className="mt-3 text-3xl font-bold tracking-tight text-slate-100">
        {prefix}
        <AnimatedNumber value={value} decimals={decimals} />
        {suffix}
      </p>
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </m.div>
  );
}
