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
