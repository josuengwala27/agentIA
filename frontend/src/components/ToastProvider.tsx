"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type ToastType = "success" | "error" | "info" | "warning";

type Toast = {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  createdAt: number;
  ttlMs: number;
};

type ToastContextValue = {
  addToast: (t: Omit<Toast, "id" | "createdAt">) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

function toastTypeStyles(type: ToastType) {
  switch (type) {
    case "success":
      return {
        border: "border-emerald-600/40",
        bg: "bg-emerald-50/80",
        text: "text-emerald-950",
      };
    case "error":
      return {
        border: "border-rose-600/40",
        bg: "bg-rose-50/80",
        text: "text-rose-950",
      };
    case "warning":
      return {
        border: "border-amber-600/40",
        bg: "bg-amber-50/80",
        text: "text-amber-950",
      };
    case "info":
    default:
      return {
        border: "border-sky-600/40",
        bg: "bg-sky-50/80",
        text: "text-sky-950",
      };
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((t: Omit<Toast, "id" | "createdAt">) => {
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    const next: Toast = {
      ...t,
      id,
      createdAt: Date.now(),
    };
    setToasts((prev) => [next, ...prev].slice(0, 5));
  }, []);

  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) =>
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== t.id));
      }, t.ttlMs)
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [toasts]);

  const value = useMemo<ToastContextValue>(() => ({ addToast }), [addToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed top-4 right-4 z-[100] w-[92vw] max-w-sm space-y-2">
        {toasts.map((t) => {
          const styles = toastTypeStyles(t.type);
          return (
            <div
              key={t.id}
              className={[
                "rounded-xl border px-4 py-3 shadow-lg backdrop-blur",
                styles.border,
                styles.bg,
              ].join(" ")}
            >
              <div className={`text-sm font-semibold ${styles.text}`}>
                {t.title || (t.type === "error" ? "Erreur" : t.type === "success" ? "OK" : "Info")}
              </div>
              <div className={`text-sm mt-1 ${styles.text}`}>{t.message}</div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast doit être utilisé dans ToastProvider");
  return ctx;
}

