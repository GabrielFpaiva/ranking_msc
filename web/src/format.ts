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

/** Formata um `Date` local (nunca UTC) como "YYYY-MM-DD" — o inverso de
 * `parseDataLocal`. Compartilhado por `hojeISO` e por `moverJanela` (escala
 * "dia", que faz aritmética de `Date` para navegar por semana). */
function formatarISO(d: Date): string {
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, '0');
  const dia = String(d.getDate()).padStart(2, '0');
  return `${ano}-${mes}-${dia}`;
}

/**
 * Data de hoje em "YYYY-MM-DD", no fuso local do browser.
 *
 * Nunca via `toISOString()` — que converte para UTC e sofre do mesmo
 * deslize de fuso descrito em `parseDataLocal`, só que na direção contrária
 * (perto da meia-noite local, viraria o dia seguinte em vez do anterior).
 */
export function hojeISO(): string {
  return formatarISO(new Date());
}

/** Segunda-feira (meia-noite local) da semana que contém `d` — mesma
 * convenção de semana (segunda a domingo) usada por `agruparEmSemanas`. */
function segundaDaSemana(d: Date): Date {
  const deslocamento = (d.getDay() + 6) % 7; // domingo=0 vira 6, segunda=1 vira 0
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - deslocamento);
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

/** `1` avança o período selecionado, `-1` volta. */
export type DirecaoJanela = 1 | -1;

/**
 * Move o **período selecionado** por uma unidade da própria escala e devolve
 * o novo `ref`. Nada de zoom de janela aqui — cada escala navega no seu
 * próprio tamanho:
 *
 * - `dia`    → 1 dia.
 * - `semana` → 7 dias corridos.
 * - `mes`    → 1 mês (sempre cai no dia 1 — o dia do `ref` não influencia
 *              nada que a tela mostra nesta escala, então não há "dia certo"
 *              a preservar nem clamp de fim de mês a fazer).
 *
 * O gráfico mostra um nível de contexto acima do período (a semana em torno
 * do dia, o mês em torno da semana, o ano em torno do mês — ver
 * `MeuTempo.tsx`), mas isso é só apresentação: quem decide o tamanho do
 * passo de navegação é a própria escala, não o gráfico.
 *
 * `new Date(ano, mes, dia)` com componentes fora do intervalo normal é
 * normalizado pelo próprio motor JS (dia 32 de janeiro vira 1º de fevereiro,
 * mês 12 vira janeiro do ano seguinte etc.) — é assim que a virada de
 * mês/ano é tratada aqui, sem aritmética manual de módulo.
 */
export function moverPeriodo(escala: EscalaUso, ref: string, direcao: DirecaoJanela): string {
  const atual = parseDataLocal(ref);

  if (escala === 'mes') {
    const alvo = new Date(atual.getFullYear(), atual.getMonth() + direcao, 1);
    return formatarISO(alvo);
  }

  const deltaDias = escala === 'semana' ? direcao * 7 : direcao;
  const alvo = new Date(atual.getFullYear(), atual.getMonth(), atual.getDate() + deltaDias);
  return formatarISO(alvo);
}

/**
 * `true` quando o período de `escala` que contém `ref` já é inteiramente
 * futuro em relação a `hoje` — nenhum dia dele já aconteceu. Usado para
 * desabilitar o clique numa barra/bloco do gráfico (um dia, semana ou mês
 * que ainda não começou não é uma seleção válida).
 *
 * Note a diferença para `periodoSeguinteEhFuturo`: aquela pergunta é "avançar
 * a partir do período ATUAL levaria a um período futuro" (por isso usa
 * `>=` — o período de hoje já foi alcançado, então "avançar" a partir dele
 * seria ultrapassar hoje). Esta função pergunta sobre o próprio `ref`
 * recebido: só um período estritamente posterior ao de hoje é futuro — o
 * próprio período de hoje não é (`>`, não `>=`).
 *
 * `hoje` é parâmetro para permitir teste determinístico — o padrão usa o
 * relógio real via `hojeISO()`.
 */
