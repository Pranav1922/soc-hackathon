import { lazy, Suspense } from "react";
import { useHistory } from "@/context/HistoryContext";

// Lazy — pulls the results/charts/pipeline display components only when opened.
const InvestigationModal = lazy(() => import("@/components/InvestigationModal"));

/** Renders the investigation modal for whatever record History currently views. */
export default function InvestigationViewer() {
  const { viewing, closeView } = useHistory();
  if (!viewing) return null;
  return (
    <Suspense fallback={null}>
      <InvestigationModal record={viewing} onClose={closeView} />
    </Suspense>
  );
}
