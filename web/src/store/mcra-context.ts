import { createContext } from 'react';

import type { RunSummary } from '../types';

export interface MCRAContextValue {
  siconfi: string | null;
  competencia: string | null;
  lastRun: RunSummary | null;
  setCurrent: (siconfi: string, competencia: string) => void;
  setLastRun: (summary: RunSummary) => void;
  reset: () => void;
}

export const MCRAContext = createContext<MCRAContextValue | null>(null);
