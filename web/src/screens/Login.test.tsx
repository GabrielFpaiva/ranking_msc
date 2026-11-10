// Testes da tela de Login — fluxo feliz (redirect), mensagens de erro e
// primeiro acesso (criação do administrador pelo navegador).

import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  apiAcceptInvite,
  apiInviteStatus,
  apiLogin,
  apiSetup,
  apiSetupStatus,
} from '../api/client';
import { Login } from './Login';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    apiAcceptInvite: vi.fn(),
    apiInviteStatus: vi.fn(),
    apiLogin: vi.fn(),
    apiSetup: vi.fn(),
    apiSetupStatus: vi.fn(),
  };
});

const apiAcceptInviteMock = vi.mocked(apiAcceptInvite);
const apiInviteStatusMock = vi.mocked(apiInviteStatus);
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

// Deixa as duas consultas de status (setup e convite) terminarem antes de
// afirmar que algo NÃO apareceu.
async function esperarConsultasDeStatus() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

beforeEach(() => {
  apiAcceptInviteMock.mockReset();
  apiInviteStatusMock.mockReset();
  apiLoginMock.mockReset();
  apiSetupMock.mockReset();
  apiSetupStatusMock.mockReset();
  apiSetupStatusMock.mockResolvedValue(false);
  apiInviteStatusMock.mockResolvedValue(false);
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

describe('Login — convite', () => {
  const CODIGO =
    'MCRA1.eyJ2IjoxLCJlbWFpbCI6ImFuYUBwbWpwLmdvdi5iciJ9\n' +
    '.MEUCIQDabcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';

  async function abrirModoConvite() {
    const user = userEvent.setup();
    renderLogin();
    await user.click(await screen.findByRole('button', { name: 'Tenho um convite' }));
    return user;
  }

  async function preencherConvite(
    user: ReturnType<typeof userEvent.setup>,
    senha: string,
    confirmar: string,
  ) {
    await user.click(screen.getByLabelText('Código do convite'));
    await user.paste(CODIGO);
    await user.type(screen.getByLabelText('Nova senha'), senha);
    await user.type(screen.getByLabelText('Confirmar senha'), confirmar);
    await user.click(screen.getByRole('button', { name: 'Entrar com convite' }));
  }

  beforeEach(() => {
    apiInviteStatusMock.mockResolvedValue(true);
  });

  it('com convites ligados mostra "Tenho um convite"', async () => {
    renderLogin();

    expect(await screen.findByRole('button', { name: 'Tenho um convite' })).toBeTruthy();
  });

  it('com convites desligados não mostra "Tenho um convite"', async () => {
    apiInviteStatusMock.mockResolvedValue(false);
    renderLogin();
    await esperarConsultasDeStatus();

    expect(screen.queryByRole('button', { name: 'Tenho um convite' })).toBeNull();
  });

  it('falha ao consultar o status dos convites não mostra o botão e o login segue normal', async () => {
    apiInviteStatusMock.mockRejectedValue(new ApiError(500, 'boom'));
    apiLoginMock.mockResolvedValue(undefined);
    renderLogin();
    await esperarConsultasDeStatus();

    expect(screen.queryByRole('button', { name: 'Tenho um convite' })).toBeNull();
    await fillAndSubmit({ 'E-mail': 'admin', 'Senha': 'senha-forte' }, 'Entrar');
    expect(await screen.findByText('TELA INICIO')).toBeTruthy();
  });

  it('no primeiro acesso não mostra "Tenho um convite", mesmo com convites ligados', async () => {
    apiSetupStatusMock.mockResolvedValue(true);
    renderLogin();
    await screen.findByText('Primeiro acesso — crie o usuário administrador');
    await esperarConsultasDeStatus();

    expect(screen.queryByRole('button', { name: 'Tenho um convite' })).toBeNull();
  });

  it('abre o modo convite com código, senha e confirmação, sem o campo de e-mail', async () => {
    await abrirModoConvite();

    expect(screen.getByLabelText('Código do convite')).toBeTruthy();
    expect(screen.getByLabelText('Nova senha')).toBeTruthy();
    expect(screen.getByLabelText('Confirmar senha')).toBeTruthy();
    expect(screen.queryByLabelText('E-mail')).toBeNull();
    expect(screen.getByRole('button', { name: 'Entrar com convite' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Voltar ao login' })).toBeTruthy();
  });

  it('aceita o convite, entra com o username devolvido pela API e vai para /inicio', async () => {
    apiAcceptInviteMock.mockResolvedValue({
      username: 'ana@pmjp.gov.br',
      password_reset: false,
    });
    apiLoginMock.mockResolvedValue(undefined);
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');

    expect(apiAcceptInviteMock).toHaveBeenCalledWith(CODIGO, 'senha-forte-123');
    expect(apiLoginMock).toHaveBeenCalledWith('ana@pmjp.gov.br', 'senha-forte-123');
    expect(await screen.findByText('TELA INICIO')).toBeTruthy();
  });

  it('senha curta bloqueia o envio antes de chamar a API', async () => {
    const user = await abrirModoConvite();

    await preencherConvite(user, 'curta', 'curta');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('A senha deve ter pelo menos 8 caracteres.');
    expect(apiAcceptInviteMock).not.toHaveBeenCalled();
  });

  it('senhas diferentes bloqueiam o envio com mensagem clara', async () => {
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'outra-coisa-123');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('As senhas não conferem.');
    expect(apiAcceptInviteMock).not.toHaveBeenCalled();
  });

  it.each([
    [400, 'Código inválido: confira se copiou o código inteiro.'],
    [403, 'Os convites estão desligados nesta versão.'],
    [409, 'Este convite já foi usado neste computador.'],
    [410, 'Este convite venceu em 17/11/2026.'],
  ])('erro %i mostra o detail da API (e não a tradução genérica do client)', async (status, detail) => {
    apiAcceptInviteMock.mockRejectedValue(new ApiError(status, detail));
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(detail);
    expect(apiLoginMock).not.toHaveBeenCalled();
    expect(screen.queryByText('TELA INICIO')).toBeNull();
  });

  it.each([
    [400, 'Código de convite inválido. Copie o código inteiro do e-mail e cole de novo, ou peça um novo convite.'],
    [403, 'Convites não estão ativados nesta versão do MCRA. Procure o responsável técnico.'],
    [409, 'Este convite já foi usado neste computador. Peça um novo convite ao responsável técnico.'],
    [410, 'Este convite venceu. Peça um novo convite ao responsável técnico.'],
  ])('erro %i sem detail diz o que fazer', async (status, mensagem) => {
    apiAcceptInviteMock.mockRejectedValue(new ApiError(status, ''));
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');

    expect((await screen.findByRole('alert')).textContent).toBe(mensagem);
  });

  it.each([
    ['erro 5xx', new ApiError(503, 'Service Unavailable')],
    ['rede fora', new TypeError('Failed to fetch')],
  ])('%s mostra a mensagem de conexão', async (_nome, erro) => {
    apiAcceptInviteMock.mockRejectedValue(erro);
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');

    expect((await screen.findByRole('alert')).textContent).toBe(
      'Não foi possível conectar ao servidor. Tente novamente.',
    );
  });

  it('convite aceito mas login que falha orienta a entrar pelo login normal e devolve o e-mail', async () => {
    apiAcceptInviteMock.mockResolvedValue({
      username: 'ana@pmjp.gov.br',
      password_reset: true,
    });
    apiLoginMock.mockRejectedValue(new ApiError(401, 'Unauthorized'));
    const user = await abrirModoConvite();

    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(
      'Sua conta já foi criada, mas não foi possível entrar agora. Volte ao login e entre com o seu e-mail e a senha que você acabou de escolher.',
    );

    await user.click(screen.getByRole('button', { name: 'Voltar ao login' }));
    expect((screen.getByLabelText('E-mail') as HTMLInputElement).value).toBe('ana@pmjp.gov.br');
  });

  it('"Voltar ao login" restaura o login normal e limpa erro e senhas', async () => {
    apiAcceptInviteMock.mockRejectedValue(new ApiError(410, 'Este convite venceu.'));
    const user = await abrirModoConvite();
    await preencherConvite(user, 'senha-forte-123', 'senha-forte-123');
    await screen.findByRole('alert');

    await user.click(screen.getByRole('button', { name: 'Voltar ao login' }));

    expect(screen.getByLabelText('E-mail')).toBeTruthy();
    expect((screen.getByLabelText('Senha') as HTMLInputElement).value).toBe('');
    expect(screen.queryByLabelText('Código do convite')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Tenho um convite' })).toBeTruthy();
  });
});
