// Tela "Meu tempo de uso" — período selecionável (dia/semana/mês), navegação
// por mês ou ano, gráfico do período (calendário do mês ou barras do ano) e
// detalhamento por tela.
//
// Consome GET /api/uso/historico?escala&ref (números do card + "Por tela") e,
// só na escala "mes", também GET /api/uso/anual?ano (as doze barras do ano).
// Ver app/api/routes/uso.py para a assimetria intencional: quando o período
// de `escala` cruza a virada do mês, `total_aberto_s`/`total_ativo_s`/`rotas`
// incluem os dois lados da fronteira, mas `dias` (o calendário) cobre só o
// mês de `ref`. Não "corrigir" isso aqui — o gráfico é visão de mês (ou de
// ano, na escala "mes"), os totais são visão de período.
//
// Por que não existe visão de hora do dia: a spec original previa a escala
// "Dia" mostrando as 24 horas do dia corrente, mas o armazenamento no
// backend agrega por `(usuário, dia, rota)` — sem granularidade de hora.
// Mostrar isso exigiria mudar o formato em disco (ver app/api/uso_store.py),
// o que ficou fora deste trabalho. "Dia" continua existindo como período —
// números e "Por tela" refletem só aquele dia — mas o gráfico permanece
// sendo o calendário do mês, com o dia destacado. Não tente "completar" a
// visão de hora sem antes resolver isso no backend.

import { useEffect, useState } from 'react';

import { ApiError, api } from '../api/client';
import { ROUTE_TITLES } from '../components/TopBar';
import {
  agruparEmSemanas,
  descricaoJanela,
  formatarDuracao,
  hojeISO,
  janelaSeguinteEhFutura,
  moverJanela,
} from '../format';
import type { DirecaoJanela } from '../format';
import type { EscalaUso, UsoAnual, UsoDia, UsoHistorico } from '../types';

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

