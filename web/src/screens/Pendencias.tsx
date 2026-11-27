import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError, api } from '../api/client';
import { DimTag } from '../components/DimTag';
import { Sev } from '../components/Sev';
import { useDrawer } from '../store/useDrawer';
import { useMCRA } from '../store/useMCRA';
import type { PendenciasPage, Severidade } from '../types';

const SEV_OPTIONS: (Severidade | '')[] = ['', 'ERRO', 'ALERTA', 'INFO'];
const DIM_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'Estrutura', label: 'Estrutura' },
  { value: 'Fechamento', label: 'Fechamento' },
  { value: 'IC_Dominio', label: 'IC / Domínio' },
  { value: 'PCASP_Completude', label: 'PCASP / Completude' },
  { value: 'Temporal', label: 'Temporal' },
];
const PAGE_SIZE = 100;

export function Pendencias() {
  const { siconfi, competencia } = useMCRA();
  const { openRule, openConta } = useDrawer();
  const [searchParams, setSearchParams] = useSearchParams();
  // Dimensão é derivada da URL (fonte de verdade): mantém o filtro em sincronia
  // com deep-link, link da sidebar e back/forward, sem estado local stale.
  const filterDimensao = searchParams.get('dimensao') ?? '';
  const [page, setPage] = useState<PendenciasPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filterSev, setFilterSev] = useState<Severidade | ''>('');
  const [filterRegra, setFilterRegra] = useState('');
  const [filterConta, setFilterConta] = useState('');
  const [currentPage, setCurrentPage] = useState(0);

  useEffect(() => {
    // Troca de competência/ente: zera paginação e limpa a tabela anterior para
    // não exibir pendências de outro mês sob o cabeçalho já trocado. (Mudanças
    // de filtro/página preservam a tabela durante a carga — sem flash.)
    setCurrentPage(0);
    setPage(null);
    setError(null);
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
        dimensao: filterDimensao || undefined,
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
  }, [siconfi, competencia, filterRegra, filterSev, filterConta, filterDimensao, currentPage]);

  // Mudança de dimensão (dropdown, deep-link, back/forward) volta para a 1ª página.
  useEffect(() => {
    setCurrentPage(0);
  }, [filterDimensao]);

  function setDimensaoFilter(value: string) {
    setSearchParams(
      (prev) => {
        if (value) prev.set('dimensao', value);
        else prev.delete('dimensao');
        return prev;
      },
      { replace: true },
    );
  }

  function resetFilters() {
    setFilterSev('');
    setFilterRegra('');
    setFilterConta('');
    setDimensaoFilter('');
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
          <span className="samid-filter-lbl">Dimensão</span>
          <select
            className="samid-select"
            value={filterDimensao}
            onChange={(e) => setDimensaoFilter(e.target.value)}
          >
            {DIM_OPTIONS.map((o) => (
              <option key={o.value || 'todas'} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
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
        </div>

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
