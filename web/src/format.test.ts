import { describe, expect, it } from 'vitest';

import {
  agruparEmSemanas,
  descricaoJanela,
  formatarDuracao,
  janelaSeguinteEhFutura,
  moverJanela,
  parseDataLocal,
} from './format';
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

describe('moverJanela', () => {
  it('dia inexistente no mês de destino é clampado (31 de março → fevereiro)', () => {
    // Fevereiro de 2026 tem 28 dias (não bissexto) — dia 31 não existe.
    expect(moverJanela('semana', '2026-03-31', -1)).toBe('2026-02-28');
    expect(moverJanela('dia', '2026-03-31', -1)).toBe('2026-02-28');
  });

  it('clampa para o dia 29 num fevereiro bissexto', () => {
    expect(moverJanela('dia', '2024-03-31', -1)).toBe('2024-02-29');
  });

  it('virada de ano ao avançar de dezembro para janeiro', () => {
    expect(moverJanela('dia', '2026-12-15', 1)).toBe('2027-01-15');
  });

  it('virada de ano ao voltar de janeiro para dezembro', () => {
    expect(moverJanela('semana', '2026-01-10', -1)).toBe('2025-12-10');
  });

  it('dia do mês preservado quando existe no mês de destino', () => {
    expect(moverJanela('dia', '2026-06-15', 1)).toBe('2026-07-15');
  });

  it('escala "mes" navega por ano e sempre cai no dia 1 do mesmo mês', () => {
    expect(moverJanela('mes', '2026-05-20', 1)).toBe('2027-05-01');
    expect(moverJanela('mes', '2026-05-20', -1)).toBe('2025-05-01');
  });

  it('escala "mes" nunca quebra num 29/02 de ano não bissexto — cai sempre em dia 1', () => {
    expect(moverJanela('mes', '2024-02-29', 1)).toBe('2025-02-01');
  });
});

describe('janelaSeguinteEhFutura', () => {
  it('escala dia/semana: bloqueia avançar quando já se está no mês corrente', () => {
    expect(janelaSeguinteEhFutura('dia', '2026-09-01', '2026-09-09')).toBe(true);
    expect(janelaSeguinteEhFutura('semana', '2026-09-30', '2026-09-09')).toBe(true);
  });

  it('escala dia/semana: permite avançar de um mês passado para o corrente', () => {
    expect(janelaSeguinteEhFutura('dia', '2026-08-01', '2026-09-09')).toBe(false);
  });

  it('escala dia/semana: bloqueia mesmo virando o ano (dezembro passado, janeiro corrente)', () => {
    expect(janelaSeguinteEhFutura('dia', '2027-01-05', '2027-01-20')).toBe(true);
    expect(janelaSeguinteEhFutura('dia', '2026-12-05', '2027-01-20')).toBe(false);
  });

  it('escala mes: bloqueia avançar quando já se está no ano corrente', () => {
    expect(janelaSeguinteEhFutura('mes', '2026-01-01', '2026-09-09')).toBe(true);
  });

  it('escala mes: permite avançar de um ano passado para o corrente', () => {
    expect(janelaSeguinteEhFutura('mes', '2025-06-01', '2026-09-09')).toBe(false);
  });
});

describe('descricaoJanela', () => {
  it('escala dia/semana descreve o mês por extenso com o ano', () => {
    expect(descricaoJanela('semana', '2026-09-09')).toBe('Setembro 2026');
    expect(descricaoJanela('dia', '2026-01-01')).toBe('Janeiro 2026');
  });

  it('escala mes descreve só o ano', () => {
    expect(descricaoJanela('mes', '2026-09-09')).toBe('2026');
  });
});
