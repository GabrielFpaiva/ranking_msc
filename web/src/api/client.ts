// Wrapper fino sobre fetch para o backend FastAPI.
// Em dev usa o proxy do Vite (/api → :8000). Em prod é same-origin.

import { authStore } from '../store/auth';

import type {
  Compare,
  Competencia,
  ContaDetail,
  ContaList,
  EntregasResponse,
  EscalaUso,
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
  UsoAnual,
  UsoHistorico,
  UsoHoje,
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

// Normaliza o campo `detail` do FastAPI para string. Em erros de validação
// (422) o detail é um ARRAY de objetos {msg, loc, ...} — sem normalizar, o
// array vazaria para ApiError.detail e as telas tentariam renderizar objetos
// como children do React.
function detailToString(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((item) =>
        item && typeof item === 'object' && typeof (item as { msg?: unknown }).msg === 'string'
          ? (item as { msg: string }).msg
          : null,
      )
      .filter((msg): msg is string => msg !== null);
    if (msgs.length > 0) return msgs.join('; ');
  }
  return undefined;
}

async function extractDetail(res: Response): Promise<string | undefined> {
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return detailToString(body.detail);
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new ApiError(res.status, (await extractDetail(res)) ?? res.statusText);
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
    throw new ApiError(res.status, (await extractDetail(res)) ?? 'Falha ao criar o usuário.');
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
    throw new ApiError(res.status, (await extractDetail(res)) ?? 'Credenciais inválidas');
  }
  const data = (await res.json()) as { access_token: string };
  authStore.setToken(data.access_token);
}

// Convite assinado. Os tipos moram aqui (e não em types.ts) porque só este
// módulo e as telas Login e Convidar os usam.
export interface InviteAccepted {
  username: string;
  password_reset: boolean;
}

export interface InviteCreated {
  email: string;
  /** ISO 8601 com offset. */
  expires_at: string;
  email_sent: boolean;
  code: string;
}

export interface InviteSent {
  email: string;
  issued_at: string;
  expires_at: string;
  email_sent: boolean;
}

/** O que o usuário logado pode fazer com convites neste computador. */
export interface InviteAccess {
  can_invite: boolean;
  /** É o emissor do invites.yaml: pode (re)ativar os convites com o código de ativação. */
  can_activate: boolean;
  /** Conta do Gmail que envia (só para quem pode convidar). */
  smtp_user: string | null;
}

/** Conta de envio (o login de quem convida autoriza a troca). */
export interface InviteSenderInput {
  smtpUser: string;
  smtpPassword: string;
}

/** Rota pública: o convidado ainda não tem conta. `true` = há chave pública configurada. */
export async function apiInviteStatus(): Promise<boolean> {
  const res = await fetch(`${BASE}/auth/invite-status`);
  const data = await jsonOrThrow<{ enabled: boolean }>(res);
  return data.enabled;
}

