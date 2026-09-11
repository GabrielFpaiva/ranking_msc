// Tela "Meu tempo de uso" — período selecionável (dia/semana/mês) e
// detalhamento por tela. Os botões ‹ › movem o **período selecionado** por
// uma unidade da própria escala (um dia, uma semana, um mês — ver
// `moverPeriodo` em format.ts); o mesmo efeito é alcançado clicando direto
// numa barra/bloco do gráfico. O gráfico sempre mostra um nível de contexto
// acima do período selecionado, nunca o período isolado — 7 barras minúsculas
// pra destacar um único dia não ajudaria ninguém:
//
//   escala "dia"    → período = 1 dia    → gráfico = a semana daquele dia
//   escala "semana" → período = 1 semana → gráfico = o mês daquela semana
//   escala "mes"    → período = 1 mês    → gráfico = o ano daquele mês
//
// Consome GET /api/uso/historico?escala&ref (números do card + "Por tela") e,
// só na escala "mes", também GET /api/uso/anual?ano (as doze barras do ano).
// As duas buscas se repetem a cada 60s (mesma cadência do `UsoMini` da
// sidebar) enquanto a aba está visível, para os dois números da página
// andarem juntos — sem isso, quem deixa a tela aberta via a sidebar subir e
// esta tela parada. O refresh é silencioso: mantém os dados anteriores na
// tela em vez de voltar para "Carregando…" a cada tick.
// Ver app/api/routes/uso.py para a assimetria intencional: quando o período
// de `escala` cruza a virada do mês, `total_aberto_s`/`total_ativo_s`/`rotas`
// incluem os dois lados da fronteira, mas `dias` (usado para montar o
// calendário do mês e a semana em foco) cobre só o mês de `ref`. Não
// "corrigir" isso aqui — o gráfico é visão de contexto, os totais são visão
// de período.
//
// Por que não existe visão de hora do dia: a spec original previa a escala
// "Dia" mostrando as 24 horas do dia corrente, mas o armazenamento no
// backend agrega por `(usuário, dia, rota)` — sem granularidade de hora.
// Mostrar isso exigiria mudar o formato em disco (ver app/api/uso_store.py),
// o que ficou fora deste trabalho.

import { useEffect, useState } from 'react';

import { ApiError, api } from '../api/client';
import { ROUTE_TITLES } from '../routeTitles';
import {
  agruparEmSemanas,
  descricaoJanela,
  distribuirMaiorResto,
  formatarDuracao,
  hojeISO,
  moverPeriodo,
  periodoEhFuturo,
  periodoSeguinteEhFuturo,
} from '../format';
import type { DirecaoJanela } from '../format';
import type { EscalaUso, UsoAnual, UsoDia, UsoHistorico, UsoRota } from '../types';

// Mesma cadência de 60s do `UsoMini` (badge da sidebar) — sem isso, os dois
// números da mesma página andam em velocidades diferentes: a sidebar sobe a
// cada minuto, mas esta tela ficava parada até a próxima troca de
// escala/ref, dando a impressão de que a tela "travou" enquanto aberta.
const INTERVALO_ATUALIZACAO_MS = 60_000;

const ESCALAS: { valor: EscalaUso; rotulo: string }[] = [
  { valor: 'dia', rotulo: 'Dia' },
  { valor: 'semana', rotulo: 'Semana' },
  { valor: 'mes', rotulo: 'Mês' },
];

// Segunda a domingo — mesma ordem de `agruparEmSemanas`. "S T Q Q S S D"
// repete letra de propósito (Segunda/Sexta/Sábado, Terça, Quinta todas têm
// iniciais compartilhadas em português) — é o rótulo de calendário usual.
const LETRAS_DIA_SEMANA = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];

const MESES_ABREV = [
  'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez',
];

/** Formata uma data "YYYY-MM-DD" como "DD/MM" por fatiamento de string — sem
 * passar por `Date`, não há risco de deslocar o dia por fuso (ver
 * `parseDataLocal` em `format.ts` para o caminho que precisa de `Date`). */
function formatarDataCurta(iso: string): string {
  const [, mes, dia] = iso.split('-');
  return `${dia}/${mes}`;
}

