import { useLocation } from 'react-router-dom';

import { useMCRA } from '../store/mcra';

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
  '/ranking': { breadcrumb: 'Visões', title: 'Ranking Regional' },
};

export function TopBar() {
  const { pathname } = useLocation();
  const { competencia, siconfi } = useMCRA();
  const hasSelection = Boolean(siconfi && competencia);
  const { breadcrumb, title } = ROUTE_TITLES[pathname] ?? {
    breadcrumb: 'MCRA',
    title: 'PMJP',
  };

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
        <a
          className="samid-btn samid-btn-ghost"
          href={
            hasSelection
              ? `/api/exports/excel?siconfi=${encodeURIComponent(siconfi!)}&competencia=${encodeURIComponent(competencia!)}`
              : undefined
          }
          aria-disabled={!hasSelection}
          onClick={(event) => {
            if (!hasSelection) event.preventDefault();
          }}
        >
          Excel
        </a>
        <a
          className="samid-btn samid-btn-gold"
          href={
            hasSelection
              ? `/api/exports/pdf?siconfi=${encodeURIComponent(siconfi!)}&competencia=${encodeURIComponent(competencia!)}`
              : undefined
          }
          aria-disabled={!hasSelection}
          onClick={(event) => {
            if (!hasSelection) event.preventDefault();
          }}
        >
          Exportar PDF
        </a>
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
