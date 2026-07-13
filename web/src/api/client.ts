// Wrapper fino sobre fetch para o backend FastAPI.
// Em dev usa o proxy do Vite (/api → :8000). Em prod é same-origin.

import { authStore } from '../store/auth';

import type {
  Compare,
  Competencia,
  ContaDetail,
  ContaList,
  Heatmap,
  LogPage,
  PendenciasPage,
  Recommendations,
  Rule,
  RuleDetail,
  RuleHistory,
  RunSummary,
  Score,
  ScoreHistory,
  Summary,
  SuperavitData,
} from '../types';

const BASE = '/api';

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`[${status}] ${detail}`);
    this.status = status;
    this.detail = detail;
  }

  get userMessage(): string {
    switch (this.status) {
      case 401: return 'Sessão expirada. Faça login novamente.';
      case 403: return 'Você não tem permissão para esta ação.';
      case 404: return 'Recurso não encontrado.';
      case 409: return 'Processamento já em andamento para esta competência.';
      case 422: return 'Dados inválidos. Verifique os campos e tente novamente.';
      case 500: return 'Erro interno do servidor. Tente novamente mais tarde.';
      default:  return this.detail || 'Erro inesperado. Tente novamente.';
    }
  }
}

function authHeaders(): HeadersInit {
  const token = authStore.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchAuth(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(input, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers as Record<string, string> | undefined) },
  });
  if (res.status === 401) {
    authStore.clearToken();
    window.location.href = '/login';
  }
  return res;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // body não é JSON; mantém statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiSetupStatus(): Promise<boolean> {
  const res = await fetch(`${BASE}/auth/setup-status`);
  const data = await jsonOrThrow<{ needs_setup: boolean }>(res);
  return data.needs_setup;
}

export async function apiSetup(username: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, body.detail ?? 'Falha ao criar o usuário.');
  }
}

export async function apiLogin(username: string, password: string): Promise<void> {
  const form = new URLSearchParams({ username, password, grant_type: 'password' });
  const res = await fetch(`${BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, body.detail ?? 'Credenciais inválidas');
  }
  const data = (await res.json()) as { access_token: string };
  authStore.setToken(data.access_token);
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  );
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&');
}

function _triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

export const api = {
  health: (): Promise<{ status: string; rules_enabled: string }> =>
    fetch(`${BASE}/health`).then((r) => jsonOrThrow<{ status: string; rules_enabled: string }>(r)),

  competencias: (siconfi?: string): Promise<Competencia[]> =>
    fetchAuth(`${BASE}/competencias${qs({ siconfi })}`).then((r) => jsonOrThrow<Competencia[]>(r)),

  run: (file: File): Promise<RunSummary> => {
    const form = new FormData();
    form.append('file', file);
    return fetchAuth(`${BASE}/run`, { method: 'POST', body: form }).then((r) =>
      jsonOrThrow<RunSummary>(r),
    );
  },

  score: (siconfi: string, competencia: string): Promise<Score> =>
    fetchAuth(`${BASE}/score${qs({ siconfi, competencia })}`).then((r) => jsonOrThrow<Score>(r)),

  summary: (siconfi: string, competencia: string): Promise<Summary> =>
    fetchAuth(`${BASE}/summary${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<Summary>(r),
    ),

  scoreHistory: (siconfi: string, meses = 6): Promise<ScoreHistory> =>
    fetchAuth(`${BASE}/score-history${qs({ siconfi, meses })}`).then((r) =>
      jsonOrThrow<ScoreHistory>(r),
    ),

  pendencias: (params: {
    siconfi: string;
    competencia: string;
    regra_id?: string;
    severidade?: string;
    conta_prefix?: string;
    dimensao?: string;
    offset?: number;
    limit?: number;
  }): Promise<PendenciasPage> =>
    fetchAuth(`${BASE}/pendencias${qs(params)}`).then((r) => jsonOrThrow<PendenciasPage>(r)),

  rules: (): Promise<Rule[]> =>
    fetchAuth(`${BASE}/rules`).then((r) => jsonOrThrow<Rule[]>(r)),

  rule: (ruleId: string): Promise<RuleDetail> =>
    fetchAuth(`${BASE}/rules/${encodeURIComponent(ruleId)}`).then((r) => jsonOrThrow<RuleDetail>(r)),

  heatmap: (siconfi: string, meses = 6): Promise<Heatmap> =>
    fetchAuth(`${BASE}/heatmap${qs({ siconfi, meses })}`).then((r) => jsonOrThrow<Heatmap>(r)),

  ruleHistory: (siconfi: string, ruleId: string, meses = 6): Promise<RuleHistory> =>
    fetchAuth(
      `${BASE}/rule-history/${encodeURIComponent(ruleId)}${qs({ siconfi, meses })}`,
    ).then((r) => jsonOrThrow<RuleHistory>(r)),

  conta: (
    contaContabil: string,
    siconfi: string,
    competencia: string,
  ): Promise<ContaDetail> =>
    fetchAuth(
      `${BASE}/contas/${encodeURIComponent(contaContabil)}${qs({ siconfi, competencia })}`,
    ).then((r) => jsonOrThrow<ContaDetail>(r)),

  caixa: (siconfi: string, competencia: string): Promise<ContaList> =>
    fetchAuth(`${BASE}/caixa${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<ContaList>(r),
    ),

  passivos: (siconfi: string, competencia: string): Promise<ContaList> =>
    fetchAuth(`${BASE}/passivos${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<ContaList>(r),
    ),

  superavit: (siconfi: string, competencia: string): Promise<SuperavitData> =>
    fetchAuth(`${BASE}/superavit${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<SuperavitData>(r),
    ),

  recommendations: (siconfi: string, competencia: string): Promise<Recommendations> =>
    fetchAuth(`${BASE}/recommendations${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<Recommendations>(r),
    ),

  compare: (siconfi: string, a: string, b: string): Promise<Compare> =>
    fetchAuth(`${BASE}/compare${qs({ siconfi, a, b })}`).then((r) => jsonOrThrow<Compare>(r)),

  log: (params: {
    execucao_id?: string;
    level?: string;
    limit?: number;
  } = {}): Promise<LogPage> =>
    fetchAuth(`${BASE}/log${qs(params)}`).then((r) => jsonOrThrow<LogPage>(r)),

  exportExcel: async (siconfi: string, competencia: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/exports/excel${qs({ siconfi, competencia })}`);
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(res.status, body.detail ?? res.statusText);
    }
    _triggerBlobDownload(await res.blob(), `pendencias_${siconfi}_${competencia}.xlsx`);
  },

  exportPdf: async (siconfi: string, competencia: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/exports/pdf${qs({ siconfi, competencia })}`);
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(res.status, body.detail ?? res.statusText);
    }
    _triggerBlobDownload(await res.blob(), `executivo_${siconfi}_${competencia}.pdf`);
  },
};

export { ApiError };
