import type { IconType } from "react-icons";
import type { ReactNode } from "react";

type Accent = "cyan" | "amber" | "emerald" | "slate";

const ACCENT: Record<Accent, string> = {
  cyan: "text-accent",
  amber: "text-risk-medium",
  emerald: "text-risk-low",
  slate: "text-slate-400",
};

interface InfoCardProps {
  label: string;
  value: ReactNode;
  icon?: IconType;
  accent?: Accent;
  className?: string;
}

/** Labelled value card used to surface single facts (intent, pattern, confidence…). */
export default function InfoCard({ label, value, icon: Icon, accent = "cyan", className = "" }: InfoCardProps) {
  return (
    <div className={`glass glass-hover animate-fade-up p-4 ${className}`}>
      <div className="flex items-center gap-2">
        {Icon && (
          <span className={`grid h-7 w-7 place-items-center rounded-lg bg-white/5 ${ACCENT[accent]}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      </div>
      <p className="mt-3 break-words text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}
