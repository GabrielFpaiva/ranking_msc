import { useState } from 'react';

import { useLocation } from 'react-router-dom';

import { api } from '../api/client';
import { useMCRA } from '../store/useMCRA';

const ROUTE_TITLES: Record<string, { breadcrumb: string; title: string }> = {
  '/inicio': { breadcrumb: 'Análise', title: 'Início' },
  '/execucao': { breadcrumb: 'Análise', title: 'Execução' },
  '/regras': { breadcrumb: 'Análise', title: 'Regras' },
  '/pendencias': { breadcrumb: 'Análise', title: 'Pendências' },
  '/caixa': { breadcrumb: 'Contas', title: 'Caixa' },
  '/passivos': { breadcrumb: 'Contas', title: 'Passivos' },
  '/superavit': { breadcrumb: 'Contas', title: 'Superávit' },
  '/executivo': { breadcrumb: 'Visões', title: 'Visão Executiva' },
  '/comparar': { breadcrumb: 'Visões', title: 'Comparar Competências' },
};

export function TopBar() {
  const { pathname } = useLocation();
  const { competencia, siconfi } = useMCRA();
  const hasSelection = Boolean(siconfi && competencia);
  const { breadcrumb, title } = ROUTE_TITLES[pathname] ?? {
    breadcrumb: 'MCRA',
    title: 'PMJP',
  };
  const [exportBusy, setExportBusy] = useState<'excel' | 'pdf' | null>(null);

  function triggerExport(type: 'excel' | 'pdf') {
    if (!siconfi || !competencia || exportBusy) return;
    setExportBusy(type);
    const call = type === 'excel'
      ? api.exportExcel(siconfi, competencia)
      : api.exportPdf(siconfi, competencia);
    call.catch(() => undefined).finally(() => setExportBusy(null));
  }

  return (
    <header className="samid-topbar">
      <div>
        <div className="samid-breadcrumb">{breadcrumb}</div>
        <h1 className="samid-topbar-title">{title}</h1>
      </div>
      <div className="samid-topbar-actions">
        <div className="samid-competencia">
          <div className="samid-competencia-lbl">
            {siconfi ? `ENTE ${siconfi}` : 'COMPETÊNCIA'}
          </div>
          <div className="samid-competencia-val">{competencia ?? '—'}</div>
        </div>
        <button
          className="samid-btn samid-btn-ghost"
          type="button"
          disabled
          title="Reprocessar — a ser implementado"
        >
          Reprocessar
        </button>
        <button
          type="button"
          className="samid-btn samid-btn-ghost"
          disabled={!hasSelection || exportBusy !== null}
          onClick={() => triggerExport('excel')}
        >
          {exportBusy === 'excel' ? 'Gerando…' : 'Excel'}
        </button>
        <button
          type="button"
          className="samid-btn samid-btn-gold"
          disabled={!hasSelection || exportBusy !== null}
          onClick={() => triggerExport('pdf')}
        >
          {exportBusy === 'pdf' ? 'Gerando…' : 'Exportar PDF'}
        </button>
        <button
          className="samid-icon-btn"
          type="button"
          aria-label="Notificações"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>
      </div>
    </header>
  );
}
