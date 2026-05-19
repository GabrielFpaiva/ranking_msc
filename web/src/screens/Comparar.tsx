import { useEffect, useMemo, useState } from 'react';

import { api } from '../api/client';
import { useMCRA } from '../store/useMCRA';
import type { Compare, Competencia } from '../types';

export function Comparar() {
  const { siconfi, competencia } = useMCRA();
  const [comps, setComps] = useState<Competencia[]>([]);
  const [a, setA] = useState<string>('');
  const [b, setB] = useState<string>('');
  const [diff, setDiff] = useState<Compare | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siconfi) return;
    let cancelled = false;
    setError(null);
    api
      .competencias(siconfi)
      .then((items) => {
        if (cancelled) return;
        setComps(items);
        if (items.length >= 2) {
          setB(items[0].competencia);
          setA(items[1].competencia);
        } else if (items.length === 1) {
          setA(items[0].competencia);
          setB(competencia ?? items[0].competencia);
        }
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!siconfi || !a || !b || a === b) {
      setDiff(null);
      return;
    }
    api
      .compare(siconfi, a, b)
      .then((d) => {
        if (cancelled) return;
        setDiff(d);
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [siconfi, a, b]);

  const optionList = useMemo(() => comps.map((c) => c.competencia), [comps]);

  if (!siconfi) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Comparar</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem ente ativo
        </h2>
        <p className="samid-muted">Volte para Início e processe um CSV MSC.</p>
      </div>
    );
  }

  return (
    <div className="samid-stack">
      <section className="samid-card">
        <div className="samid-compare-head">
          <div>
            <div className="samid-eyebrow">Diff de score · {siconfi}</div>
            <h2 className="samid-card-title">Comparar competências</h2>
          </div>
          <div className="samid-compare-pickers">
            <div>
              <div className="samid-eyebrow">A</div>
              <select className="samid-select" value={a} onChange={(e) => setA(e.target.value)}>
                {optionList.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <span style={{ fontSize: 24 }}>→</span>
            <div>
              <div className="samid-eyebrow">B</div>
              <select className="samid-select" value={b} onChange={(e) => setB(e.target.value)}>
                {optionList.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      {error && <p className="samid-pill samid-pill-erro">{error}</p>}

      {a && b && a === b && (
        <p className="samid-muted">Selecione duas competências diferentes para comparar.</p>
      )}

      {diff && (
        <>
          <div className="samid-grid-2">
            <CompareCard side="A" data={diff.a} />
            <CompareCard side="B" data={diff.b} />
          </div>

          <section className="samid-card">
            <div className="samid-card-head">
              <div>
                <div className="samid-eyebrow">Delta consolidado</div>
                <h2 className="samid-card-title">
                  {diff.delta_score >= 0 ? '+' : ''}
                  {diff.delta_score.toFixed(2).replace('.', ',')} pontos · {diff.delta_pendencias >= 0 ? '+' : ''}
                  {diff.delta_pendencias} pendências
                </h2>
              </div>
              <span
                className={`samid-compare-delta ${diff.delta_score >= 0 ? 'down' : 'up'}`}
              >
                {diff.delta_score >= 0 ? '▲ melhora' : '▼ piora'}
              </span>
            </div>

            <div className="samid-compare-dims">
              {diff.dimensions.map((d) => (
                <div key={d.dimension} className="samid-compare-dimrow">
                  <div className="samid-compare-dimname">{d.dimension}</div>
                  <div className="samid-compare-barpair">
                    <DimSide pct={d.score_a * 100} side="left" />
                    <DimSide pct={d.score_b * 100} side="right" />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function CompareCard({ side, data }: { side: 'A' | 'B'; data: Compare['a'] }) {
  return (
    <div className="samid-compare-card">
      <div className="samid-eyebrow">Lado {side} · {data.competencia}</div>
      <div className="samid-compare-mv">{data.pontuacao.toFixed(1).replace('.', ',')}</div>
      <div className="samid-compare-ml">
        Banda {data.banda} · {data.total_pendencias.toLocaleString('pt-BR')} pendência(s)
      </div>
    </div>
  );
}

function DimSide({ pct, side }: { pct: number; side: 'left' | 'right' }) {
  return (
    <div className="samid-compare-side">
      {side === 'left' && <span className="samid-compare-barlbl">{pct.toFixed(0)}%</span>}
      <div className={`samid-compare-bar${side === 'left' ? ' samid-compare-bar-left' : ''}`}>
        <div style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: 'var(--samid-midnight)' }} />
      </div>
      {side === 'right' && <span className="samid-compare-barlbl">{pct.toFixed(0)}%</span>}
    </div>
  );
}
