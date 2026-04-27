import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { Sev } from '../components/Sev';
import { ScoreChart } from '../components/charts/ScoreChart';
import { useDrawer } from '../store/drawer';
import { useMCRA } from '../store/mcra';
import type { Banda, Recommendation, Score, ScoreHistory } from '../types';

const BAND_COLOR: Record<Banda, string> = {
  A: 'var(--samid-band-a)',
  B: 'var(--samid-band-b)',
  C: 'var(--samid-band-c)',
  D: 'var(--samid-band-d)',
  E: 'var(--samid-band-e)',
};

export function Executivo() {
  const { siconfi, competencia } = useMCRA();
  const { openRule } = useDrawer();
  const [score, setScore] = useState<Score | null>(null);
  const [history, setHistory] = useState<ScoreHistory | null>(null);
  const [recos, setRecos] = useState<Recommendation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    Promise.all([
      api.score(siconfi, competencia),
      api.scoreHistory(siconfi, 6),
      api.recommendations(siconfi, competencia).catch(() => ({ items: [] as Recommendation[] })),
    ])
      .then(([s, h, r]) => {
        if (cancelled) return;
        setScore(s);
        setHistory(h);
        setRecos((r as { items: Recommendation[] }).items);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  if (!siconfi || !competencia) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Visão Executiva</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem competência ativa
        </h2>
        <p className="samid-muted">Volte para Início e processe um CSV MSC.</p>
      </div>
    );
  }

  if (error) {
    return <p className="samid-pill samid-pill-erro">{error}</p>;
  }

  if (!score) {
    return <p className="samid-muted">Carregando visão executiva...</p>;
  }

  // Delta é sempre relativo à competência ativa exibida no header — não aos
  // dois pontos mais novos do histórico. Quando o usuário processa/backfilla
  // um mês antigo depois de já existirem snapshots mais novos, "últimos dois"
  // mostraria delta de outra competência, contradizendo o score em tela.
  const prev =
    history?.points
      .filter((p) => p.competencia < competencia)
      .sort((a, b) => a.competencia.localeCompare(b.competencia))
      .at(-1) ?? null;
  const delta = prev ? score.pontuacao - prev.pontuacao : null;

  return (
    <div className="samid-stack">
      <section className="samid-exec-hero">
        <div className="samid-exec-hero-l">
          <div className="samid-eyebrow" style={{ color: 'rgba(255,255,255,.6)' }}>
            {competencia} · ente {siconfi}
          </div>
          <h1 className="samid-exec-title">Conformidade MSC</h1>
          <p className="samid-exec-sub">
            Pontuação consolidada do envio à Matriz de Saldos Contábeis no SICONFI.
          </p>
          <div className="samid-exec-badges">
            <span className="samid-pill samid-pill-info">{score.regras_executadas} regras</span>
            <span className="samid-pill samid-pill-erro">{score.regras_falhas_erro} ERRO</span>
            <span className="samid-pill samid-pill-alerta">{score.regras_falhas_alerta} ALERTA</span>
          </div>
        </div>
        <div className="samid-exec-hero-r">
          <div className="samid-exec-bigscore">
            <div
              className="samid-exec-bigscore-num"
              style={{ color: BAND_COLOR[score.banda] }}
            >
              {score.pontuacao.toFixed(1).replace('.', ',')}
            </div>
            <div className="samid-exec-bigscore-band">BANDA {score.banda} · / 100</div>
            {delta !== null && (
              <div
                className="samid-exec-delta"
                style={{ color: delta >= 0 ? '#6BE097' : '#FFA8A6' }}
              >
                {delta >= 0 ? '▲' : '▼'} {delta.toFixed(2).replace('.', ',')} vs {prev?.competencia}
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="samid-grid-2">
        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Pontos de atenção · ações sugeridas</div>
              <h2 className="samid-card-title">{recos.length} recomendação(ões)</h2>
            </div>
          </div>
          {recos.length === 0 ? (
            <p className="samid-muted">Nada crítico no momento. Mantenha a consistência das próximas competências.</p>
          ) : (
            <div className="samid-exec-actionlist">
              {recos.map((r, i) => (
                <button
                  type="button"
                  key={`${r.titulo}-${i}`}
                  className="samid-exec-action"
                  onClick={() => r.referencia && /^R\d+/.test(r.referencia) && openRule(r.referencia)}
                  style={{ background: 'transparent', border: 'none', textAlign: 'left', cursor: r.referencia?.startsWith('R') ? 'pointer' : 'default' }}
                >
                  <div className="samid-exec-action-num">{i + 1}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                      <strong>{r.titulo}</strong>
                      <Sev level={r.severidade} />
                    </div>
                    <div className="samid-muted" style={{ fontSize: 13 }}>
                      {r.descricao}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Evolução · 6 meses</div>
              <h2 className="samid-card-title">Linha do tempo</h2>
            </div>
          </div>
          {history && history.points.length > 0 ? (
            <ScoreChart points={history.points} />
          ) : (
            <p className="samid-muted">Sem histórico registrado para este ente.</p>
          )}
        </section>
      </div>

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Conformidade por dimensão</div>
            <h2 className="samid-card-title">{Object.keys(score.dimensions).length} dimensões ativas</h2>
          </div>
        </div>
        <div className="samid-score-breakdown">
          {Object.values(score.dimensions).map((dim) => (
            <div key={dim.dimension} className="samid-score-row">
              <div className="samid-score-dim">{dim.dimension}</div>
              <div className="samid-score-bar">
                <div style={{ width: `${(dim.score * 100).toFixed(1)}%` }} />
              </div>
              <div className="samid-score-pct">{(dim.score * 100).toFixed(0)}%</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
