"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

type ConfirmOptions = {
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
};

type ConfirmContextValue = {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
};

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolverRef = useRef<(v: boolean) => void>();

  const close = useCallback(() => {
    setOpen(false);
    setOpts(null);
  }, []);

  const confirm = useCallback((nextOpts: ConfirmOptions) => {
    setOpts(nextOpts);
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const value = useMemo<ConfirmContextValue>(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}

      {open && opts && (
        <div className="fixed inset-0 z-[120] grid place-items-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => {
              resolverRef.current?.(false);
              close();
            }}
          />
          <div className="relative z-[121] w-[92vw] max-w-lg rounded-2xl border bg-[var(--panel)]/95 backdrop-blur p-5 shadow-xl">
            <div className="text-lg font-display font-semibold">{opts.title}</div>
            {opts.description && <div className="text-sm text-[var(--muted)] mt-2">{opts.description}</div>}
            <div className="mt-5 flex gap-3 justify-end">
              <button
                type="button"
                className="px-4 py-2 rounded-lg border border-[var(--line)] bg-transparent text-[var(--ink)] hover:bg-[var(--accent-soft)]/60"
                onClick={() => {
                  resolverRef.current?.(false);
                  close();
                }}
              >
                {opts.cancelText || "Annuler"}
              </button>
              <button
                type="button"
                className={[
                  "px-4 py-2 rounded-lg text-white",
                  opts.danger ? "bg-[var(--danger)]" : "bg-[var(--accent)]",
                ].join(" ")}
                onClick={() => {
                  resolverRef.current?.(true);
                  close();
                }}
              >
                {opts.confirmText || "Confirmer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm doit être utilisé dans ConfirmProvider");
  return ctx;
}

