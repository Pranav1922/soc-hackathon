import { FiTool } from "react-icons/fi";
import EmptyState from "@/components/EmptyState";

/** Generic "coming in a later phase" page for not-yet-built routes. */
export default function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <h2 className="text-xl font-bold tracking-tight text-slate-100">{title}</h2>
        <p className="text-sm text-slate-400">Planned for {phase}.</p>
      </div>
      <EmptyState
        icon={FiTool}
        title={`${title} — coming soon`}
        description={`This screen is scaffolded and will be implemented in ${phase}.`}
      />
    </div>
  );
}