/** Dia do mês (dois dígitos) a partir de "YYYY-MM-DD", por fatiamento. */
function diaDoMes(iso: string): string {
  return iso.slice(8, 10);
}

/** O dia entra no calendário exibido se cair dentro de `[inicio, fim]` do
 * período — para escala "dia" esse intervalo colapsa no próprio dia, para
 * "semana" cobre a semana inteira. Comparação de string funciona porque
 * `YYYY-MM-DD` ordena lexicograficamente igual à ordem cronológica. */
function estaNoPeriodo(dia: UsoDia, data: UsoHistorico): boolean {
  return dia.dia >= data.inicio && dia.dia <= data.fim;
}

// ---------------------------------------------------------------------------
// Paleta por rota — pilha empilhada (gráfico) e legenda horizontal "Por tela"
// ---------------------------------------------------------------------------
//
// Rank 1 (rota mais usada no domínio do gráfico) sempre ganha `--jp-red` —
// igual ao Screen Time do iPhone reserva a cor de destaque pro topo do
// ranking. As próximas quatro têm cores dedicadas em tokens.css. Acima de 5
// nomeadas, o resto vira "Outras": esta é uma ferramenta interna de
// prefeitura, não um painel de 11 cores, e a maioria dos dias reais tem 1–3
// rotas com uso que importa visualmente.
const CORES_RANK = [
  'var(--uso-cat-1)',
  'var(--uso-cat-2)',
  'var(--uso-cat-3)',
  'var(--uso-cat-4)',
  'var(--uso-cat-5)',
];
const COR_OUTRAS = 'var(--uso-cat-outras)';
// Chave sintética para o grupo "Outras" — nunca colide com uma rota real, que
// sempre começa com "/" (ver ROTAS_VALIDAS em app/api/uso_store.py).
const ROTA_OUTRAS = 'outras';

interface Segmento {
  rota: string;
  nome: string;
  segundos: number;
  cor: string;
}

/** Soma os segundos de cada rota ao longo de todas as colunas do gráfico (o
 * mês inteiro no calendário, o ano inteiro nas doze barras) e devolve as
 * rotas ordenadas da mais usada para a menos usada.
 *
 * Deliberadamente **não** usa `data.rotas` (que é só o total do período de
 * `escala`) — é o domínio inteiro do gráfico que decide rank e cor, para a
 * pilha ficar estável coluna a coluna e a cor de uma rota não mudar ao
 * navegar dentro do mesmo mês/ano. Ver cabeçalho do arquivo sobre a
 * diferença entre o domínio do gráfico e o do período selecionado. */
function ordenarRotasPorTotal(colunas: Record<string, number>[]): string[] {
  const totais = new Map<string, number>();
  for (const coluna of colunas) {
    for (const [rota, segundos] of Object.entries(coluna)) {
      totais.set(rota, (totais.get(rota) ?? 0) + segundos);
    }
  }
  return [...totais.entries()].sort((a, b) => b[1] - a[1]).map(([rota]) => rota);
}

/** Mapa rota → variável CSS de cor, para as até 5 primeiras posições do
 * ranking. Rota fora do mapa cai em "Outras" — ver `montarSegmentos` e
 * `montarLegenda`. */
function construirPaleta(ranking: string[]): Map<string, string> {
  const paleta = new Map<string, string>();
  ranking.slice(0, CORES_RANK.length).forEach((rota, i) => paleta.set(rota, CORES_RANK[i]));
  return paleta;
}

/** Converte o `por_rota` de uma coluna (um dia ou um mês) em segmentos
 * empilháveis, já na ordem em que devem entrar no DOM: rank 1 primeiro,
 * "Outras" por último. Combinado com `flex-direction: column-reverse` em
 * `.uso-barra-pilha`/`.uso-ano-barra-pilha` (globals.css), isso desenha a
 * rota mais usada embaixo da pilha. */
