import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { Sev } from '../components/Sev';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { PendenciasPage, Severidade } from '../types';

const SEV_OPTIONS: (Severidade | '')[] = ['', 'ERRO', 'ALERTA', 'INFO'];

export function Pendencias() {
  const { siconfi, competencia } = useMCRA();
  const { openRule, openConta } = useDrawer();
  const [page, setPage] = useState<PendenciasPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filterSev, setFilterSev] = useState<Severidade | ''>('');
  const [filterRegra, setFilterRegra] = useState('');
  const [filterConta, setFilterConta] = useState('');

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    api
      .pendencias({
        siconfi,
        competencia,
        regra_id: filterRegra || undefined,
        severidade: filterSev || undefined,
        conta_prefix: filterConta || undefined,
        limit: 200,
      })
      .then((p) => {
        if (!cancelled) setPage(p);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia, filterRegra, filterSev, filterConta]);

  if (!siconfi || !competencia) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Pendências</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem competência ativa
        </h2>
        <p className="samid-muted">
          Volte para Início e processe um CSV MSC para popular esta tela.
        </p>
      </div>
    );
  }

  return (
    <div className="samid-pend-layout">
      <aside className="samid-filter-rail">
        <div className="samid-filter-head">
          <span className="samid-eyebrow">Filtros</span>
        </div>

        <div className="samid-filter-group">
          <span className="samid-filter-lbl">Severidade</span>
          {SEV_OPTIONS.map((opt) => (
            <label key={opt || 'todas'} className="samid-check">
              <input
                type="radio"
                name="sev"
                checked={filterSev === opt}
                onChange={() => setFilterSev(opt)}
              />
              {opt || 'Todas'}
            </label>
          ))}
        </div>

        <div className="samid-filter-group">
          <span className="samid-filter-lbl">Regra (ex: R054)</span>
          <input
            className="samid-input"
            value={filterRegra}
            onChange={(e) => setFilterRegra(e.target.value.trim().toUpperCase())}
            placeholder="R___"
          />
        </div>

        <div className="samid-filter-group">
          <span className="samid-filter-lbl">Conta (prefixo)</span>
          <input
            className="samid-input"
            value={filterConta}
            onChange={(e) => setFilterConta(e.target.value.trim())}
            placeholder="111110"
          />
        </div>

        <button
          type="button"
          className="samid-btn samid-btn-ghost samid-btn-block"
          onClick={() => {
            setFilterSev('');
            setFilterRegra('');
            setFilterConta('');
          }}
        >
          Limpar filtros
        </button>
      </aside>

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">
              {competencia} · {siconfi}
            </div>
            <h2 className="samid-card-title">
              {busy
                ? 'Carregando...'
                : page
                  ? `${page.total.toLocaleString('pt-BR')} pendência(s)`
                  : 'Sem dados'}
            </h2>
          </div>
        </div>

        {error && (
          <p className="samid-pill samid-pill-erro" role="alert">
            {error}
          </p>
        )}

        {page && page.items.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table className="samid-table samid-table-dense">
              <thead>
                <tr>
                  <th>Regra</th>
                  <th>Severidade</th>
                  <th>Conta</th>
                  <th>Descrição</th>
                  <th>Esperado</th>
                  <th>Encontrado</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((p, i) => (
                  <tr key={`${p.regra_id}-${p.conta_contabil}-${i}`}>
                    <td onClick={() => openRule(p.regra_id)}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span className="mono" style={{ fontWeight: 600 }}>
                          {p.regra_id}
                        </span>
                        <DimTag name={p.dimensao} />
                      </div>
                    </td>
                    <td>
                      <Sev level={p.severidade} />
                    </td>
                    <td className="mono" onClick={() => p.conta_contabil && openConta(p.conta_contabil)}>
                      {p.conta_contabil}
                    </td>
                    <td>{p.descricao}</td>
                    <td className="mono">{p.valor_esperado ?? '—'}</td>
                    <td className="mono">{p.valor_encontrado ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {page.total > page.items.length && (
              <p className="samid-muted" style={{ marginTop: 12 }}>
                Mostrando {page.items.length} de {page.total.toLocaleString('pt-BR')}. Refine os
                filtros para reduzir o conjunto.
              </p>
            )}
          </div>
        ) : page && !busy ? (
          <p className="samid-muted">Nenhuma pendência para os filtros atuais.</p>
        ) : null}
      </section>
    </div>
  );
}