export function periodoEhFuturo(
  escala: EscalaUso,
  ref: string,
  hoje: string = hojeISO(),
): boolean {
  const dataRef = parseDataLocal(ref);
  const dataHoje = parseDataLocal(hoje);

  if (escala === 'dia') {
    return dataRef.getTime() > dataHoje.getTime();
  }

  if (escala === 'semana') {
    // Comparação pela segunda-feira de cada semana — semanas correm de
    // segunda a domingo (mesma convenção de `agruparEmSemanas`).
    return segundaDaSemana(dataRef).getTime() > segundaDaSemana(dataHoje).getTime();
  }

  const chaveRef = dataRef.getFullYear() * 12 + dataRef.getMonth();
  const chaveHoje = dataHoje.getFullYear() * 12 + dataHoje.getMonth();
  return chaveRef > chaveHoje;
}

/**
 * `true` quando avançar o período selecionado de `ref` (ver `moverPeriodo`)
 * levaria a um período futuro. Usado para desabilitar o botão "›": ninguém
 * precisa navegar para um dia, semana ou mês que ainda não começou.
 *
 * Equivale a "hoje não é estritamente posterior a `ref`" — trocar a ordem
 * dos argumentos de `periodoEhFuturo` reaproveita a mesma comparação de
 * três ramos (dia/semana/mês) sem duplicá-la: "hoje > ref" nega para
 * "ref >= hoje", que é exatamente "ref já alcançou (ou passou) o período
 * de hoje".
 *
 * `hoje` é parâmetro para permitir teste determinístico — o padrão usa o
 * relógio real via `hojeISO()`.
 */
export function periodoSeguinteEhFuturo(
  escala: EscalaUso,
  ref: string,
  hoje: string = hojeISO(),
): boolean {
  return !periodoEhFuturo(escala, hoje, ref);
}

const MESES_POR_EXTENSO = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

/** "DD de mês" a partir de um `Date` local — ex.: `"09 de setembro"`. Usado
 * tanto para o dia isolado (escala `dia`) quanto para as pontas de uma
 * semana que cruza a virada do mês (escala `semana`). */
function diaPorExtenso(d: Date): string {
  const dia = String(d.getDate()).padStart(2, '0');
  return `${dia} de ${MESES_POR_EXTENSO[d.getMonth()].toLowerCase()}`;
}

/**
 * Descreve o **período selecionado** (não o gráfico, que mostra um nível de
 * contexto acima — ver `MeuTempo.tsx`): `"09 de setembro"` para `dia`,
 * `"07 – 13 de setembro"` para `semana`, `"Setembro 2026"` para `mes`.
 *
 * A semana (`semana`) repete o mês só quando a segunda e o domingo caem em
 * meses diferentes (`"31 de agosto – 06 de setembro"`) — sem isso, uma
 * semana que cruza a virada do mês (ou do ano) ficaria ambígua com só os
 * números dos dias.
 *
 * Mês por extenso via tabela própria, não `toLocaleDateString`: evita
 * depender de dados de locale do ambiente (Node/browser) só para um rótulo
 * de cabeçalho, e mantém o formato exato pedido.
 */
export function descricaoJanela(escala: EscalaUso, ref: string): string {
  const data = parseDataLocal(ref);

  if (escala === 'dia') return diaPorExtenso(data);

  if (escala === 'semana') {
    const segunda = segundaDaSemana(data);
    const domingo = new Date(segunda.getFullYear(), segunda.getMonth(), segunda.getDate() + 6);
    if (segunda.getMonth() === domingo.getMonth()) {
      const diaSegunda = String(segunda.getDate()).padStart(2, '0');
      const diaDomingo = String(domingo.getDate()).padStart(2, '0');
      return `${diaSegunda} – ${diaDomingo} de ${MESES_POR_EXTENSO[segunda.getMonth()].toLowerCase()}`;
    }
    return `${diaPorExtenso(segunda)} – ${diaPorExtenso(domingo)}`;
  }

  // escala === 'mes'
  return `${MESES_POR_EXTENSO[data.getMonth()]} ${data.getFullYear()}`;
}
