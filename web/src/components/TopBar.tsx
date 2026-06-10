import { useEffect, useRef, useState } from 'react';

import { useLocation, useNavigate } from 'react-router-dom';

import { ApiError, api } from '../api/client';
import { authStore } from '../store/auth';
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
  const [exportError, setExportError] = useState<string | null>(null);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const user = authStore.getUser();

  useEffect(() => () => {
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
  }, []);

  function triggerExport(type: 'excel' | 'pdf') {
    if (!siconfi || !competencia || exportBusy) return;
    setExportBusy(type);
    setExportError(null);
    const call = type === 'excel'
      ? api.exportExcel(siconfi, competencia)
      : api.exportPdf(siconfi, competencia);
    call
      .catch((err: unknown) => {
        const msg = err instanceof ApiError ? err.userMessage : 'Erro ao exportar. Tente novamente.';
        setExportError(msg);
        if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
        errorTimerRef.current = setTimeout(() => setExportError(null), 6000);
      })
      .finally(() => setExportBusy(null));
  }

  function handleLogout() {
    authStore.clearToken();
    void navigate('/login', { replace: true });
  }

  return (
    <header className="samid-topbar">
      <div>
        <div className="samid-breadcrumb">{breadcrumb}</div>
        <h1 className="samid-topbar-title">{title}</h1>
      </div>
      <div className="samid-topbar-actions">
        {exportError && (
          <span className="samid-topbar-export-error" role="alert">
            {exportError}
          </span>
        )}
        <div className="samid-competencia">
          <div className="samid-competencia-lbl">
            {siconfi ? `ENTE ${siconfi}` : 'COMPETÊNCIA'}
          </div>
          <div className="samid-competencia-val">{competencia ?? '—'}</div>
        </div>
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
        <div className="samid-topbar-user">
          <span className="samid-topbar-username">{user ?? 'Usuário'}</span>
          <button
            type="button"
            className="samid-btn samid-btn-ghost"
            onClick={handleLogout}
          >
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
