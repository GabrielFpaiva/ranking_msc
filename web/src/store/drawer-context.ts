import { createContext } from 'react';

export type DrawerKind = 'rule' | 'conta';

export interface DrawerState {
  kind: DrawerKind;
  payload: string;
}

export interface DrawerContextValue {
  state: DrawerState | null;
  openRule: (ruleId: string) => void;
  openConta: (conta: string) => void;
  close: () => void;
}

export const DrawerContext = createContext<DrawerContextValue | null>(null);
