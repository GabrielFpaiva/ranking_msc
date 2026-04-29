import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import type { RunSummary } from '../types';

interface MCRAContextValue {
  siconfi: string | null;
  competencia: string | null;
  lastRun: RunSummary | null;
  setCurrent: (siconfi: string, competencia: string) => void;
  setLastRun: (summary: RunSummary) => void;
  reset: () => void;
}

const STORAGE_KEY = 'mcra-current';

interface PersistedState {
  siconfi: string | null;
  competencia: string | null;
}

function loadPersisted(): PersistedState {
  if (typeof window === 'undefined') return { siconfi: null, competencia: null };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { siconfi: null, competencia: null };
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    return {
      siconfi: parsed.siconfi ?? null,
      competencia: parsed.competencia ?? null,
    };
  } catch {
    return { siconfi: null, competencia: null };
  }
}

function persist(state: PersistedState): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full ou desabilitado — ignoramos.
  }
}

const MCRAContext = createContext<MCRAContextValue | null>(null);

export function MCRAProvider({ children }: { children: ReactNode }) {
  const initial = loadPersisted();
  const [siconfi, setSiconfi] = useState<string | null>(initial.siconfi);
  const [competencia, setCompetencia] = useState<string | null>(initial.competencia);
  const [lastRun, setLastRunState] = useState<RunSummary | null>(null);

  const setCurrent = useCallback((s: string, c: string) => {
    setSiconfi(s);
    setCompetencia(c);
    persist({ siconfi: s, competencia: c });
  }, []);

  const setLastRun = useCallback((summary: RunSummary) => {
    setLastRunState(summary);
    setSiconfi(summary.siconfi);
    setCompetencia(summary.competencia);
    persist({ siconfi: summary.siconfi, competencia: summary.competencia });
  }, []);

  const reset = useCallback(() => {
    setSiconfi(null);
    setCompetencia(null);
    setLastRunState(null);
    persist({ siconfi: null, competencia: null });
  }, []);

  const value = useMemo<MCRAContextValue>(
    () => ({ siconfi, competencia, lastRun, setCurrent, setLastRun, reset }),
    [siconfi, competencia, lastRun, setCurrent, setLastRun, reset],
  );

  return <MCRAContext.Provider value={value}>{children}</MCRAContext.Provider>;
}

export function useMCRA(): MCRAContextValue {
  const ctx = useContext(MCRAContext);
  if (!ctx) throw new Error('useMCRA must be used inside <MCRAProvider>');
  return ctx;
}
