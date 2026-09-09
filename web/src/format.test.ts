import { describe, expect, it } from 'vitest';

import { agruparEmSemanas, formatarDuracao, parseDataLocal } from './format';
import type { UsoDia } from './types';

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

describe('parseDataLocal', () => {
  it('não desloca o dia por fuso — ao contrário de `new Date(iso)`', () => {
    // Este é exatamente o bug clássico: `new Date("2026-09-01")` é UTC
    // meia-noite, que em fuso negativo (ex: America/Recife, UTC-3) volta
    // para 31/08 às 21h local. `parseDataLocal` tem que devolver dia 1.
    const data = parseDataLocal('2026-09-01');
    expect(data.getFullYear()).toBe(2026);
    expect(data.getMonth()).toBe(8); // setembro, zero-indexado
    expect(data.getDate()).toBe(1);
  });
});

/** Gera o mês inteiro (com zeros) no mesmo formato que o backend devolve em `dias`. */
function mesCompleto(ano: number, mes: number): UsoDia[] {
  const ultimoDia = new Date(ano, mes, 0).getDate();
  return Array.from({ length: ultimoDia }, (_, i) => {
    const dia = i + 1;
    return {
      dia: `${ano}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`,
      aberto_s: 0,
      ativo_s: 0,
    };
  });
}

/** Achata semanas para só os dias (ou `null`) — legível nas asserções. */
function achatar(semanas: (UsoDia | null)[][]): (string | null)[][] {
  return semanas.map((semana) => semana.map((d) => (d ? d.dia : null)));
}

describe('agruparEmSemanas', () => {
  it('mês vazio → nenhuma semana', () => {
    expect(agruparEmSemanas([])).toEqual([]);
  });

  it('mês começando na segunda: primeira semana sem vazios no início', () => {
    // Junho de 2026 começa numa segunda-feira.
    const semanas = agruparEmSemanas(mesCompleto(2026, 6));
    expect(achatar(semanas)[0]).toEqual([
      '2026-06-01', '2026-06-02', '2026-06-03', '2026-06-04',
      '2026-06-05', '2026-06-06', '2026-06-07',
    ]);
  });

  it('mês começando no domingo: seis vazios antes do dia 1', () => {
    // Novembro de 2026 começa num domingo — o dia 1 cai no último slot
    // (domingo) da primeira semana.
    const semanas = agruparEmSemanas(mesCompleto(2026, 11));
    expect(achatar(semanas)[0]).toEqual([null, null, null, null, null, null, '2026-11-01']);
  });

  it('fevereiro de 28 dias: nenhum dia 29 aparece e a grade fecha corretamente', () => {
    const semanas = agruparEmSemanas(mesCompleto(2026, 2));
    const diasReais = achatar(semanas).flat().filter((d): d is string => d !== null);
    expect(diasReais).toHaveLength(28);
    expect(diasReais[diasReais.length - 1]).toBe('2026-02-28');
    expect(diasReais).not.toContain('2026-02-29');
  });

  it('preenche vazios corretamente nas duas pontas quando o mês precisa de ambos', () => {
    // Setembro de 2026 começa numa terça (1 vazio no início) e termina numa
    // quarta (4 vazios no fim) — as duas pontas da grade num mesmo mês.
    const semanas = agruparEmSemanas(mesCompleto(2026, 9));
    const achatada = achatar(semanas);
    expect(achatada[0]).toEqual([
      null, '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-05', '2026-09-06',
    ]);
    expect(achatada[achatada.length - 1]).toEqual([
      '2026-09-28', '2026-09-29', '2026-09-30', null, null, null, null,
    ]);
  });
});
