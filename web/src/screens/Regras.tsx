import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';

import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { Sev } from '../components/Sev';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { Heatmap, HeatmapCell, Rule } from '../types';

const HEAT_LEVELS = [
  { max: 0, bg: 'var(--bg-canvas)', color: 'var(--fg-3)' },
  { max: 5, bg: '#FBEFD9', color: 'var(--samid-alerta)' },
  { max: 30, bg: '#F8D49A', color: 'var(--samid-alerta)' },
  { max: 100, bg: '#F0A45D', color: '#fff' },
  { max: Infinity, bg: 'var(--samid-erro)', color: '#fff' },
];

function cellStyle(qtd: number): CSSProperties {
  const lvl = HEAT_LEVELS.find((l) => qtd <= l.max) ?? HEAT_LEVELS[HEAT_LEVELS.length - 1];
  return { background: lvl.bg, color: lvl.color };
}

export function Regras() {
  const { siconfi } = useMCRA();
  const { openRule } = useDrawer();
  const [rules, setRules] = useState<Rule[]>([]);
  const [heat, setHeat] = useState<Heatmap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [heatOpen, setHeatOpen] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .rules()
      .then((r) => !cancelled && setRules(r))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!siconfi) return;
    let cancelled = false;
    api
      .heatmap(siconfi, 6)
      .then((h) => !cancelled && setHeat(h))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [siconfi]);

  const cellMap = useMemo(() => {
    const map = new Map<string, HeatmapCell>();
    if (!heat) return map;
    for (const c of heat.cells) {
      map.set(`${c.regra_id}|${c.competencia}`, c);
    }
    return map;
  }, [heat]);

  const filteredRules = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rules;
    return rules.filter((r) =>
      `${r.rule_id} ${r.rule_name} ${r.dimensao}`.toLowerCase().includes(q),
    );
  }, [rules, query]);

  return (
    <div className="samid-stack">
      {error && <p className="samid-pill samid-pill-erro">{error}</p>}

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Heatmap · regras × competências</div>
            <h2 className="samid-card-title">
              {!siconfi
                ? 'Sem competência ativa'
                : heat
                  ? `${heat.regras.length} regras · ${heat.competencias.length} competência(s)`
                  : 'Carregando heatmap...'}
            </h2>
          </div>
          <div className="samid-heat-legend-row">
            {siconfi && heatOpen && (
            <div className="samid-heat-legend" aria-label="Escala de incidência">
              <span>baixa</span>
              {HEAT_LEVELS.slice(0, -1).map((l) => (
                <span key={String(l.max)} className="samid-heat-cell" style={{ background: l.bg }} />
              ))}
              <span className="samid-heat-cell" style={{ background: HEAT_LEVELS[HEAT_LEVELS.length - 1].bg }} />
              <span>alta</span>
            </div>
            )}
            <button
              type="button"
              className="samid-btn samid-btn-ghost"
              aria-expanded={heatOpen}
              onClick={() => setHeatOpen((v) => !v)}
            >
              {heatOpen ? 'Ocultar' : 'Mostrar'}
            </button>
          </div>
        </div>

        {heatOpen && !siconfi && (
          <p className="samid-muted">
            Processe um CSV MSC para ver o heatmap.{' '}
            <Link to="/inicio" className="samid-btn samid-btn-primary" style={{ display: 'inline-flex' }}>
              Ir para Início
            </Link>
          </p>
        )}

        {heatOpen && heat && heat.competencias.length > 0 && (
          <div className="samid-heatmap" role="table" aria-label="Heatmap regras × competências">
            <div className="samid-heat-head">
              <div />
              {heat.competencias.map((c) => (
                <div key={c} className="samid-heat-month">
                  {c}
                </div>
              ))}
            </div>
            {heat.regras.map((r) => (
              <button
                type="button"
                key={r.id}
                className="samid-heat-row"
                onClick={() => openRule(r.id)}
                style={{ background: 'transparent', border: 'none', textAlign: 'left' }}
              >
                <div className="samid-heat-label">
                  <b>{r.id}</b>
                  <span title={r.nome}>{r.nome}</span>
                </div>
                {heat.competencias.map((c) => {
                  const cell = cellMap.get(`${r.id}|${c}`);
                  const qtd = cell?.pendencias ?? 0;
                  return (
                    <div key={c} className="samid-heat-cell" style={cellStyle(qtd)}>
                      {qtd > 0 ? qtd.toLocaleString('pt-BR') : ''}
                    </div>
                  );
                })}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Catálogo</div>
            <h2 className="samid-card-title">
              {query.trim()
                ? `${filteredRules.length} de ${rules.length} regras`
                : `${rules.length} regras registradas`}
            </h2>
          </div>
          <input
            type="search"
            className="samid-rules-search"
            placeholder="Buscar por regra, nome ou dimensão…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Buscar regras"
          />
        </div>

        <div className="samid-table-scroll">
        <table className="samid-table samid-table-dense">
          <thead>
            <tr>
              <th>Regra</th>
              <th>Nome</th>
              <th>Dimensão</th>
              <th>Pontua?</th>
              <th>Severidade · última comp.</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filteredRules.map((r) => {
              const lastComp = heat?.competencias[heat.competencias.length - 1];
              const lastCell = lastComp ? cellMap.get(`${r.rule_id}|${lastComp}`) : undefined;
              return (
                <tr key={r.rule_id} onClick={() => openRule(r.rule_id)}>
                  <td className="mono" style={{ fontWeight: 600 }}>
                    {r.rule_id}
                  </td>
                  <td>{r.rule_name}</td>
                  <td>
                    <DimTag name={r.dimensao} />
                  </td>
                  <td>
                    {r.is_scoring ? (
                      <span className="samid-chip samid-chip-ok">SIM</span>
                    ) : (
                      <span className="samid-chip">INFO</span>
                    )}
                  </td>
                  <td>
                    {lastCell?.severidade_max ? (
                      <Sev level={lastCell.severidade_max} />
                    ) : (
                      <span className="samid-muted">—</span>
                    )}
                  </td>
                  <td className="mono samid-muted">
                    {lastCell ? lastCell.pendencias.toLocaleString('pt-BR') : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </section>
    </div>
  );
}
