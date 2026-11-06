// Testes da tela de Login — fluxo feliz (redirect), mensagens de erro e
// primeiro acesso (criação do administrador pelo navegador).

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiLogin, apiSetup, apiSetupStatus } from '../api/client';
import { Login } from './Login';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    apiLogin: vi.fn(),
    apiSetup: vi.fn(),
    apiSetupStatus: vi.fn(),
  };
});

const apiLoginMock = vi.mocked(apiLogin);
const apiSetupMock = vi.mocked(apiSetup);
const apiSetupStatusMock = vi.mocked(apiSetupStatus);

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/inicio" element={<div>TELA INICIO</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillAndSubmit(fields: Record<string, string>, buttonName: string) {
  const user = userEvent.setup();
  for (const [label, value] of Object.entries(fields)) {
    await user.type(screen.getByLabelText(label), value);
  }
  await user.click(screen.getByRole('button', { name: buttonName }));
}

beforeEach(() => {
  apiLoginMock.mockReset();
  apiSetupMock.mockReset();
  apiSetupStatusMock.mockReset();
  apiSetupStatusMock.mockResolvedValue(false);
});

describe('Login', () => {
  it('login válido chama apiLogin e navega para /inicio', async () => {
    apiLoginMock.mockResolvedValue(undefined);
    renderLogin();

    await fillAndSubmit({ 'E-mail': 'admin', 'Senha': 'senha-forte' }, 'Entrar');

    expect(apiLoginMock).toHaveBeenCalledWith('admin', 'senha-forte');
    expect(await screen.findByText('TELA INICIO')).toBeTruthy();
  });

  it('credenciais inválidas (401) mostram mensagem amigável', async () => {
    apiLoginMock.mockRejectedValue(new ApiError(401, 'Unauthorized'));
    renderLogin();

    await fillAndSubmit({ 'E-mail': 'admin', 'Senha': 'errada-123' }, 'Entrar');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('E-mail ou senha inválidos.');
    expect(screen.queryByText('TELA INICIO')).toBeNull();
  });

  it('erro de servidor (>=500) mostra mensagem de conexão', async () => {
    apiLoginMock.mockRejectedValue(new ApiError(500, 'Internal Server Error'));
    renderLogin();

    await fillAndSubmit({ 'E-mail': 'admin', 'Senha': 'senha-forte' }, 'Entrar');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(
      'Não foi possível conectar ao servidor. Tente novamente.',
    );
  });
});

describe('Login — ajuda', () => {
  it('login tem link para ajuda', () => {
    renderLogin();

    const link = screen.getByRole('link', { name: 'Precisa de ajuda?' });
    expect(link.getAttribute('href')).toBe('/ajuda');
  });
});

describe('Login — primeiro acesso', () => {
  beforeEach(() => {
    apiSetupStatusMock.mockResolvedValue(true);
  });

  it('sem usuários configurados, mostra o formulário de criação do admin', async () => {
    renderLogin();

    expect(
      await screen.findByText('Primeiro acesso — crie o usuário administrador'),
    ).toBeTruthy();
    expect(screen.getByLabelText('Confirmar senha')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Criar administrador' })).toBeTruthy();
  });

  it('cria o admin, faz login automático e navega para /inicio', async () => {
    apiSetupMock.mockResolvedValue(undefined);
    apiLoginMock.mockResolvedValue(undefined);
    renderLogin();
    await screen.findByLabelText('Confirmar senha');

    await fillAndSubmit(
      {
        'E-mail': 'admin',
        'Senha': 'senha-forte-123',
        'Confirmar senha': 'senha-forte-123',
      },
      'Criar administrador',
    );

    expect(apiSetupMock).toHaveBeenCalledWith('admin', 'senha-forte-123');
    expect(apiLoginMock).toHaveBeenCalledWith('admin', 'senha-forte-123');
    expect(await screen.findByText('TELA INICIO')).toBeTruthy();
  });

  it('senhas diferentes bloqueiam o envio com mensagem clara', async () => {
    renderLogin();
    await screen.findByLabelText('Confirmar senha');

    await fillAndSubmit(
      {
        'E-mail': 'admin',
        'Senha': 'senha-forte-123',
        'Confirmar senha': 'outra-coisa-123',
      },
      'Criar administrador',
    );

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('As senhas não conferem.');
    expect(apiSetupMock).not.toHaveBeenCalled();
  });

  it('senha curta bloqueia o envio antes de chamar a API', async () => {
    renderLogin();
    await screen.findByLabelText('Confirmar senha');

    await fillAndSubmit(
      { 'E-mail': 'admin', 'Senha': 'curta', 'Confirmar senha': 'curta' },
      'Criar administrador',
    );

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('A senha deve ter pelo menos 8 caracteres.');
    expect(apiSetupMock).not.toHaveBeenCalled();
  });

  it('setup concluído por outra sessão (403) orienta a fazer login', async () => {
    apiSetupMock.mockRejectedValue(new ApiError(403, 'Setup já concluído.'));
    renderLogin();
    await screen.findByLabelText('Confirmar senha');

    await fillAndSubmit(
      {
        'E-mail': 'admin',
        'Senha': 'senha-forte-123',
        'Confirmar senha': 'senha-forte-123',
      },
      'Criar administrador',
    );

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Setup já concluído. Faça login com suas credenciais.');
  });
});
