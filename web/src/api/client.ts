// Wrapper fino sobre fetch para o backend FastAPI.
// Em dev usa o proxy do Vite (/api → :8000). Em prod é same-origin.

import type {
  Competencia,
  ContaDetail,
  ContaList,
  Heatmap,
  PendenciasPage,
  Rule,
  RuleDetail,
  RuleHistory,
  RunSummary,
  Score,
  ScoreHistory,
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

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  );
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&');
}

export const api = {
  health: (): Promise<{ status: string; rules_enabled: string }> =>
    fetch(`${BASE}/health`).then((r) => jsonOrThrow<{ status: string; rules_enabled: string }>(r)),

  competencias: (siconfi?: string): Promise<Competencia[]> =>
    fetch(`${BASE}/competencias${qs({ siconfi })}`).then((r) => jsonOrThrow<Competencia[]>(r)),

  run: (file: File): Promise<RunSummary> => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${BASE}/run`, { method: 'POST', body: form }).then((r) =>
      jsonOrThrow<RunSummary>(r),
    );
  },

  score: (siconfi: string, competencia: string): Promise<Score> =>
    fetch(`${BASE}/score${qs({ siconfi, competencia })}`).then((r) => jsonOrThrow<Score>(r)),

  scoreHistory: (siconfi: string, meses = 6): Promise<ScoreHistory> =>
    fetch(`${BASE}/score-history${qs({ siconfi, meses })}`).then((r) =>
      jsonOrThrow<ScoreHistory>(r),
    ),

  pendencias: (params: {
    siconfi: string;
    competencia: string;
    regra_id?: string;
    severidade?: string;
    conta_prefix?: string;
    offset?: number;
    limit?: number;
  }): Promise<PendenciasPage> =>
    fetch(`${BASE}/pendencias${qs(params)}`).then((r) => jsonOrThrow<PendenciasPage>(r)),

  rules: (): Promise<Rule[]> =>
    fetch(`${BASE}/rules`).then((r) => jsonOrThrow<Rule[]>(r)),

  rule: (ruleId: string): Promise<RuleDetail> =>
    fetch(`${BASE}/rules/${encodeURIComponent(ruleId)}`).then((r) => jsonOrThrow<RuleDetail>(r)),

  heatmap: (siconfi: string, meses = 6): Promise<Heatmap> =>
    fetch(`${BASE}/heatmap${qs({ siconfi, meses })}`).then((r) => jsonOrThrow<Heatmap>(r)),

  ruleHistory: (siconfi: string, ruleId: string, meses = 6): Promise<RuleHistory> =>
    fetch(
      `${BASE}/rule-history/${encodeURIComponent(ruleId)}${qs({ siconfi, meses })}`,
    ).then((r) => jsonOrThrow<RuleHistory>(r)),

  conta: (
    contaContabil: string,
    siconfi: string,
    competencia: string,
  ): Promise<ContaDetail> =>
    fetch(
      `${BASE}/contas/${encodeURIComponent(contaContabil)}${qs({ siconfi, competencia })}`,
    ).then((r) => jsonOrThrow<ContaDetail>(r)),

  caixa: (siconfi: string, competencia: string): Promise<ContaList> =>
    fetch(`${BASE}/caixa${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<ContaList>(r),
    ),

  passivos: (siconfi: string, competencia: string): Promise<ContaList> =>
    fetch(`${BASE}/passivos${qs({ siconfi, competencia })}`).then((r) =>
      jsonOrThrow<ContaList>(r),
    ),

  superavit: (siconfi: string, competencia: string): Promise<Response> =>
    fetch(`${BASE}/superavit${qs({ siconfi, competencia })}`),
};

export { ApiError };