export function MeuTempo() {
  const [escala, setEscala] = useState<EscalaUso>('semana');
  const [ref, setRef] = useState<string>(() => hojeISO());
  const [data, setData] = useState<UsoHistorico | null>(null);
  const [anual, setAnual] = useState<UsoAnual | null>(null);
  const [anualError, setAnualError] = useState<string | null>(null);
  const [tentativaAnual, setTentativaAnual] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelado = false;
    setBusy(true);
    setError(null);
    api
      .usoHistorico(escala, ref)
      .then((resposta) => {
        if (!cancelado) setData(resposta);
      })
      .catch((err: unknown) => {
        if (!cancelado) {
          // Descarta o resultado anterior — mesma razão de Entregas.tsx:
          // sem isto, uma falha ao trocar de escala ou navegar deixaria os
          // controles no valor novo mas os números no período antigo.
          setData(null);
          setError(err instanceof ApiError ? err.userMessage : 'Erro ao carregar o tempo de uso.');
        }
      })
      .finally(() => {
        if (!cancelado) setBusy(false);
      });
    return () => {
      cancelado = true;
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
  useEffect(() => {
    if (escala !== 'mes') {
      setAnual(null);
      setAnualError(null);
      return;
    }
    let cancelado = false;
    setAnualError(null);
    const ano = Number(ref.slice(0, 4));
    api
      .usoAnual(ano)
      .then((resposta) => {
        if (!cancelado) setAnual(resposta);
      })
      .catch(() => {
        if (!cancelado) {
          setAnual(null);
          setAnualError('Não foi possível carregar o gráfico do ano.');
        }
      });
    return () => {
      cancelado = true;
    };
  }, [escala, ref, tentativaAnual]);

  const semanas = data ? agruparEmSemanas(data.dias) : [];
  const maxDia = data ? Math.max(1, ...data.dias.map((d) => d.aberto_s)) : 1;
  const maxMesDoAno = anual ? Math.max(1, ...anual.meses.map((m) => m.aberto_s)) : 1;
  const maxRota =
    data && data.rotas.length > 0 ? Math.max(1, ...data.rotas.map((r) => r.aberto_s)) : 1;
  const ociosoS = data ? Math.max(0, data.total_aberto_s - data.total_ativo_s) : 0;
  const proximaEhFutura = janelaSeguinteEhFutura(escala, ref);
  const mesDoRef = ref.slice(0, 7);

  function navegar(direcao: DirecaoJanela): void {
    setRef((atual) => moverJanela(escala, atual, direcao));
  }

  return (
    <div className="samid-stack">
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
            <div className="uso-total mono" data-testid="uso-total">
              {formatarDuracao(data.total_aberto_s)}
            </div>

            <div className="uso-resumo">
              <div className="uso-resumo-item">
                <div className="samid-eyebrow">Aberto</div>
                <div className="mono uso-resumo-val" data-testid="uso-aberto">
                  {formatarDuracao(data.total_aberto_s)}
                </div>
              </div>
              <div className="uso-resumo-item">
                <div className="samid-eyebrow">Ativo</div>
                <div className="mono uso-resumo-val" data-testid="uso-ativo">
                  {formatarDuracao(data.total_ativo_s)}
                </div>
              </div>
              <div className="uso-resumo-item">
                <div className="samid-eyebrow">Ocioso</div>
                <div className="mono uso-resumo-val" data-testid="uso-ocioso">
                  {formatarDuracao(ociosoS)}
                </div>
              </div>
            </div>

            <div className="uso-grafico">
              <div className="uso-grafico-nav">
                <button
                  type="button"
                  className="uso-nav-btn"
                  aria-label="Período anterior"
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
                    {anual.meses.map((m) => (
                      <div
                        key={m.mes}
                        className="uso-ano-col"
                        title={`${MESES_ABREV[Number(m.mes.slice(5, 7)) - 1]} — ${formatarDuracao(m.aberto_s)}`}
                      >
                        <div className="uso-ano-barra-track">
                          <div
                            className={`uso-ano-barra${m.mes === mesDoRef ? ' uso-barra-destaque' : ''}${
                              m.aberto_s === 0 ? ' uso-barra-vestigial' : ''
                            }`}
                            style={{
                              height:
                                m.aberto_s === 0 ? '6%' : `${Math.max(4, (m.aberto_s / maxMesDoAno) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="uso-ano-mes-lbl">
                          {MESES_ABREV[Number(m.mes.slice(5, 7)) - 1]}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="samid-muted">Carregando gráfico…</p>
                )
              ) : (
                <div className="uso-semanas" data-testid="uso-semanas">
                  <div className="uso-dias-letras" aria-hidden>
                    {LETRAS_DIA_SEMANA.map((letra, i) => (
                      <span key={i} className="uso-dia-letra">
                        {letra}
                      </span>
                    ))}
                  </div>
                  {semanas.map((semana, i) => {
                    const diasReais = semana.filter((d): d is UsoDia => d !== null);
                    const somaSemana = diasReais.reduce((soma, d) => soma + d.aberto_s, 0);
                    return (
                      <div key={i} className="uso-semana-bloco">
                        <div className="uso-semana">
                          {semana.map((dia, j) =>
                            dia ? (
                              <div
                                key={j}
                                className={`uso-barra-col${estaNoPeriodo(dia, data) ? ' uso-barra-col-destaque' : ''}`}
                                title={`${formatarDataCurta(dia.dia)} — ${formatarDuracao(dia.aberto_s)}`}
                              >
                                <div
                                  className={`uso-barra${estaNoPeriodo(dia, data) ? ' uso-barra-destaque' : ''}${
                                    dia.aberto_s === 0 ? ' uso-barra-vestigial' : ''
                                  }`}
                                  style={{
                                    height:
                                      dia.aberto_s === 0
                                        ? '6%'
                                        : `${Math.max(4, (dia.aberto_s / maxDia) * 100)}%`,
                                  }}
                                />
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
                            <span className="mono uso-semana-total">{formatarDuracao(somaSemana)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      <section className="samid-card">
        <div className="samid-eyebrow">Por tela</div>
        {data && data.rotas.length === 0 && (
          <p className="samid-muted">sem uso registrado no período</p>
        )}
        {data && data.rotas.length > 0 && (
          <div className="uso-rotas">
            {data.rotas.map((r) => {
              const pct = (r.aberto_s / maxRota) * 100;
              const nome = ROUTE_TITLES[r.rota]?.title ?? r.rota;
              return (
                <div key={r.rota} className="uso-rota-row">
                  <div className="uso-rota-nome">{nome}</div>
                  <div className="uso-rota-track">
                    <div className="uso-rota-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="mono uso-rota-tempo">{formatarDuracao(r.aberto_s)}</div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
