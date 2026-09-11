import { describe, expect, it } from 'vitest';

import {
  agruparEmSemanas,
  descricaoJanela,
  distribuirMaiorResto,
  formatarDuracao,
  moverPeriodo,
  parseDataLocal,
  periodoEhFuturo,
  periodoSeguinteEhFuturo,
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

describe('distribuirMaiorResto', () => {
  it('as partes somam exatamente o total, num caso com vários restos grandes e empatados', () => {
    // Sete pesos iguais não dividem 10 exatamente (10/7 ≈ 1,4286) — todo
    // mundo descarta a mesma fração grande (~0,43) ao arredondar pra baixo.
    // O empate é resolvido pela ordem original (sort estável): as três
    // primeiras entradas levam a unidade extra.
    const resultado = distribuirMaiorResto([1, 1, 1, 1, 1, 1, 1], 10);
    expect(resultado).toEqual([2, 2, 2, 1, 1, 1, 1]);
    expect(resultado.reduce((soma, v) => soma + v, 0)).toBe(10);
  });

  it('os percentuais somam exatamente 100', () => {
    // Mesmos segundos do caso real que motivou o conserto (soma = 18301s).
    const pesos = [7200, 5400, 3601, 2100];
    const resultado = distribuirMaiorResto(pesos, 100);
    expect(resultado.reduce((soma, v) => soma + v, 0)).toBe(100);
  });

  it('os minutos exibidos somam exatamente os minutos exibidos do total', () => {
    const pesos = [7200, 5400, 3601, 2100]; // soma = 18301s
    const totalMinutosExibido = Math.floor(18301 / 60); // 305
    const resultado = distribuirMaiorResto(pesos, totalMinutosExibido);
    expect(resultado.reduce((soma, v) => soma + v, 0)).toBe(totalMinutosExibido);
  });

  it('uma entrada só recebe o total inteiro', () => {
    expect(distribuirMaiorResto([12345], 205)).toEqual([205]);
  });

  it('entradas de valor zero ficam zeradas e não atrapalham a soma', () => {
    const resultado = distribuirMaiorResto([0, 10, 0, 5], 100);
    expect(resultado[0]).toBe(0);
    expect(resultado[2]).toBe(0);
    expect(resultado.reduce((soma, v) => soma + v, 0)).toBe(100);
  });

  it('total zero devolve só zeros, sem dividir por zero nem NaN', () => {
    const resultado = distribuirMaiorResto([10, 20, 30], 0);
    expect(resultado).toEqual([0, 0, 0]);
    expect(resultado.some(Number.isNaN)).toBe(false);
  });

  it('pesos todos zero com total positivo não gera NaN (caso degenerado documentado)', () => {
    const resultado = distribuirMaiorResto([0, 0, 0], 10);
    expect(resultado).toEqual([0, 0, 0]);
    expect(resultado.some(Number.isNaN)).toBe(false);
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
      por_rota: {},
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

describe('moverPeriodo', () => {
  it('escala "dia" navega 1 dia por vez', () => {
    expect(moverPeriodo('dia', '2026-09-09', 1)).toBe('2026-09-10');
    expect(moverPeriodo('dia', '2026-09-09', -1)).toBe('2026-09-08');
  });

  it('escala "dia": cruza a virada do mês e do ano', () => {
    expect(moverPeriodo('dia', '2026-09-30', 1)).toBe('2026-10-01');
    expect(moverPeriodo('dia', '2026-12-31', 1)).toBe('2027-01-01');
    expect(moverPeriodo('dia', '2027-01-01', -1)).toBe('2026-12-31');
  });

  it('escala "semana" navega 7 dias corridos por vez', () => {
    expect(moverPeriodo('semana', '2026-09-09', 1)).toBe('2026-09-16');
    expect(moverPeriodo('semana', '2026-09-09', -1)).toBe('2026-09-02');
  });

  it('escala "semana": cruza a virada do mês e do ano', () => {
    expect(moverPeriodo('semana', '2026-09-28', 1)).toBe('2026-10-05');
    expect(moverPeriodo('semana', '2026-12-28', 1)).toBe('2027-01-04');
    expect(moverPeriodo('semana', '2027-01-03', -1)).toBe('2026-12-27');
  });

  it('escala "mes" navega 1 mês por vez e sempre cai no dia 1 — o dia do ref não importa nessa escala', () => {
    expect(moverPeriodo('mes', '2026-05-20', 1)).toBe('2026-06-01');
    expect(moverPeriodo('mes', '2026-05-20', -1)).toBe('2026-04-01');
  });

  it('escala "mes": cruza a virada do ano nos dois sentidos', () => {
    expect(moverPeriodo('mes', '2026-12-15', 1)).toBe('2027-01-01');
    expect(moverPeriodo('mes', '2027-01-15', -1)).toBe('2026-12-01');
  });
});

describe('periodoEhFuturo', () => {
  it('escala "dia": só um dia estritamente depois de hoje é futuro', () => {
    expect(periodoEhFuturo('dia', '2026-09-10', '2026-09-09')).toBe(true);
    expect(periodoEhFuturo('dia', '2026-09-09', '2026-09-09')).toBe(false);
    expect(periodoEhFuturo('dia', '2026-09-08', '2026-09-09')).toBe(false);
  });

  it('escala "semana": só uma semana estritamente depois da semana corrente é futura', () => {
    // Hoje = quarta 09/09/2026; semana corrente = segunda 07/09 a domingo 13/09.
    expect(periodoEhFuturo('semana', '2026-09-16', '2026-09-09')).toBe(true); // semana seguinte
    expect(periodoEhFuturo('semana', '2026-09-07', '2026-09-09')).toBe(false); // a própria semana corrente
    expect(periodoEhFuturo('semana', '2026-09-02', '2026-09-09')).toBe(false); // semana passada
  });

  it('escala "mes": só um mês estritamente depois do mês corrente é futuro', () => {
    expect(periodoEhFuturo('mes', '2026-10-01', '2026-09-09')).toBe(true);
    expect(periodoEhFuturo('mes', '2026-09-01', '2026-09-09')).toBe(false);
    expect(periodoEhFuturo('mes', '2026-08-15', '2026-09-09')).toBe(false);
  });
});

describe('periodoSeguinteEhFuturo', () => {
  it('escala "dia": bloqueia avançar quando já se está em hoje', () => {
    expect(periodoSeguinteEhFuturo('dia', '2026-09-09', '2026-09-09')).toBe(true);
  });

  it('escala "dia": permite avançar de ontem para hoje', () => {
    expect(periodoSeguinteEhFuturo('dia', '2026-09-08', '2026-09-09')).toBe(false);
  });

  it('escala "semana": bloqueia avançar quando já se está na semana corrente', () => {
    expect(periodoSeguinteEhFuturo('semana', '2026-09-07', '2026-09-09')).toBe(true);
    expect(periodoSeguinteEhFuturo('semana', '2026-09-13', '2026-09-09')).toBe(true);
  });

  it('escala "semana": permite avançar de uma semana passada para a corrente, cruzando o ano', () => {
    expect(periodoSeguinteEhFuturo('semana', '2026-09-02', '2026-09-09')).toBe(false);
    // Semana anterior cruza a virada do ano: segunda 28/12/2026 a domingo
    // 03/01/2027 — imediatamente antes da semana corrente de hoje (04/01/2027).
    expect(periodoSeguinteEhFuturo('semana', '2026-12-30', '2027-01-06')).toBe(false);
  });

  it('escala "mes": bloqueia avançar quando já se está no mês corrente', () => {
    expect(periodoSeguinteEhFuturo('mes', '2026-09-01', '2026-09-09')).toBe(true);
  });

  it('escala "mes": permite avançar de um mês passado para o corrente, cruzando o ano', () => {
    expect(periodoSeguinteEhFuturo('mes', '2026-08-15', '2026-09-09')).toBe(false);
    expect(periodoSeguinteEhFuturo('mes', '2026-12-05', '2027-01-20')).toBe(false);
    expect(periodoSeguinteEhFuturo('mes', '2027-01-05', '2027-01-20')).toBe(true);
  });
});

describe('descricaoJanela', () => {
  it('escala "dia" descreve o dia selecionado em "DD de mês"', () => {
    expect(descricaoJanela('dia', '2026-09-09')).toBe('09 de setembro');
    expect(descricaoJanela('dia', '2026-01-01')).toBe('01 de janeiro');
  });

  it('escala "semana" descreve a semana (segunda a domingo) em "DD – DD de mês"', () => {
    // 09/09/2026 é quarta; a semana vai de segunda 07/09 a domingo 13/09.
    expect(descricaoJanela('semana', '2026-09-09')).toBe('07 – 13 de setembro');
  });

  it('escala "semana": semana que cruza a virada do mês repete o mês nas duas pontas', () => {
    // 02/09/2026 é quarta; a semana vai de segunda 31/08 a domingo 06/09.
    expect(descricaoJanela('semana', '2026-09-02')).toBe('31 de agosto – 06 de setembro');
  });

  it('escala "mes" descreve o mês por extenso com o ano', () => {
    expect(descricaoJanela('mes', '2026-09-09')).toBe('Setembro 2026');
    expect(descricaoJanela('mes', '2026-01-01')).toBe('Janeiro 2026');
  });
});
