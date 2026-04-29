import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

type DrawerKind = 'rule' | 'conta';

interface DrawerState {
  kind: DrawerKind;
  payload: string;
}

interface DrawerContextValue {
  state: DrawerState | null;
  openRule: (ruleId: string) => void;
  openConta: (conta: string) => void;
  close: () => void;
}

const DrawerContext = createContext<DrawerContextValue | null>(null);

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DrawerState | null>(null);

  const openRule = useCallback((ruleId: string) => setState({ kind: 'rule', payload: ruleId }), []);
  const openConta = useCallback((conta: string) => setState({ kind: 'conta', payload: conta }), []);
  const close = useCallback(() => setState(null), []);

  useEffect(() => {
    if (!state) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [state, close]);

  const value = useMemo<DrawerContextValue>(
    () => ({ state, openRule, openConta, close }),
    [state, openRule, openConta, close],
  );

  return <DrawerContext.Provider value={value}>{children}</DrawerContext.Provider>;
}

export function useDrawer(): DrawerContextValue {
  const ctx = useContext(DrawerContext);
  if (!ctx) throw new Error('useDrawer must be used inside <DrawerProvider>');
  return ctx;
}
