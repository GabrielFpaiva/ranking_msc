// Tela "Meu tempo de uso" — período selecionável (dia/semana/mês), gráfico
// diário do mês corrente e detalhamento por tela.
//
// Consome GET /api/uso/historico?escala&ref (ver app/api/routes/uso.py). Uma
// assimetria é intencional e documentada lá: quando o período de `escala`
// cruza a virada do mês, `total_aberto_s`/`total_ativo_s`/`rotas` incluem os
// dois lados da fronteira, mas `dias` (o gráfico) cobre só o mês de `ref`. Não
// "corrigir" isso aqui — o gráfico é visão de mês, os totais são visão de
// período.

import { useEffect, useState } from 'react';

import { ApiError, api } from '../api/client';
import { ROUTE_TITLES } from '../components/TopBar';
import { agruparEmSemanas, formatarDuracao, hojeISO, parseDataLocal } from '../format';
import type { EscalaUso, UsoHistorico } from '../types';

const ESCALAS: { valor: EscalaUso; rotulo: string }[] = [
  { valor: 'dia', rotulo: 'Dia' },
  { valor: 'semana', rotulo: 'Semana' },
  { valor: 'mes', rotulo: 'Mês' },
];

// Segunda a domingo — mesma ordem de `agruparEmSemanas`. "S T Q Q S S D"
// repete letra de propósito (Segunda/Sexta/Sábado, Terça, Quinta todas têm
// iniciais compartilhadas em português) — é o rótulo de calendário usual.
const LETRAS_DIA_SEMANA = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];

/** Formata uma data "YYYY-MM-DD" como "DD/MM" por fatiamento de string — sem
 * passar por `Date`, não há risco de deslocar o dia por fuso (ver
 * `parseDataLocal` em `format.ts` para o caminho que precisa de `Date`). */
function formatarDataCurta(iso: string): string {
  const [, mes, dia] = iso.split('-');
  return `${dia}/${mes}`;
}

/** "Setembro de 2026" a partir de uma data "YYYY-MM-DD" do próprio mês. */
function formatarMesAno(iso: string): string {
  const nome = parseDataLocal(iso).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  return nome.charAt(0).toUpperCase() + nome.slice(1);
}

export function MeuTempo() {
  const [escala, setEscala] = useState<EscalaUso>('semana');
  const [ref] = useState<string>(() => hojeISO());
  const [data, setData] = useState<UsoHistorico | null>(null);
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
          // sem isto, uma falha ao trocar de escala deixaria os chips na
          // escala nova mas os números na escala antiga.
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

  const semanas = data ? agruparEmSemanas(data.dias) : [];
  const maxDia = data ? Math.max(1, ...data.dias.map((d) => d.aberto_s)) : 1;
  const maxRota =
    data && data.rotas.length > 0 ? Math.max(1, ...data.rotas.map((r) => r.aberto_s)) : 1;
  const ociosoS = data ? Math.max(0, data.total_aberto_s - data.total_ativo_s) : 0;
  const nomeMes = data && data.dias.length > 0 ? formatarMesAno(data.dias[0].dia) : '';

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
              <div className="samid-eyebrow" style={{ marginTop: 24 }}>
                {nomeMes}
              </div>
              <div className="uso-semanas" data-testid="uso-semanas">
                <div className="uso-dias-letras" aria-hidden>
                  {LETRAS_DIA_SEMANA.map((letra, i) => (
                    <span key={i} className="uso-dia-letra">
                      {letra}
                    </span>
                  ))}
                </div>
                {semanas.map((semana, i) => (
                  <div key={i} className="uso-semana">
                    {semana.map((dia, j) =>
                      dia ? (
                        <div
                          key={j}
                          className="uso-barra-col"
                          title={`${formatarDataCurta(dia.dia)} — ${formatarDuracao(dia.aberto_s)}`}
                        >
                          <div
                            className={`uso-barra${dia.aberto_s === 0 ? ' uso-barra-vestigial' : ''}`}
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
                ))}
              </div>
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
