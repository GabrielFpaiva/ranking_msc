/** Helpers de formatação compartilhados pela UI. */

import type { EscalaUso, UsoDia } from './types';

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

/** `1` avança a janela, `-1` volta. */
export type DirecaoJanela = 1 | -1;

/**
 * Move a "janela" que a tela "Meu tempo de uso" está olhando — um mês para
 * as escalas `dia`/`semana`, um ano para `mes` — e devolve o novo `ref` já
 * dentro dela.
 *
 * Para navegação por mês, mantém o mesmo dia quando ele existe no mês de
 * destino, e cai no último dia válido quando não existe (ex.: 31 de março
 * → fevereiro vira 28, ou 29 em ano bissexto — nunca joga para março de
 * novo, nem quebra em "31 de fevereiro"). Para navegação por ano (escala
 * `mes`), o dia do `ref` não influencia nada que a tela mostra — os números
 * olham o mês inteiro e o gráfico olha o ano inteiro — então o novo `ref`
 * sempre cai no dia 1 do mesmo mês, no ano de destino: não há "dia certo"
 * a preservar, e dia 1 nunca precisa de clamp.
 *
 * `new Date(ano, mes, 1)` com `mes` fora de 0..11 é normalizado pelo próprio
 * motor JS (mês 12 vira janeiro do ano seguinte, mês -1 vira dezembro do
 * ano anterior) — é assim que a virada de dezembro/janeiro é tratada aqui,
 * sem aritmética manual de módulo.
 */
export function moverJanela(escala: EscalaUso, ref: string, direcao: DirecaoJanela): string {
  const atual = parseDataLocal(ref);

  if (escala === 'mes') {
    const novoAno = atual.getFullYear() + direcao;
    return `${novoAno}-${String(atual.getMonth() + 1).padStart(2, '0')}-01`;
  }

  const alvo = new Date(atual.getFullYear(), atual.getMonth() + direcao, 1);
  const novoAno = alvo.getFullYear();
  const novoMes = alvo.getMonth();
  const ultimoDiaDoMes = new Date(novoAno, novoMes + 1, 0).getDate();
  const novoDia = Math.min(atual.getDate(), ultimoDiaDoMes);

  return `${novoAno}-${String(novoMes + 1).padStart(2, '0')}-${String(novoDia).padStart(2, '0')}`;
}

/**
 * `true` quando avançar a janela de `ref` (um mês para `dia`/`semana`, um
 * ano para `mes`) levaria a uma janela inteiramente futura — nenhum dia
 * dela já aconteceu.
 *
 * Isso acontece exatamente quando a janela ATUAL de `ref` já é a janela de
 * hoje (ou uma além dela, que não deveria ser alcançável pela UI, mas fica
 * coberto por segurança). Usado para desabilitar o botão "›": ninguém
 * precisa navegar para um mês ou ano que ainda não começou.
 *
 * `hoje` é parâmetro para permitir teste determinístico — o padrão usa o
 * relógio real via `hojeISO()`.
 */
export function janelaSeguinteEhFutura(
  escala: EscalaUso,
  ref: string,
  hoje: string = hojeISO(),
): boolean {
  const dataRef = parseDataLocal(ref);
  const dataHoje = parseDataLocal(hoje);

  if (escala === 'mes') {
    return dataRef.getFullYear() >= dataHoje.getFullYear();
  }

  const chaveRef = dataRef.getFullYear() * 12 + dataRef.getMonth();
  const chaveHoje = dataHoje.getFullYear() * 12 + dataHoje.getMonth();
  return chaveRef >= chaveHoje;
}

const MESES_POR_EXTENSO = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

/**
 * Descreve a janela atual por extenso — `"Setembro 2026"` para as escalas
 * `dia`/`semana` (janela de mês), `"2026"` para `mes` (janela de ano).
 *
 * Mês por extenso via tabela própria, não `toLocaleDateString`: evita
 * depender de dados de locale do ambiente (Node/browser) só para um rótulo
 * de cabeçalho, e mantém o formato exato pedido, sem o "de" que
 * `Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' })`
 * insere entre mês e ano.
 */
export function descricaoJanela(escala: EscalaUso, ref: string): string {
  const data = parseDataLocal(ref);
  if (escala === 'mes') return String(data.getFullYear());
  return `${MESES_POR_EXTENSO[data.getMonth()]} ${data.getFullYear()}`;
}
