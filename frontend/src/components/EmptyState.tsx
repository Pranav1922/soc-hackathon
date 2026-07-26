import type { IconType } from "react-icons";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: IconType;
  title: string;
  description: string;
  action?: ReactNode;
}

/** Reusable empty/placeholder panel with a centered icon, copy, and optional CTA. */
export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="glass flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/5 text-accent">
        <Icon className="h-6 w-6" />
      </div>
      <div className="max-w-md space-y-1.5">
        <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
        <p className="text-sm leading-relaxed text-slate-400">{description}</p>
      </div>
      {action}
    </div>
  );
}
