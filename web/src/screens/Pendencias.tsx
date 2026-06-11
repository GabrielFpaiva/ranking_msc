import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError, api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { Sev } from '../components/Sev';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { PendenciasPage, Severidade } from '../types';

const SEV_OPTIONS: (Severidade | '')[] = ['', 'ERRO', 'ALERTA', 'INFO'];
const PAGE_SIZE = 100;

export function Pendencias() {
  const { siconfi, competencia } = useMCRA();
  const { openRule, openConta } = useDrawer();
  const [page, setPage] = useState<PendenciasPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [filterSev, setFilterSev] = useState<Severidade | ''>('');
  const [filterRegra, setFilterRegra] = useState('');
  const [filterConta, setFilterConta] = useState('');
  const [currentPage, setCurrentPage] = useState(0);

  useEffect(() => {
    setCurrentPage(0);
  }, [siconfi, competencia]);

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
        offset: currentPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      .then((p) => {
        if (!cancelled) setPage(p);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.userMessage : 'Erro ao carregar pendências.');
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia, filterRegra, filterSev, filterConta, currentPage]);

  function resetFilters() {
    setFilterSev('');
    setFilterRegra('');
    setFilterConta('');
    setCurrentPage(0);
  }

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setCurrentPage(0);
    };
  }

  if (!siconfi || !competencia) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Pendências</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem competência ativa
        </h2>
        <p className="samid-muted">
          Processe um CSV MSC para popular esta tela.
        </p>
        <Link to="/inicio" className="samid-btn samid-btn-primary" style={{ marginTop: 12, display: 'inline-flex' }}>
          Ir para Início
        </Link>
      </div>
    );
  }

  const total = page?.total ?? 0;
  const rangeStart = total === 0 ? 0 : currentPage * PAGE_SIZE + 1;
  const rangeEnd = Math.min(rangeStart + PAGE_SIZE - 1, total);
  const hasPrev = currentPage > 0;
  const hasNext = rangeEnd < total;

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
                onChange={() => handleFilterChange(setFilterSev)(opt)}
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
            onChange={(e) => handleFilterChange(setFilterRegra)(e.target.value.trim().toUpperCase())}
            placeholder="R___"
          />
        </div>

        <div className="samid-filter-group">
          <span className="samid-filter-lbl">Conta (prefixo)</span>
          <input
            className="samid-input"
            value={filterConta}
            onChange={(e) => handleFilterChange(setFilterConta)(e.target.value.trim())}
            placeholder="111110"
          />
        </div>

        <button
          type="button"
          className="samid-btn samid-btn-ghost samid-btn-block"
          onClick={resetFilters}
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
                  ? `${total.toLocaleString('pt-BR')} pendência(s)`
                  : 'Sem dados'}
            </h2>
          </div>
          <button
            type="button"
            className="samid-btn samid-btn-ghost"
            disabled={exportBusy || !page}
            onClick={() => {
              setExportError(null);
              setExportBusy(true);
              api
                .exportExcel(siconfi, competencia)
                .catch((err: unknown) => {
                  const msg = err instanceof ApiError
                    ? err.status === 404
                      ? 'Relatório não encontrado. Execute o pipeline primeiro.'
                      : err.userMessage
                    : 'Erro ao exportar.';
                  setExportError(msg);
                })
                .finally(() => setExportBusy(false));
            }}
          >
            {exportBusy ? 'Gerando...' : 'Exportar Excel'}
          </button>
        </div>

        {exportError && (
          <p className="samid-pill samid-pill-erro" role="alert">
            {exportError}
          </p>
        )}

        {error && (
          <p className="samid-pill samid-pill-erro" role="alert">
            {error}
          </p>
        )}

        {page && total > 0 && (
          <p className="samid-muted" style={{ fontSize: 12, margin: '0 0 8px' }}>
            Mostrando {rangeStart.toLocaleString('pt-BR')}–{rangeEnd.toLocaleString('pt-BR')} de {total.toLocaleString('pt-BR')} pendências
          </p>
        )}

        {page && page.items.length > 0 ? (
          <>
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
                      <td style={{ cursor: 'pointer' }} onClick={() => openRule(p.regra_id)}>
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
                      <td
                        className="mono"
                        style={{ cursor: p.conta_contabil ? 'pointer' : 'default' }}
                        onClick={() => p.conta_contabil && openConta(p.conta_contabil)}
                      >
                        {p.conta_contabil}
                      </td>
                      <td>{p.descricao}</td>
                      <td className="mono">{p.valor_esperado ?? '—'}</td>
                      <td className="mono">{p.valor_encontrado ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="samid-pagination">
              <button
                type="button"
                className="samid-btn samid-btn-ghost"
                disabled={!hasPrev || busy}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                ← Anterior
              </button>
              <button
                type="button"
                className="samid-btn samid-btn-ghost"
                disabled={!hasNext || busy}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                Próximo →
              </button>
            </div>
          </>
        ) : page && !busy ? (
          <p className="samid-muted">Nenhuma pendência para os filtros atuais.</p>
        ) : null}
      </section>
    </div>
  );
}
