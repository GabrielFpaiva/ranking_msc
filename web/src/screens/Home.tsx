import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { ScoreBadge } from '../components/ScoreBadge';
import { Sev } from '../components/Sev';
import { UploadDrop } from '../components/UploadDrop';
import { ScoreChart } from '../components/charts/ScoreChart';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { RunSummary, ScoreHistory } from '../types';

export function Home() {
  const { siconfi, competencia, lastRun, setLastRun } = useMCRA();
  const { openRule } = useDrawer();
  const [history, setHistory] = useState<ScoreHistory | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [run, setRun] = useState<RunSummary | null>(lastRun);

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
      .catch((err: Error) => {
        if (!cancelled) setHistoryError(err.message);
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
          {run && (
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
                <a
                  href={`/api/exports/excel?siconfi=${encodeURIComponent(run.siconfi)}&competencia=${encodeURIComponent(run.competencia)}`}
                  className="samid-btn samid-btn-primary"
                  download
                  id="btn-export-excel"
                >
                  ⬇ Exportar Excel
                </a>
                <a
                  href={`/api/exports/pdf?siconfi=${encodeURIComponent(run.siconfi)}&competencia=${encodeURIComponent(run.competencia)}`}
                  className="samid-btn samid-btn-gold"
                  id="btn-export-pdf"
                >
                  📄 Exportar PDF
                </a>
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
          {run ? (
            <>
              <ScoreBadge pontuacao={run.score.pontuacao} banda={run.score.banda} size="lg" />
              <div className="samid-score-breakdown">
                {Object.entries(run.score.dimensions).map(([key, dim]) => (
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
              {run ? `${run.total_pendencias.toLocaleString('pt-BR')} pendência(s) na competência` : 'Aguardando execução'}
            </h2>
          </div>
        </div>
        {run && run.top_regras.length > 0 ? (
          <div className="samid-bars">
            {run.top_regras.map((r) => {
              const max = run.top_regras[0].pendencias || 1;
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
        ) : run ? (
          <p className="samid-muted">Sem regras violadas — parabéns.</p>
        ) : (
          <p className="samid-muted">A lista aparece após a primeira execução.</p>
        )}
      </section>
    </div>
  );
}
