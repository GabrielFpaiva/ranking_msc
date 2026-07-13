// Testes do wrapper de API — foco no comportamento de autenticação:
// 401 em qualquer chamada autenticada limpa a sessão (logout forçado).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { authStore } from '../store/auth';
import { ApiError, api, apiLogin, apiSetup } from './client';

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