/** Rota pública: a prova é a assinatura do código. Não guarda token; o login vem depois. */
export async function apiAcceptInvite(code: string, password: string): Promise<InviteAccepted> {
  const res = await fetch(`${BASE}/auth/invite/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, password }),
  });
  return jsonOrThrow<InviteAccepted>(res);
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

  // Telemetria de uso: nunca deve interromper o usuário, então a promise
  // sempre resolve — mas um status não-2xx (ex: payload inválido em dev)
  // aparece no console em vez de desaparecer em silêncio.
  //
  // `manterVivo` liga `fetch(..., { keepalive: true })` — só para o envio de
  // saída disparado por `pagehide` (ver useTempoUso.ts). Sem isso, um fetch
  // iniciado depois que a página começa a descarregar pode ser abortado pelo
  // browser antes de completar, perdendo o último intervalo. Não é
  // `navigator.sendBeacon`: `sendBeacon` não aceita header customizado, e
  // este endpoint exige `Authorization` (JWT) — `keepalive` resolve o mesmo
  // problema de sobrevivência ao unload sem abrir mão do header. Fica
  // desligado por padrão porque `keepalive` tem teto de corpo por navegador
  // (~64kB somados) e o caminho normal (intervalo, `visibilitychange`) não
  // precisa dessa garantia.
  usoHeartbeat: (
    rota: string,
    aberto_s: number,
    ativo_s: number,
    opcoes: { manterVivo?: boolean } = {},
  ): Promise<void> =>
    fetchAuth(`${BASE}/uso/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rota, aberto_s, ativo_s }),
      ...(opcoes.manterVivo ? { keepalive: true } : {}),
    }).then((r) => {
      if (!r.ok) {
        console.warn(`[uso] heartbeat falhou (${r.status}) para rota=${rota}`);
      }
    }),

  usoHoje: (): Promise<UsoHoje> =>
    fetchAuth(`${BASE}/uso/hoje`).then((r) => jsonOrThrow<UsoHoje>(r)),

  usoHistorico: (escala: EscalaUso, ref: string): Promise<UsoHistorico> =>
    fetchAuth(`${BASE}/uso/historico${qs({ escala, ref })}`).then((r) =>
      jsonOrThrow<UsoHistorico>(r),
    ),

  usoAnual: (ano: number): Promise<UsoAnual> =>
    fetchAuth(`${BASE}/uso/anual${qs({ ano })}`).then((r) => jsonOrThrow<UsoAnual>(r)),

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

  getEntregas: (ano: number): Promise<EntregasResponse> =>
    fetchAuth(`${BASE}/entregas${qs({ ano })}`).then((r) => jsonOrThrow<EntregasResponse>(r)),

  log: (params: {
    execucao_id?: string;
    level?: string;
    limit?: number;
  } = {}): Promise<LogPage> =>
    fetchAuth(`${BASE}/log${qs(params)}`).then((r) => jsonOrThrow<LogPage>(r)),

  /** Mostra o item "Convidar" no menu? (pode convidar, ou é o emissor e ainda vai ativar). */
  inviteCapability: (): Promise<boolean> =>
    api.inviteAccess().then((data) => data.can_invite || data.can_activate),

  inviteAccess: (): Promise<InviteAccess> =>
    fetchAuth(`${BASE}/invites/capability`)
      .then((r) => jsonOrThrow<Partial<InviteAccess> & { can_invite: boolean }>(r))
      .then((data) => ({
        can_invite: data.can_invite,
        can_activate: data.can_activate ?? false,
        smtp_user: data.smtp_user ?? null,
      })),

  // Código de ativação e senha de app só passam por aqui, no
  // corpo da requisição; nada é guardado.
  activateInvites: (
    activationCode: string,
    sender: InviteSenderInput,
  ): Promise<InviteAccess> =>
    fetchAuth(`${BASE}/invites/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        activation_code: activationCode,
        smtp_user: sender.smtpUser,
        smtp_password: sender.smtpPassword,
      }),
    }).then((r) => jsonOrThrow<InviteAccess>(r)),

  updateInviteSender: (sender: InviteSenderInput): Promise<InviteAccess> =>
    fetchAuth(`${BASE}/invites/sender`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        smtp_user: sender.smtpUser,
        smtp_password: sender.smtpPassword,
      }),
    }).then((r) => jsonOrThrow<InviteAccess>(r)),

  /** Convida pelo e-mail: é só isso que quem convida informa. */
  createInvite: (email: string): Promise<InviteCreated> =>
    fetchAuth(`${BASE}/invites`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }).then((r) => jsonOrThrow<InviteCreated>(r)),

  listInvites: (): Promise<InviteSent[]> =>
    fetchAuth(`${BASE}/invites`).then((r) => jsonOrThrow<InviteSent[]>(r)),

  /** Troca a senha do usuário logado. 400 = senha atual incorreta (não desloga). */
  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) {
      throw new ApiError(res.status, (await extractDetail(res)) ?? res.statusText);
    }
  },

  exportExcel: async (siconfi: string, competencia: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/exports/excel${qs({ siconfi, competencia })}`);
    if (!res.ok) {
      throw new ApiError(res.status, (await extractDetail(res)) ?? res.statusText);
    }
    _triggerBlobDownload(await res.blob(), `pendencias_${siconfi}_${competencia}.xlsx`);
  },

  usoRelatorio: async (escala: EscalaUso, ref: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/uso/relatorio${qs({ escala, ref })}`);
    if (!res.ok) {
      throw new ApiError(res.status, (await extractDetail(res)) ?? res.statusText);
    }
    const disposicao = res.headers.get('Content-Disposition') ?? '';
    const nome = /filename="([^"]+)"/.exec(disposicao)?.[1] ?? `uso_${ref}.pdf`;
    _triggerBlobDownload(await res.blob(), nome);
  },

  exportPdf: async (siconfi: string, competencia: string): Promise<void> => {
    const res = await fetchAuth(`${BASE}/exports/pdf${qs({ siconfi, competencia })}`);
    if (!res.ok) {
      throw new ApiError(res.status, (await extractDetail(res)) ?? res.statusText);
    }
    _triggerBlobDownload(await res.blob(), `executivo_${siconfi}_${competencia}.pdf`);
  },
};

export { ApiError };
