import { useContext } from 'react';

import { MCRAContext } from './mcra-context';

export function useMCRA() {
  const ctx = useContext(MCRAContext);
  if (!ctx) throw new Error('useMCRA must be used inside <MCRAProvider>');
  return ctx;
}
