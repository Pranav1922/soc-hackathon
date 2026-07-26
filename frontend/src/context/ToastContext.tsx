import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, m } from "framer-motion";
import { FiAlertCircle, FiCheckCircle, FiInfo, FiX } from "react-icons/fi";

type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastApi {
  toast: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const STYLE: Record<ToastKind, { icon: typeof FiInfo; cls: string }> = {
  success: { icon: FiCheckCircle, cls: "text-risk-low" },
  error: { icon: FiAlertCircle, cls: "text-risk-high" },
  info: { icon: FiInfo, cls: "text-accent" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const remove = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const toast = useCallback(
    (message: string, kind: ToastKind = "success") => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, message, kind }]);
      window.setTimeout(() => remove(id), 3800);
    },
    [remove],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2" role="region" aria-label="Notifications">
          <AnimatePresence initial={false}>
            {toasts.map((t) => {
              const S = STYLE[t.kind];
              const Icon = S.icon;
              return (
                <m.div
                  key={t.id}
                  layout
                  initial={{ opacity: 0, y: 16, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 24 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  role="status"
                  className="glass pointer-events-auto flex items-start gap-3 border-white/10 bg-surface-900/90 p-3.5 shadow-soft"
                >
                  <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${S.cls}`} />
                  <p className="flex-1 text-sm text-slate-200">{t.message}</p>
                  <button
                    type="button"
                    onClick={() => remove(t.id)}
                    aria-label="Dismiss notification"
                    className="text-slate-500 transition hover:text-slate-200"
                  >
                    <FiX className="h-4 w-4" />
                  </button>
                </m.div>
              );
            })}
          </AnimatePresence>
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a <ToastProvider>");
  return ctx;
}
