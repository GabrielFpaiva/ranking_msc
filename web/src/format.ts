/** Helpers de formatação compartilhados pela UI. */

import type { UsoDia } from './types';

/**
 * Formata um número como moeda BRL.
 *
 * Valores que arredondam para zero são normalizados para zero positivo, evitando
 * a exibição de "-R$ 0,00" (zero negativo) em saldos nulos.
 */
export function fmtBRL(v: number): string {
  const safe = Math.round(v * 100) === 0 ? 0 : v;
  return safe.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/**
 * Formata segundos como duração curta ("1h45" ou "45m").
 *
 * Usado tanto no badge de tempo de uso da sidebar (`UsoMini`) quanto na tela
 * de detalhe (`/uso`) — por isso mora aqui, e não em um componente.
 */
export function formatarDuracao(segundos: number): string {
  const totalMinutos = Math.floor(segundos / 60);
  const horas = Math.floor(totalMinutos / 60);
  const minutos = totalMinutos % 60;
  if (horas === 0) return `${minutos}m`;
  return `${horas}h${String(minutos).padStart(2, '0')}`;
}

/**
 * Interpreta uma data "YYYY-MM-DD" como meia-noite local, nunca UTC.
 *
 * `new Date("2026-09-01")` é tratado pelo motor JS como meia-noite UTC. Num
 * fuso negativo como o nosso (America/Recife, UTC-3), isso volta para as 21h
 * do dia anterior em horário local — `getDay()` e `getDate()` passam a
 * mentir sobre o dia da semana e o dia do mês. Construir o `Date` a partir
 * dos três componentes numéricos evita a conversão de fuso por completo.
 */
export function parseDataLocal(iso: string): Date {
  const [ano, mes, dia] = iso.split('-').map(Number);
  return new Date(ano, mes - 1, dia);
}

/**
 * Data de hoje em "YYYY-MM-DD", no fuso local do browser.
 *
 * Nunca via `toISOString()` — que converte para UTC e sofre do mesmo
 * deslize de fuso descrito em `parseDataLocal`, só que na direção contrária
 * (perto da meia-noite local, viraria o dia seguinte em vez do anterior).
 */
export function hojeISO(): string {
  const agora = new Date();
  const ano = agora.getFullYear();
  const mes = String(agora.getMonth() + 1).padStart(2, '0');
  const dia = String(agora.getDate()).padStart(2, '0');
  return `${ano}-${mes}-${dia}`;
}

/**
 * Agrupa os dias de um mês (já vindo do backend com zeros preenchidos, ver
 * `GET /api/uso/historico`) em semanas de segunda a domingo.
 *
 * Preenche com `null` os slots fora do mês nas duas pontas da grade — o
 * início da primeira semana quando o dia 1 não cai numa segunda, e o fim da
 * última quando o último dia não cai num domingo. `dias` não precisa vir
 * ordenado: a função ordena por segurança antes de agrupar.
 *
 * Única lógica não trivial da tela "Meu tempo de uso" — por isso vive fora
 * do componente, com testes próprios (lógica dentro de componente não é
 * testada de verdade).
 */
export function agruparEmSemanas(dias: UsoDia[]): (UsoDia | null)[][] {
  if (dias.length === 0) return [];

  const ordenados = [...dias].sort((a, b) => a.dia.localeCompare(b.dia));
  const semanas: (UsoDia | null)[][] = [];
  let semanaAtual: (UsoDia | null)[] = [];

  // getDay(): domingo=0 .. sábado=6. Queremos semana começando na segunda
  // (índice 0), então domingo vira o último slot (índice 6).
  const primeiroDiaSemana = parseDataLocal(ordenados[0].dia).getDay();
  const vaziosNoInicio = (primeiroDiaSemana + 6) % 7;
  for (let i = 0; i < vaziosNoInicio; i++) semanaAtual.push(null);

  for (const dia of ordenados) {
    semanaAtual.push(dia);
    if (semanaAtual.length === 7) {
      semanas.push(semanaAtual);
      semanaAtual = [];
    }
  }
  if (semanaAtual.length > 0) {
    while (semanaAtual.length < 7) semanaAtual.push(null);
    semanas.push(semanaAtual);
  }
  return semanas;
}
