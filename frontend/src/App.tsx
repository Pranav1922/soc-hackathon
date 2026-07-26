import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { domAnimation, LazyMotion, MotionConfig } from "framer-motion";
import { AnalysisProvider } from "@/context/AnalysisContext";
import { ToastProvider } from "@/context/ToastContext";
import { ActivityProvider } from "@/context/ActivityContext";
import { HistoryProvider } from "@/context/HistoryContext";
import { SearchProvider } from "@/context/SearchContext";
import AppWatchers from "@/app/AppWatchers";
import Background from "@/components/Background";
import Spinner from "@/components/Spinner";
import GlobalSearch from "@/components/GlobalSearch";
import InvestigationViewer from "@/components/InvestigationViewer";
import AppLayout from "@/layouts/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Analyze from "@/pages/Analyze";
import Pipeline from "@/pages/Pipeline";
import Architecture from "@/pages/Architecture";
import History from "@/pages/History";
import Activity from "@/pages/Activity";

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
 * Routes + app-wide providers. Landing (/) is the entry page; the investigation
 * app lives under AppLayout. Phase 3 adds Toast / Activity / History / Search
 * providers (all client-side, localStorage-backed) around the existing tree.
 */
export default function App() {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">
        <Background />
        <ToastProvider>
          <ActivityProvider>
            <HistoryProvider>
              <AnalysisProvider>
                <SearchProvider>
                  <AppWatchers />
                  <Suspense fallback={<RouteFallback />}>
                    <Routes>
                      <Route path="/" element={<Landing />} />
                      <Route element={<AppLayout />}>
                        <Route path="/dashboard" element={<Dashboard />} />
                        <Route path="/analyze" element={<Analyze />} />
                        <Route path="/pipeline" element={<Pipeline />} />
                        <Route path="/architecture" element={<Architecture />} />
                        <Route path="/history" element={<History />} />
                        <Route path="/activity" element={<Activity />} />
                      </Route>
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </Suspense>
                  <GlobalSearch />
                  <InvestigationViewer />
                </SearchProvider>
              </AnalysisProvider>
            </HistoryProvider>
          </ActivityProvider>
        </ToastProvider>
      </MotionConfig>
    </LazyMotion>
  );
}
