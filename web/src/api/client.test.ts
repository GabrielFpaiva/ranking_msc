// Testes do wrapper de API — foco no comportamento de autenticação:
// 401 em qualquer chamada autenticada limpa a sessão (logout forçado).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { authStore } from '../store/auth';
import { ApiError, api, apiAcceptInvite, apiInviteStatus, apiLogin, apiSetup } from './client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiLogin', () => {
  it('guarda o token no authStore quando as credenciais são aceitas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(200, { access_token: 'tok-123' })),
    );

    await apiLogin('admin', 'senha');

    expect(authStore.getToken()).toBe('tok-123');
  });

  it('lança ApiError com o detail do backend quando o login falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: 'Credenciais inválidas' })),
    );

    await expect(apiLogin('admin', 'errada')).rejects.toMatchObject({
      status: 401,
      detail: 'Credenciais inválidas',
    });
    expect(authStore.getToken()).toBeNull();
  });
});

describe('fetchAuth — 401 força logout', () => {
  it('limpa o token quando uma chamada autenticada retorna 401', async () => {
    authStore.setToken('tok-expirado');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: 'Token expirado' })),
    );

    await expect(api.rules()).rejects.toBeInstanceOf(ApiError);

    expect(authStore.getToken()).toBeNull();
  });

  it('envia o token no header Authorization', async () => {
    authStore.setToken('tok-valido');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal('fetch', fetchMock);

    await api.rules();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-valido');
  });

  it('não limpa o token em erros que não são 401', async () => {
    authStore.setToken('tok-valido');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(500, { detail: 'boom' })),
    );

    await expect(api.rules()).rejects.toMatchObject({ status: 500 });

    expect(authStore.getToken()).toBe('tok-valido');
  });
});

describe('normalização do detail (erros de validação FastAPI)', () => {
  it('detail em array (422) vira string com as mensagens — nunca objetos', async () => {
    const validationBody = {
      detail: [
        { type: 'string_too_short', loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
        { type: 'string_pattern_mismatch', loc: ['body', 'username'], msg: 'String should match pattern' },
      ],
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(422, validationBody)));

    const err = await apiSetup('ad min', 'curta').catch((e: unknown) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(typeof (err as ApiError).detail).toBe('string');
    expect((err as ApiError).detail).toBe(
      'String should have at least 8 characters; String should match pattern',
    );
  });

  it('detail em array sem msg utilizável cai no fallback string', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(422, { detail: [{ foo: 1 }] })));

    const err = await api.rules().catch((e: unknown) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(typeof (err as ApiError).detail).toBe('string');
  });
});

describe('convite — rotas públicas (sem token)', () => {
  it('apiInviteStatus consulta GET /api/auth/invite-status e devolve enabled', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { enabled: true }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiInviteStatus()).resolves.toBe(true);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    expect(url).toBe('/api/auth/invite-status');
    expect(init?.method ?? 'GET').toBe('GET');
  });

  it('apiInviteStatus devolve false quando os convites estão desligados', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { enabled: false })));

    await expect(apiInviteStatus()).resolves.toBe(false);
  });

  it('apiInviteStatus rejeita com ApiError quando a API falha', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(500, { detail: 'boom' })));

    await expect(apiInviteStatus()).rejects.toMatchObject({ status: 500 });
  });

  it('apiAcceptInvite envia código e senha por POST e devolve o username', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(201, { username: 'ana@pmjp.gov.br', password_reset: false }));
    vi.stubGlobal('fetch', fetchMock);

    const out = await apiAcceptInvite('MCRA1.abc.def', 'senha-forte-123');

    expect(out).toEqual({ username: 'ana@pmjp.gov.br', password_reset: false });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/auth/invite/accept');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      code: 'MCRA1.abc.def',
      password: 'senha-forte-123',
    });
    expect(authStore.getToken()).toBeNull();
  });

  it('apiAcceptInvite lança ApiError com status e detail do backend (410 vencido)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(410, { detail: 'Convite vencido.' })),
    );

    await expect(apiAcceptInvite('MCRA1.a.b', 'senha-forte-123')).rejects.toMatchObject({
      status: 410,
      detail: 'Convite vencido.',
    });
  });
});