function montarSegmentos(
  porRota: Record<string, number>,
  ranking: string[],
  paleta: Map<string, string>,
): Segmento[] {
  const segmentos: Segmento[] = [];
  for (const rota of ranking.slice(0, paleta.size)) {
    const segundos = porRota[rota] ?? 0;
    if (segundos > 0) {
      segmentos.push({
        rota,
        nome: ROUTE_TITLES[rota]?.title ?? rota,
        segundos,
        cor: paleta.get(rota)!,
      });
    }
  }
  const outrasSegundos = Object.entries(porRota)
    .filter(([rota]) => !paleta.has(rota))
    .reduce((soma, [, segundos]) => soma + segundos, 0);
  if (outrasSegundos > 0) {
    segmentos.push({ rota: ROTA_OUTRAS, nome: 'Outras', segundos: outrasSegundos, cor: COR_OUTRAS });
  }
  return segmentos;
}

interface EntradaLegenda {
  rota: string;
  nome: string;
  segundos: number;
  /** Segundos de uso *ativo* dentro do aberto acima — sustenta a barrinha
   * ativo/ocioso e o texto pequeno de "ativo" do chip (ver JSX). Nunca maior
   * que `segundos`. */
  ativoSegundos: number;
  cor: string;
}

/** Mesma lógica de `montarSegmentos`, mas para os totais do período
 * selecionado (`data.rotas`) — sustenta a legenda horizontal "Por tela".
 * Recebe a mesma `paleta` do gráfico para que a cor de uma rota seja igual
 * na pilha e na legenda.
 *
 * Carrega `ativo_s` junto de `aberto_s` desde o início — não é possível
 * calcular "quanto do Outras foi ativo" depois de já ter jogado fora o
 * detalhe por rota, então a soma teria que ser refeita do zero. */
function montarLegenda(rotas: UsoRota[], paleta: Map<string, string>): EntradaLegenda[] {
  const entradas: EntradaLegenda[] = [];
  let outrasSegundos = 0;
  let outrasAtivoSegundos = 0;
  for (const r of rotas) {
    const cor = paleta.get(r.rota);
    if (cor) {
      entradas.push({
        rota: r.rota,
        nome: ROUTE_TITLES[r.rota]?.title ?? r.rota,
        segundos: r.aberto_s,
        ativoSegundos: r.ativo_s,
        cor,
      });
    } else {
      outrasSegundos += r.aberto_s;
      outrasAtivoSegundos += r.ativo_s;
    }
  }
  entradas.sort((a, b) => CORES_RANK.indexOf(a.cor) - CORES_RANK.indexOf(b.cor));
  if (outrasSegundos > 0) {
    entradas.push({
      rota: ROTA_OUTRAS,
      nome: 'Outras',
      segundos: outrasSegundos,
      ativoSegundos: outrasAtivoSegundos,
      cor: COR_OUTRAS,
    });
  }
  return entradas;
}

