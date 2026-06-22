/** Helpers de formatação compartilhados pela UI. */

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
