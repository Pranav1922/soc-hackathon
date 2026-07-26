import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { domAnimation, LazyMotion } from "framer-motion";
import { AnalysisProvider } from "@/context/AnalysisContext";
import Background from "@/components/Background";
import Spinner from "@/components/Spinner";
import AppLayout from "@/layouts/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Analyze from "@/pages/Analyze";
import Pipeline from "@/pages/Pipeline";
import Placeholder from "@/pages/Placeholder";

// Landing is the entry page but not needed once inside the app — load it lazily.
const Landing = lazy(() => import("@/pages/Landing"));

function RouteFallback() {
  return (
    <div className="grid min-h-screen place-items-center">
      <Spinner className="h-6 w-6 text-accent" />
    </div>
  );
}

/**
 * Routes. Landing (/) is the entry page; the investigation app lives under
 * AppLayout at /dashboard, /analyze, /pipeline. LazyMotion loads only the DOM
 * animation feature set to keep the framer-motion footprint small.
 */
export default function App() {
  return (
    <LazyMotion features={domAnimation} strict>
      <Background />
      <AnalysisProvider>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/analyze" element={<Analyze />} />
              <Route path="/pipeline" element={<Pipeline />} />
              <Route path="/history" element={<Placeholder title="History" phase="a later phase" />} />
              <Route path="/activity" element={<Placeholder title="Activity" phase="a later phase" />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AnalysisProvider>
    </LazyMotion>
  );
}
