import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
type Kind = 'success' | 'error' | 'info';
const Context = createContext<{ show(message: string, kind?: Kind): void } | null>(null);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; kind: Kind } | null>(null);
  const show = useCallback((message: string, kind: Kind = 'success') => { setToast({ message, kind }); window.setTimeout(() => setToast(null), 3500); }, []);
  const value = useMemo(() => ({ show }), [show]);
  return <Context.Provider value={value}>{children}<div className={`toast${toast ? ` visible ${toast.kind}` : ''}`} role="status" aria-live="polite">{toast?.message}</div></Context.Provider>;
}
export function useToast() { const value = useContext(Context); if (!value) throw new Error('useToast 必须在 ToastProvider 内使用'); return value; }