describe('convite — emissão (com token)', () => {
  it('api.inviteCapability envia o token e devolve can_invite', async () => {
    authStore.setToken('tok-valido');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { can_invite: true }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.inviteCapability()).resolves.toBe(true);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/invites/capability');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-valido');
  });

  it('api.inviteCapability mostra o item também para o emissor que ainda vai ativar', async () => {
    authStore.setToken('tok-valido');
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(200, { can_invite: false, can_activate: true, smtp_user: null }),
        ),
    );

    await expect(api.inviteCapability()).resolves.toBe(true);
  });

  it('api.inviteAccess preenche can_activate e smtp_user quando a API antiga não manda', async () => {
    authStore.setToken('tok-valido');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { can_invite: true })));

    await expect(api.inviteAccess()).resolves.toEqual({
      can_invite: true,
      can_activate: false,
      smtp_user: null,
    });
  });

  it('api.activateInvites envia código, senha da chave e conta de envio', async () => {
    authStore.setToken('tok-valido');
    const acesso = { can_invite: true, can_activate: true, smtp_user: 'envio@gmail.com' };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, acesso));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      api.activateInvites('MCRA-ATIVACAO1.xyz', {
        keyPassword: 'senha-da-chave-12',
        smtpUser: 'envio@gmail.com',
        smtpPassword: 'abcd efgh',
      }),
    ).resolves.toEqual(acesso);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/invites/activate');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      activation_code: 'MCRA-ATIVACAO1.xyz',
      key_password: 'senha-da-chave-12',
      smtp_user: 'envio@gmail.com',
      smtp_password: 'abcd efgh',
    });
  });

  it('api.updateInviteSender usa PUT /api/invites/sender', async () => {
    authStore.setToken('tok-valido');
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(200, { can_invite: true, can_activate: true, smtp_user: 'nova@gmail.com' }),
      );
    vi.stubGlobal('fetch', fetchMock);

    await api.updateInviteSender({
      keyPassword: 'senha-da-chave-12',
      smtpUser: 'nova@gmail.com',
      smtpPassword: 'wxyz',
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/invites/sender');
    expect(init.method).toBe('PUT');
  });

  it('api.createInvite envia e-mail e senha da chave e devolve o convite', async () => {
    authStore.setToken('tok-valido');
    const convite = {
      email: 'ana@pmjp.gov.br',
      expires_at: '2026-11-17T14:30:00-03:00',
      email_sent: true,
      code: 'MCRA1.a.b',
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, convite));
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.createInvite('ana@pmjp.gov.br', 'chave-secreta-1')).resolves.toEqual(convite);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/invites');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-valido');
    expect(JSON.parse(init.body as string)).toEqual({
      email: 'ana@pmjp.gov.br',
      key_password: 'chave-secreta-1',
    });
  });

  it('api.createInvite lança ApiError com o detail (400 senha da chave incorreta)', async () => {
    authStore.setToken('tok-valido');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(400, { detail: 'Senha da chave incorreta.' })),
    );

    await expect(api.createInvite('ana@pmjp.gov.br', 'errada')).rejects.toMatchObject({
      status: 400,
      detail: 'Senha da chave incorreta.',
    });
  });

  it('api.listInvites consulta GET /api/invites com o token', async () => {
    authStore.setToken('tok-valido');
    const lista = [
      {
        email: 'ana@pmjp.gov.br',
        issued_at: '2026-11-10T10:00:00-03:00',
        expires_at: '2026-11-17T10:00:00-03:00',
        email_sent: true,
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, lista));
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.listInvites()).resolves.toEqual(lista);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/invites');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-valido');
  });

  it('api.listInvites sem permissão (403) rejeita com status 403 e não limpa o token', async () => {
    authStore.setToken('tok-valido');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(403, { detail: 'Sem permissão para convidar.' })),
    );

    await expect(api.listInvites()).rejects.toMatchObject({ status: 403 });
    expect(authStore.getToken()).toBe('tok-valido');
  });
});

describe('ApiError.userMessage', () => {
  it.each([
    [401, 'Sessão expirada. Faça login novamente.'],
    [409, 'Processamento já em andamento para esta competência.'],
    [422, 'Dados inválidos. Verifique os campos e tente novamente.'],
    [500, 'Erro interno do servidor. Tente novamente mais tarde.'],
  ])('mapeia status %i para mensagem amigável', (status, expected) => {
    expect(new ApiError(status, 'detalhe técnico').userMessage).toBe(expected);
  });
});