export function MeuTempo() {
  const [escala, setEscala] = useState<EscalaUso>('semana');
  const [ref, setRef] = useState<string>(() => hojeISO());
  const [data, setData] = useState<UsoHistorico | null>(null);
  const [anual, setAnual] = useState<UsoAnual | null>(null);
  const [anualError, setAnualError] = useState<string | null>(null);
  const [tentativaAnual, setTentativaAnual] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Busca inicial (ou de troca de escala/ref) mais um refresh silencioso a
  // cada 60s — mesma cadência do `UsoMini` na sidebar, para os dois números
  // da página andarem juntos enquanto a tela fica aberta.
  //
  // `comCarregamento` distingue as duas: só a busca inicial mostra o
  // skeleton de "Carregando…" e troca o banner de erro — o refresh
  // periódico atualiza `data` em silêncio e, se falhar, preserva o que já
  // estava na tela em vez de piscar para o estado de erro (uma falha de
  // rede de 60 em 60s não pode virar um banner piscando).
  useEffect(() => {
    let cancelado = false;

    function buscar(comCarregamento: boolean): void {
      if (comCarregamento) {
        setBusy(true);
        setData(null);
        setError(null);
      }
      api
        .usoHistorico(escala, ref)
        .then((resposta) => {
          if (!cancelado) {
            setData(resposta);
            setError(null);
          }
        })
        .catch((err: unknown) => {
          if (!cancelado && comCarregamento) {
            // Descarta o resultado anterior — mesma razão de Entregas.tsx:
            // sem isto, uma falha ao trocar de escala ou navegar deixaria os
            // controles no valor novo mas os números no período antigo.
            setData(null);
            setError(err instanceof ApiError ? err.userMessage : 'Erro ao carregar o tempo de uso.');
          }
          // Refresh silencioso que falha não mexe em `data`/`error` — a tela
          // continua mostrando o último dado bom até a próxima tentativa.
        })
        .finally(() => {
          if (!cancelado && comCarregamento) setBusy(false);
        });
    }

    buscar(true);

    const timer = window.setInterval(() => {
      // Aba oculta: sem usuário olhando, o refresh é só desperdício de
      // requisição — `document.visibilityState` é o mesmo sinal que
      // `useTempoUso` já usa para pausar o heartbeat quando a aba não está à
      // vista.
      if (document.visibilityState === 'visible') buscar(false);
    }, INTERVALO_ATUALIZACAO_MS);

    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, [escala, ref]);

  // Só a escala "mes" troca o gráfico de calendário do mês para as doze
  // barras do ano — busca separada do efeito acima: o card de números e o
  // "Por tela" têm seu próprio erro (banner principal), e uma falha aqui não
  // pode arrastar o resto da tela. Mas "não travar a tela" não é o mesmo que
  // "não dizer nada": sem um estado de falha próprio, uma requisição que
  // nunca resolve fica presa em "Carregando gráfico…" para sempre — o tipo
  // de coisa que vira chamado de suporte dizendo que a tela travou. Por isso
  // o gráfico guarda seu próprio `anualError`, mostrado só ali, sem banner.
  // Mesmo tratamento de "busca inicial vs. refresh silencioso" do efeito
  // acima, aplicado ao gráfico anual — ele também precisa acompanhar a
  // cadência de 60s, sem piscar para "Carregando gráfico…" nem para a
  // mensagem de falha a cada tick.
  useEffect(() => {
    if (escala !== 'mes') {
      setAnual(null);
      setAnualError(null);
      return;
    }
    let cancelado = false;
    const ano = Number(ref.slice(0, 4));

    function buscar(comCarregamento: boolean): void {
      if (comCarregamento) {
        setAnual(null);
        setAnualError(null);
      }
      api
        .usoAnual(ano)
        .then((resposta) => {
          if (!cancelado) {
            setAnual(resposta);
            setAnualError(null);
          }
        })
        .catch(() => {
          if (!cancelado && comCarregamento) {
            setAnual(null);
            setAnualError('Não foi possível carregar o gráfico do ano.');
          }
          // Refresh silencioso que falha preserva as doze barras já
          // desenhadas — sem isso, uma falha transitória de rede apagaria o
          // gráfico e mostraria a mensagem de erro por cima dele sozinha.
        });
    }

    buscar(true);

    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') buscar(false);
    }, INTERVALO_ATUALIZACAO_MS);

    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, [escala, ref, tentativaAnual]);

  const semanas = data ? agruparEmSemanas(data.dias) : [];
  const maxDia = data ? Math.max(1, ...data.dias.map((d) => d.aberto_s)) : 1;
  const maxMesDoAno = anual ? Math.max(1, ...anual.meses.map((m) => m.aberto_s)) : 1;
  const ociosoS = data ? Math.max(0, data.total_aberto_s - data.total_ativo_s) : 0;
  const proximaEhFutura = periodoSeguinteEhFuturo(escala, ref);
  const mesDoRef = ref.slice(0, 7);

  // Zoom progressivo: escala "dia" mostra só a semana que contém `ref`, não
  // o mês inteiro — 30 barras minúsculas para destacar uma só não ajudava
  // ninguém. `semanas` já cobre o mês inteiro (dado que já temos, sem nova
  // requisição); aqui só recortamos o bloco cuja faixa `[inicio, fim]` do
  // período contém algum dia real — sempre existe um, já que `data.inicio`
  // cai dentro do mês de `ref` por construção do backend.
  const semanaFoco: (UsoDia | null)[] =
    data && escala === 'dia'
      ? (semanas.find((semana) => semana.some((d) => d !== null && estaNoPeriodo(d, data))) ?? [])
      : [];
  const diasReaisFoco = semanaFoco.filter((d): d is UsoDia => d !== null);
  const somaSemanaFoco = diasReaisFoco.reduce((soma, d) => soma + d.aberto_s, 0);

  // Domínio de cores do gráfico: o ano inteiro (doze barras) quando a escala
  // é "mes" **e** o ano já carregou; caso contrário, o mês inteiro do
  // calendário — nunca só o período selecionado (ver `ordenarRotasPorTotal`).
  // O fallback pro mês importa: se a busca do ano falhar (`anualError`), a
  // legenda "Por tela" não pode desmoronar em "Outras" só porque o domínio
  // de cor mais amplo não carregou — ela usa o que já está disponível em
  // `data`, que é uma busca independente (ver useEffect acima).
  const rankingGrafico =
    escala === 'mes' && anual
      ? ordenarRotasPorTotal(anual.meses.map((m) => m.por_rota))
      : data
        ? ordenarRotasPorTotal(data.dias.map((d) => d.por_rota))
        : [];
  const paletaGrafico = construirPaleta(rankingGrafico);
  const legenda = data ? montarLegenda(data.rotas, paletaGrafico) : [];
  // "Por tela" precisa fechar: formatar cada entrada isoladamente (segundos
  // → minutos, segundos → percentual) trunca cada uma pra baixo de forma
  // independente — a soma dos minutos exibidos fica visivelmente abaixo do
  // total exibido, e os percentuais exibidos somam 99%, não 100 (ver
  // `distribuirMaiorResto` em format.ts). Os pesos são os segundos de cada
  // entrada — já incluindo "Outras" — que juntos somam exatamente
  // `data.total_aberto_s`, então as duas distribuições fecham certo.
  const pesosLegenda = legenda.map((item) => item.segundos);
  const totalMinutosExibido = data ? Math.floor(data.total_aberto_s / 60) : 0;
  const minutosLegenda = distribuirMaiorResto(pesosLegenda, totalMinutosExibido);
  const percentuaisLegenda = distribuirMaiorResto(pesosLegenda, 100);
  // Mesmo problema, mesmo remédio, agora para o "ativo" de cada chip: sem
  // isso, o card anuncia aberto/ativo/ocioso lá em cima mas só o aberto
  // aparece decomposto por tela embaixo — a pessoa não tem como enxergar,
  // por exemplo, que os 59min abertos de "Início" foram só 5min de uso de
  // verdade (54min de aba esquecida aberta). Pesos em segundos de novo, para
  // a soma dos minutos ativos exibidos fechar com `data.total_ativo_s`.
  const pesosAtivoLegenda = legenda.map((item) => item.ativoSegundos);
  const totalMinutosAtivoExibido = data ? Math.floor(data.total_ativo_s / 60) : 0;
  const minutosAtivoLegenda = distribuirMaiorResto(pesosAtivoLegenda, totalMinutosAtivoExibido);
  const minutosAtivoLimitados = minutosAtivoLegenda.map((valor, i) =>
    Math.min(valor, minutosLegenda[i] ?? 0),
  );

  function navegar(direcao: DirecaoJanela): void {
    setRef((atual) => moverPeriodo(escala, atual, direcao));
  }

  /** Seleciona um período direto — clique numa barra/bloco do gráfico, sem
   * passar pelos botões ‹ ›. `escala` não muda: só troca qual dia, semana ou
   * mês está selecionado dentro da escala atual. */
  function selecionar(novoRef: string): void {
    setRef(novoRef);
  }

  return (
    <div className="samid-stack uso-screen">
      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">
              {data ? `${formatarDataCurta(data.inicio)} a ${formatarDataCurta(data.fim)}` : 'Período'}
            </div>
            <h2 className="samid-card-title">
              {busy && !data ? 'Carregando…' : 'Meu tempo de uso'}
            </h2>
          </div>
          <div className="uso-escala-chips" role="group" aria-label="Escala do período">
            {ESCALAS.map((item) => (
              <button
                key={item.valor}
                type="button"
                className={`samid-chip${escala === item.valor ? ' active' : ''}`}
                onClick={() => setEscala(item.valor)}
              >
                {item.rotulo}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="samid-pill samid-pill-erro" role="alert">
            {error}
          </p>
        )}

        {data && (
          <>
            <div className="uso-header-row">
              <div className="uso-total uso-duration" data-testid="uso-total">
                {formatarDuracao(data.total_aberto_s)}
              </div>

              <div className="uso-resumo">
                <div className="uso-resumo-item">
                  <div className="samid-eyebrow">Aberto</div>
                  <div className="uso-duration uso-resumo-val" data-testid="uso-aberto">
                    {formatarDuracao(data.total_aberto_s)}
                  </div>
                </div>
                <div className="uso-resumo-item">
                  <div className="samid-eyebrow">Ativo</div>
                  <div className="uso-duration uso-resumo-val" data-testid="uso-ativo">
                    {formatarDuracao(data.total_ativo_s)}
                  </div>
                </div>
                <div className="uso-resumo-item">
                  <div className="samid-eyebrow">Ocioso</div>
                  <div className="uso-duration uso-resumo-val" data-testid="uso-ocioso">
                    {formatarDuracao(ociosoS)}
                  </div>
                </div>
              </div>
            </div>

            <div className="uso-grafico">
              <div className="uso-grafico-nav">
                <button
                  type="button"
                  className="uso-nav-btn"
                  aria-label="Período anterior"
                  disabled={escala === 'mes' && ref.slice(0, 7) <= '2020-01'}
                  onClick={() => navegar(-1)}
                >
                  ‹
                </button>
                <div className="samid-eyebrow">{descricaoJanela(escala, ref)}</div>
                <button
                  type="button"
                  className="uso-nav-btn"
                  aria-label="Próximo período"
                  disabled={proximaEhFutura}
                  onClick={() => navegar(1)}
                >
                  ›
                </button>
              </div>

              {escala === 'mes' ? (
                anualError ? (
                  <div className="uso-ano-falha">
                    <p>{anualError}</p>
                    <button
                      type="button"
                      className="uso-ano-retry"
                      onClick={() => setTentativaAnual((n) => n + 1)}
                    >
                      Tentar novamente
                    </button>
                  </div>
                ) : anual ? (
                  <div className="uso-ano-grafico" data-testid="uso-ano-grafico">
                    {anual.meses.map((m) => {
                      const refDoMes = `${m.mes}-01`;
                      const futuro = periodoEhFuturo('mes', refDoMes);
                      return (
                      <button
                        key={m.mes}
                        type="button"
                        className="uso-ano-col"
                        disabled={futuro}
                        onClick={() => selecionar(refDoMes)}
                        aria-label={`Selecionar ${MESES_ABREV[Number(m.mes.slice(5, 7)) - 1]} de ${m.mes.slice(0, 4)}`}
                        title={`${MESES_ABREV[Number(m.mes.slice(5, 7)) - 1]} — ${formatarDuracao(m.aberto_s)}`}
                      >
                        <div className="uso-ano-barra-track">
                          <div
                            className={`uso-ano-barra-pilha${
                              m.mes === mesDoRef ? ' uso-ano-barra-pilha-destaque' : ''
                            }${m.aberto_s === 0 ? ' uso-ano-barra-pilha-vestigial' : ''}`}
                            style={{
                              height:
                                m.aberto_s === 0 ? '6%' : `${Math.max(4, (m.aberto_s / maxMesDoAno) * 100)}%`,
                            }}
                          >
                            {montarSegmentos(m.por_rota, rankingGrafico, paletaGrafico).map((seg) => (
                              <div
                                key={seg.rota}
                                className="uso-ano-barra-seg"
                                style={{ flexGrow: seg.segundos, flexBasis: 0, minHeight: 2, background: seg.cor }}
                                title={`${seg.nome} — ${formatarDuracao(seg.segundos)}`}
                              />
                            ))}
                          </div>
                        </div>
                        <span className="uso-ano-mes-lbl">
                          {MESES_ABREV[Number(m.mes.slice(5, 7)) - 1]}
                        </span>
                      </button>
                      );
                    })}
                  </div>
                ) : (
                  <p className="samid-muted">Carregando gráfico…</p>
                )
              ) : escala === 'dia' ? (
                // Uma faixa só, esticada na largura inteira — mesmo
                // tratamento das doze barras do ano acima (`.uso-ano-*`),
                // com 7 colunas no lugar de 12. Nada de blocos de semana
                // aqui: aquele layout é da escala "semana" (mês inteiro).
                <>
                  <div className="uso-dia-grafico" data-testid="uso-dia-grafico">
                    {semanaFoco.map((dia, j) =>
                      dia ? (
                        <button
                          key={j}
                          type="button"
                          className={`uso-dia-col${estaNoPeriodo(dia, data) ? ' uso-dia-col-destaque' : ''}`}
                          disabled={periodoEhFuturo('dia', dia.dia)}
                          onClick={() => selecionar(dia.dia)}
                          aria-label={`Selecionar ${formatarDataCurta(dia.dia)}`}
                          title={`${formatarDataCurta(dia.dia)} — ${formatarDuracao(dia.aberto_s)}`}
                        >
                          <div className="uso-dia-barra-track">
                            <div
                              className={`uso-barra-pilha${
                                estaNoPeriodo(dia, data) ? ' uso-barra-pilha-destaque' : ''
                              }${dia.aberto_s === 0 ? ' uso-barra-pilha-vestigial' : ''}`}
                              style={{
                                height:
                                  dia.aberto_s === 0
                                    ? '6%'
                                    : `${Math.max(4, (dia.aberto_s / maxDia) * 100)}%`,
                              }}
                            >
                              {montarSegmentos(dia.por_rota, rankingGrafico, paletaGrafico).map((seg) => (
                                <div
                                  key={seg.rota}
                                  className="uso-barra-seg"
                                  style={{
                                    flexGrow: seg.segundos,
                                    flexBasis: 0,
                                    minHeight: 2,
                                    background: seg.cor,
                                  }}
                                  title={`${seg.nome} — ${formatarDuracao(seg.segundos)}`}
                                />
                              ))}
                            </div>
                          </div>
                          <span className="uso-dia-lbl">{LETRAS_DIA_SEMANA[j]}</span>
                        </button>
                      ) : (
                        <div key={j} className="uso-dia-col">
                          <div className="uso-dia-barra-track" />
                          <span className="uso-dia-lbl">{LETRAS_DIA_SEMANA[j]}</span>
                        </div>
                      ),
                    )}
                  </div>
                  {diasReaisFoco.length > 0 && (
                    <div className="uso-semana-rodape">
                      <span className="uso-semana-intervalo">
                        {diaDoMes(diasReaisFoco[0].dia)} – {diaDoMes(diasReaisFoco[diasReaisFoco.length - 1].dia)}
                      </span>
                      <span className="uso-duration uso-semana-total">{formatarDuracao(somaSemanaFoco)}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="uso-semanas" data-testid="uso-semanas">
                  {semanas.map((semana, i) => {
                    const diasReais = semana.filter((d): d is UsoDia => d !== null);
                    const somaSemana = diasReais.reduce((soma, d) => soma + d.aberto_s, 0);
                    // Todo bloco tem pelo menos um dia real por construção de
                    // `agruparEmSemanas` (só as pontas do mês ganham `null`).
                    const futuro = periodoEhFuturo('semana', diasReais[0].dia);
                    return (
                      <button
                        key={i}
                        type="button"
                        className="uso-semana-bloco"
                        disabled={futuro}
                        onClick={() => selecionar(diasReais[0].dia)}
                        aria-label={`Selecionar semana de ${diaDoMes(diasReais[0].dia)} a ${diaDoMes(
                          diasReais[diasReais.length - 1].dia,
                        )}`}
                      >
                        {/* Eixo de letras por bloco — com as semanas lado a
                            lado (não mais empilhadas), um cabeçalho único
                            acima de tudo não se alinharia com cada grade de
                            7 colunas, que agora tem sua própria largura. */}
                        <div className="uso-dias-letras" aria-hidden>
                          {LETRAS_DIA_SEMANA.map((letra, j) => (
                            <span key={j} className="uso-dia-letra">
                              {letra}
                            </span>
                          ))}
                        </div>
                        <div className="uso-semana">
                          {semana.map((dia, j) =>
                            dia ? (
                              <div
                                key={j}
                                className={`uso-barra-col${dia.aberto_s > 0 && estaNoPeriodo(dia, data) ? ' uso-barra-col-destaque' : ''}`}
                                title={`${formatarDataCurta(dia.dia)} — ${formatarDuracao(dia.aberto_s)}`}
                              >
                                {dia.aberto_s > 0 && (
                                  <div
                                    className={`uso-barra-pilha${
                                      estaNoPeriodo(dia, data) ? ' uso-barra-pilha-destaque' : ''
                                    }`}
                                    style={{
                                      height: `${Math.max(4, (dia.aberto_s / maxDia) * 100)}%`,
                                    }}
                                  >
                                    {montarSegmentos(dia.por_rota, rankingGrafico, paletaGrafico).map((seg) => (
                                      <div
                                        key={seg.rota}
                                        className="uso-barra-seg"
                                        style={{
                                          flexGrow: seg.segundos,
                                          flexBasis: 0,
                                          minHeight: 2,
                                          background: seg.cor,
                                        }}
                                        title={`${seg.nome} — ${formatarDuracao(seg.segundos)}`}
                                      />
                                    ))}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div key={j} className="uso-barra-col uso-barra-col-vazia" />
                            ),
                          )}
                        </div>
                        {diasReais.length > 0 && (
                          <div className="uso-semana-rodape">
                            <span className="uso-semana-intervalo">
                              {diaDoMes(diasReais[0].dia)} – {diaDoMes(diasReais[diasReais.length - 1].dia)}
                            </span>
                            <span className="uso-duration uso-semana-total">{formatarDuracao(somaSemana)}</span>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      <section className="samid-card">
        <div className="uso-por-tela-header">
          <div className="samid-eyebrow">Por tela</div>
          {data && (
            <div className="uso-legenda-total">
              <span className="uso-legenda-nome">Total aberto</span>
              <span className="uso-duration uso-legenda-tempo">
                {formatarDuracao(data.total_aberto_s)}
              </span>
            </div>
          )}
        </div>
        {data && data.rotas.length === 0 && (
          <div className="uso-empty" role="status">
            <span className="uso-empty-icon" aria-hidden="true">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
            </span>
            <h3>Sem uso registrado neste período</h3>
            <p>Escolha outro período para consultar seu histórico de uso.</p>
          </div>
        )}
        {data && data.rotas.length > 0 && (
          <div className="uso-legenda">
            {legenda.map((item, i) => {
              // Fração do aberto desta tela que foi ativo — governa a
              // barrinha de duas tonalidades logo abaixo. `Math.min(100, …)`
              // é rede de segurança (ativo nunca deveria passar do aberto).
              const pctAtivo =
                item.segundos > 0 ? Math.min(100, (item.ativoSegundos / item.segundos) * 100) : 0;
              return (
                <div key={item.rota} className="uso-legenda-item">
                  <span className="uso-legenda-dot" style={{ background: item.cor }} />
                  <span className="uso-legenda-corpo">
                    <span className="uso-legenda-nome">{item.nome}</span>
                    <span className="uso-legenda-linha2">
                      <span className="uso-duration uso-legenda-tempo">
                        {formatarDuracao(minutosLegenda[i] * 60)}
                      </span>
                      <span className="uso-legenda-pct">{percentuaisLegenda[i]}%</span>
                    </span>
                    {/* Ativo/ocioso desta tela: a mesma cor da categoria, cheia
                        na fração ativa e esmaecida (opacidade) no resto — dá
                        pra ver "quase tudo esmaecido" (aba esquecida aberta,
                        ex.: Início) sem ler número nenhum. O texto ao lado é
                        só reforço, pequeno de propósito — o protagonista
                        continua sendo o aberto, na linha de cima. */}
                    <span
                      className="uso-legenda-linha3"
                      title={`${formatarDuracao(minutosAtivoLimitados[i] * 60)} de uso ativo, de ${formatarDuracao(
                        minutosLegenda[i] * 60,
                      )} de tela aberta`}
                    >
                      <span className="uso-legenda-track">
                        <span
                          className="uso-legenda-track-ativo"
                          style={{ width: `${pctAtivo}%`, background: item.cor }}
                        />
                        <span
                          className="uso-legenda-track-ocioso"
                          style={{ width: `${100 - pctAtivo}%`, background: item.cor }}
                        />
                      </span>
                      <span className="uso-duration uso-legenda-ativo-tempo">
                        {formatarDuracao(minutosAtivoLimitados[i] * 60)}
                      </span>
                    </span>
                  </span>
                </div>
              );
            })}

          </div>
        )}
      </section>
    </div>
  );
}
