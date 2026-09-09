import { describe, expect, it } from 'vitest';

import { formatarDuracao } from './format';

describe('formatarDuracao', () => {
  it('zero segundos → "0m"', () => {
    expect(formatarDuracao(0)).toBe('0m');
  });

  it('menos de uma hora → só minutos', () => {
    expect(formatarDuracao(45 * 60)).toBe('45m');
  });

  it('exatamente uma hora → "1h00"', () => {
    expect(formatarDuracao(3600)).toBe('1h00');
  });

  it('minutos precisam de zero à esquerda → "1h01"', () => {
    expect(formatarDuracao(3660)).toBe('1h01');
  });
});
