import { useEffect, useState } from 'react';

import { ApiError, api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { ScoreBadge } from '../components/ScoreBadge';
import { Sev } from '../components/Sev';
import { UploadDrop } from '../components/UploadDrop';
import { ScoreChart } from '../components/charts/ScoreChart';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { RunSummary, ScoreHistory, Summary } from '../types';

export function Home() {
  const { siconfi, competencia, lastRun, setLastRun } = useMCRA();
  const { openRule } = useDrawer();
  const [history, setHistory] = useState<ScoreHistory | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [run, setRun] = useState<RunSummary | null>(lastRun);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [exportBusy, setExportBusy] = useState<'excel' | 'pdf' | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Score, contagem e top-regras refletem a competência ATIVA (dropdown da
  // TopBar), não o último upload — buscamos um resumo por competência.
  useEffect(() => {
    if (!siconfi || !competencia) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    api
      .summary(siconfi, competencia)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  useEffect(() => {
    if (!siconfi) return;
    let cancelled = false;
    api
      .scoreHistory(siconfi, 6)
      .then((data) => {
        if (!cancelled) {
          setHistory(data);
          setHistoryError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const msg = err instanceof ApiError ? err.userMessage : 'Erro ao carregar histórico.';
          setHistoryError(msg);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, run?.execucao_id]);

  async function handleFile(file: File): Promise<void> {
    const summary = await api.run(file);
    setRun(summary);
    setLastRun(summary);
  }

  return (
    <div className="samid-stack">
      <div className="samid-grid-cols-3">
        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Importar MSC</div>
              <h2 className="samid-card-title">Nova execução</h2>
            </div>
          </div>
          <UploadDrop onFile={handleFile} />
          {run && run.competencia === competencia && (
            <>
              <div className="samid-kv" style={{ marginTop: 16 }}>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <Sev level={run.status === 'OK' ? 'INFO' : run.status === 'PARCIAL' ? 'ALERTA' : 'ERRO'} />
                  </dd>
                </div>
                <div>
                  <dt>Competência</dt>
                  <dd className="mono">{run.competencia}</dd>
                </div>
                <div>
                  <dt>Ente</dt>
                  <dd className="mono">{run.siconfi}</dd>
                </div>
                <div>
                  <dt>Pendências</dt>
                  <dd className="mono">{run.total_pendencias.toLocaleString('pt-BR')}</dd>
                </div>
              </div>
              <div className="samid-export-btns">
                {exportError && (
                  <p className="samid-error" role="alert">{exportError}</p>
                )}
                <button
                  type="button"
                  className="samid-btn samid-btn-primary"
                  disabled={exportBusy !== null}
                  id="btn-export-excel"
                  onClick={() => {
                    setExportError(null);
                    setExportBusy('excel');
                    api
                      .exportExcel(run.siconfi, run.competencia)
                      .catch((err: unknown) => {
                  const msg = err instanceof ApiError ? err.userMessage : 'Erro ao exportar.';
                  setExportError(msg);
                })
                      .finally(() => setExportBusy(null));
                  }}
                >
                  {exportBusy === 'excel' ? 'Gerando…' : '⬇ Exportar Excel'}
                </button>
                <button
                  type="button"
                  className="samid-btn samid-btn-gold"
                  disabled={exportBusy !== null}
                  id="btn-export-pdf"
                  onClick={() => {
                    setExportError(null);
                    setExportBusy('pdf');
                    api
                      .exportPdf(run.siconfi, run.competencia)
                      .catch((err: unknown) => {
                  const msg = err instanceof ApiError ? err.userMessage : 'Erro ao exportar.';
                  setExportError(msg);
                })
                      .finally(() => setExportBusy(null));
                  }}
                >
                  {exportBusy === 'pdf' ? 'Gerando…' : '📄 Exportar PDF'}
                </button>
              </div>
            </>
          )}
        </section>

        <section className="samid-card samid-score-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Score de Conformidade</div>
              <h2 className="samid-card-title">{competencia ?? '—'}</h2>
            </div>
          </div>
          {summary ? (
            <>
              <ScoreBadge pontuacao={summary.score.pontuacao} banda={summary.score.banda} size="lg" />
              <div className="samid-score-breakdown">
                {Object.entries(summary.score.dimensions).map(([key, dim]) => (
                  <div key={key} className="samid-score-row">
                    <div className="samid-score-dim">{dim.dimension}</div>
                    <div className="samid-score-bar">
                      <div style={{ width: `${(dim.score * 100).toFixed(1)}%` }} />
                    </div>
                    <div className="samid-score-pct">{(dim.score * 100).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="samid-muted">
              Faça upload de um CSV MSC para calcular o score da competência.
            </p>
          )}
        </section>

        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Evolução · 6 meses</div>
              <h2 className="samid-card-title">Linha do tempo</h2>
            </div>
          </div>
          {historyError ? (
            <p className="samid-muted">Ainda não há histórico para este ente.</p>
          ) : history && history.points.length > 0 ? (
            <ScoreChart points={history.points} />
          ) : (
            <p className="samid-muted">Nenhum período persistido ainda.</p>
          )}
        </section>
      </div>

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Top 8 regras violadas</div>
            <h2 className="samid-card-title">
              {summary ? `${summary.total_pendencias.toLocaleString('pt-BR')} pendência(s) na competência` : 'Aguardando execução'}
            </h2>
          </div>
        </div>
        {summary && summary.top_regras.length > 0 ? (
          <div className="samid-bars">
            {summary.top_regras.map((r) => {
              const max = summary.top_regras[0].pendencias || 1;
              const pct = (r.pendencias / max) * 100;
              const fillClass =
                r.severidade_max === 'ERRO'
                  ? 'samid-bar-erro'
                  : r.severidade_max === 'ALERTA'
                    ? 'samid-bar-alerta'
                    : 'samid-bar-info';
              return (
                <div
                  key={r.regra_id}
                  className="samid-bar-row"
                  role="button"
                  tabIndex={0}
                  onClick={() => openRule(r.regra_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') openRule(r.regra_id);
                  }}
                >
                  <div className="samid-bar-rid">{r.regra_id}</div>
                  <div className="samid-bar-nome">{r.regra_nome}</div>
                  <DimTag name={r.dimensao} />
                  <Sev level={r.severidade_max} />
                  <div className="samid-bar-track">
                    <div className={`samid-bar-fill ${fillClass}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="samid-bar-qty">{r.pendencias.toLocaleString('pt-BR')}</div>
                </div>
              );
            })}
          </div>
        ) : summary ? (
          <p className="samid-muted">Sem regras violadas — parabéns.</p>
        ) : (
          <p className="samid-muted">A lista aparece após a primeira execução.</p>
        )}
      </section>
    </div>
  );
}
