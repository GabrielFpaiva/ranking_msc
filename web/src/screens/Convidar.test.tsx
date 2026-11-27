// Testes da tela /convidar — emissão do convite (só o e-mail),
// resultado com e sem envio do e-mail, erros do contrato e a lista dos
// convites já emitidos. A API é simulada; o backend é testado à parte.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api } from '../api/client';
import type { InviteAccess, InviteCreated, InviteSent } from '../api/client';
import { App } from '../App';
import { authStore } from '../store/auth';
import { DrawerProvider } from '../store/drawer';
import { MCRAProvider } from '../store/mcra';
import { Convidar } from './Convidar';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: {
      ...mod.api,
      createInvite: vi.fn(),
      listInvites: vi.fn(),
      inviteCapability: vi.fn(),
      inviteAccess: vi.fn(),
      activateInvites: vi.fn(),
      updateInviteSender: vi.fn(),
      usoHoje: vi.fn(),
      usoHeartbeat: vi.fn(),
    },
  };
});

const createInviteMock = vi.mocked(api.createInvite);
const listInvitesMock = vi.mocked(api.listInvites);
const inviteAccessMock = vi.mocked(api.inviteAccess);
const activateMock = vi.mocked(api.activateInvites);
const updateSenderMock = vi.mocked(api.updateInviteSender);

const ACESSO_EMISSOR: InviteAccess = {
  can_invite: true,
  can_activate: true,
  smtp_user: 'envio@gmail.com',
};

const CONVITE: InviteCreated = {
  email: 'ana@pmjp.gov.br',
  expires_at: '2026-11-17T14:30:00-03:00',
  email_sent: true,
  code: 'MCRA1.eyJ2IjoxfQ.assinatura-longa-do-convite',
};

const EMITIDO: InviteSent = {
  email: 'bruno@pmjp.gov.br',
  issued_at: '2026-11-10T09:05:00-03:00',
  expires_at: '2026-11-17T09:05:00-03:00',
  email_sent: false,
};

function renderConvidar() {
  return render(
    <MemoryRouter initialEntries={['/convidar']}>
      <Convidar />
    </MemoryRouter>,
  );
}

async function emitir(user: ReturnType<typeof userEvent.setup>, email = 'ana@pmjp.gov.br') {
  await user.type(await screen.findByLabelText('E-mail do colaborador'), email);
  await user.click(screen.getByRole('button', { name: 'Enviar convite' }));
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  createInviteMock.mockReset();
  listInvitesMock.mockReset();
  listInvitesMock.mockResolvedValue([]);
  inviteAccessMock.mockReset();
  inviteAccessMock.mockResolvedValue(ACESSO_EMISSOR);
  activateMock.mockReset();
  updateSenderMock.mockReset();
});

describe('Convidar — ativação pelo app (sem Python na máquina de quem convida)', () => {
  it('emissor ainda não ativado vê o formulário de ativação, não o de convite', async () => {
    inviteAccessMock.mockResolvedValue({ can_invite: false, can_activate: true, smtp_user: null });
    renderConvidar();

    expect(await screen.findByText('Ativar os convites neste computador')).toBeTruthy();
    expect(screen.queryByLabelText('E-mail do colaborador')).toBeNull();
    expect(listInvitesMock).not.toHaveBeenCalled();
  });

  it('ativa com código e Gmail (sem senha da chave) e passa a mostrar o convite', async () => {
    const user = userEvent.setup();
    inviteAccessMock.mockResolvedValue({ can_invite: false, can_activate: true, smtp_user: null });
    activateMock.mockResolvedValue(ACESSO_EMISSOR);
    renderConvidar();

    await user.type(await screen.findByLabelText('Código de ativação'), 'MCRA-ATIVACAO1.abc');
    expect(screen.queryByLabelText(/senha da chave/i)).toBeNull();
    await user.type(screen.getByLabelText('Conta do Gmail que envia os convites'), 'envio@gmail.com');
    await user.type(screen.getByLabelText('Senha de app do Gmail'), 'abcd efgh');
    await user.click(screen.getByRole('button', { name: 'Ativar convites' }));

    expect(activateMock).toHaveBeenCalledWith('MCRA-ATIVACAO1.abc', {
      smtpUser: 'envio@gmail.com',
      smtpPassword: 'abcd efgh',
    });
    expect(await screen.findByLabelText('E-mail do colaborador')).toBeTruthy();
    expect(screen.getByText('envio@gmail.com')).toBeTruthy();
  });

  it('código de outra versão mostra o detail da API', async () => {
    const user = userEvent.setup();
    inviteAccessMock.mockResolvedValue({ can_invite: false, can_activate: true, smtp_user: null });
    activateMock.mockRejectedValue(new ApiError(409, 'Este código de ativação não é o desta versão.'));
    renderConvidar();

    await user.type(await screen.findByLabelText('Código de ativação'), 'MCRA-ATIVACAO1.abc');
    await user.type(screen.getByLabelText('Conta do Gmail que envia os convites'), 'e@gmail.com');
    await user.type(screen.getByLabelText('Senha de app do Gmail'), 'x');
    await user.click(screen.getByRole('button', { name: 'Ativar convites' }));

    expect((await screen.findByRole('alert')).textContent).toBe(
      'Este código de ativação não é o desta versão.',
    );
  });

  it('quem não é emissor nem pode ativar vê "Sem permissão"', async () => {
    inviteAccessMock.mockResolvedValue({ can_invite: false, can_activate: false, smtp_user: null });
    renderConvidar();

    expect(await screen.findByText('Sem permissão para convidar')).toBeTruthy();
  });

  it('troca a conta de envio sem pedir senha da chave', async () => {
    const user = userEvent.setup();
    updateSenderMock.mockResolvedValue({ ...ACESSO_EMISSOR, smtp_user: 'nova@gmail.com' });
    renderConvidar();

    await user.click(
      await screen.findByRole('button', { name: 'Trocar conta ou senha de app do Gmail' }),
    );
    const conta = screen.getByLabelText('Conta do Gmail');
    await user.clear(conta);
    await user.type(conta, 'nova@gmail.com');
    await user.type(screen.getByLabelText('Nova senha de app do Gmail'), 'wxyz');
    await user.click(screen.getByRole('button', { name: 'Salvar conta de envio' }));

    expect(updateSenderMock).toHaveBeenCalledWith({
      smtpUser: 'nova@gmail.com',
      smtpPassword: 'wxyz',
    });
    expect(await screen.findByText('Conta de envio atualizada.')).toBeTruthy();
    expect(screen.getByText('nova@gmail.com')).toBeTruthy();
  });

  it('403 ao enviar, para quem pode ativar, leva à ativação e não a "Sem permissão"', async () => {
    const user = userEvent.setup();
    createInviteMock.mockRejectedValue(new ApiError(403, 'Sem permissão para convidar.'));
    renderConvidar();

    await emitir(user);

    expect(await screen.findByText('Ativar os convites neste computador')).toBeTruthy();
    expect(screen.queryByText('Sem permissão para convidar')).toBeNull();
  });

  it('"Ativar de novo" abre a reativação', async () => {
    const user = userEvent.setup();
    renderConvidar();

    await user.click(await screen.findByRole('button', { name: 'Ativar de novo' }));

    expect(screen.getByText('Ativar os convites de novo')).toBeTruthy();
    expect(screen.getByLabelText('Código de ativação')).toBeTruthy();
  });
});

describe('Convidar — lista dos convites emitidos', () => {
  it('sem convites emitidos mostra o formulário e o aviso de lista vazia', async () => {
    renderConvidar();

    expect(await screen.findByLabelText('E-mail do colaborador')).toBeTruthy();
    // Convidar é só o e-mail: nenhum campo de senha no formulário.
    expect(screen.queryByLabelText(/senha/i)).toBeNull();
    expect(await screen.findByText('Nenhum convite emitido neste computador.')).toBeTruthy();
  });

  it('a explicação do formulário não afirma um prazo fixo (a validade é configurável)', async () => {
    renderConvidar();

    const texto = await screen.findByText(/Digite o e-mail e clique em Enviar convite/);
    expect(texto.textContent).toBe(
      'Digite o e-mail e clique em Enviar convite. A pessoa recebe o link para instalar o MCRA e escolhe a própria senha.',
    );
    expect(screen.queryByText(/\d+ dias/)).toBeNull();
  });

  it('lista cada convite com e-mail, datas em pt-BR e se o e-mail saiu', async () => {
    listInvitesMock.mockResolvedValue([
      EMITIDO,
      { ...EMITIDO, email: 'carla@pmjp.gov.br', email_sent: true },
    ]);
    renderConvidar();

    const linha = (await screen.findByText('bruno@pmjp.gov.br')).closest('tr');
    expect(linha).not.toBeNull();
    const celulas = within(linha as HTMLElement)
      .getAllByRole('cell')
      .map((c) => c.textContent);
    expect(celulas).toEqual([
      'bruno@pmjp.gov.br',
      '10/11/2026 às 09:05',
      '17/11/2026 às 09:05',
      'Não',
    ]);
    const outra = screen.getByText('carla@pmjp.gov.br').closest('tr');
    expect(within(outra as HTMLElement).getAllByRole('cell')[3].textContent).toBe('Sim');
  });

  it('falha ao carregar a lista avisa, mas o formulário continua disponível', async () => {
    listInvitesMock.mockRejectedValue(new ApiError(500, 'boom'));
    renderConvidar();

    expect(
      await screen.findByText('Não foi possível carregar a lista de convites. Tente novamente.'),
    ).toBeTruthy();
    expect(screen.getByLabelText('E-mail do colaborador')).toBeTruthy();
  });
});

describe('Convidar — sem permissão', () => {
  it('403 ao carregar a lista mostra o aviso e esconde o formulário', async () => {
    listInvitesMock.mockRejectedValue(new ApiError(403, 'Sem permissão para convidar.'));
    renderConvidar();

    expect(await screen.findByText('Sem permissão para convidar')).toBeTruthy();
    expect(screen.queryByLabelText('E-mail do colaborador')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByText(/\[403\]/)).toBeNull();
  });

  it('403 ao enviar (permissão perdida) troca o formulário pelo aviso', async () => {
    inviteAccessMock.mockResolvedValue({ ...ACESSO_EMISSOR, can_activate: false });
    createInviteMock.mockRejectedValue(new ApiError(403, 'Sem permissão para convidar.'));
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect(await screen.findByText('Sem permissão para convidar')).toBeTruthy();
    expect(screen.queryByLabelText('E-mail do colaborador')).toBeNull();
  });
});

describe('Convidar — emissão', () => {
  it('envia só o e-mail e mostra para quem foi e até quando vale', async () => {
    createInviteMock.mockResolvedValue(CONVITE);
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect(createInviteMock).toHaveBeenCalledWith('ana@pmjp.gov.br');
    const status = await screen.findByRole('status');
    expect(status.textContent).toBe(
      'Convite enviado por e-mail para ana@pmjp.gov.br. Vale até 17/11/2026 às 14:30.',
    );
    // O e-mail saiu: o código não precisa aparecer na tela.
    expect(screen.queryByLabelText('Código do convite')).toBeNull();
    expect(screen.queryByText(CONVITE.code)).toBeNull();
  });

  it('mostra o vencimento no horário de Recife mesmo quando a API devolve outro offset', async () => {
    createInviteMock.mockResolvedValue({ ...CONVITE, expires_at: '2026-11-17T17:30:00+00:00' });
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect((await screen.findByRole('status')).textContent).toContain('Vale até 17/11/2026 às 14:30.');
  });

  it('atualiza a lista depois de emitir e limpa o e-mail para o próximo convite', async () => {
    createInviteMock.mockResolvedValue(CONVITE);
    listInvitesMock.mockResolvedValueOnce([]).mockResolvedValueOnce([
      { ...EMITIDO, email: 'ana@pmjp.gov.br', email_sent: true },
    ]);
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    await waitFor(() => expect(listInvitesMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('cell', { name: 'ana@pmjp.gov.br' })).toBeTruthy();
    expect((screen.getByLabelText('E-mail do colaborador') as HTMLInputElement).value).toBe('');
  });

  it('e-mail que não saiu mostra o código para copiar, com aviso', async () => {
    createInviteMock.mockResolvedValue({ ...CONVITE, email_sent: false });
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(
      'O e-mail não saiu. O convite para ana@pmjp.gov.br foi criado e vale até 17/11/2026 às 14:30: copie o código abaixo e envie a ele por outro meio.',
    );
    const campo = screen.getByLabelText('Código do convite') as HTMLElement & {
      value: string;
      readOnly: boolean;
    };
    expect(campo.value).toBe(CONVITE.code);
    expect(campo.readOnly).toBe(true);

    await user.click(screen.getByRole('button', { name: 'Copiar código' }));

    expect(await window.navigator.clipboard.readText()).toBe(CONVITE.code);
    expect(await screen.findByText('Código copiado.')).toBeTruthy();
  });

  it('copiar que falha orienta a copiar à mão', async () => {
    createInviteMock.mockResolvedValue({ ...CONVITE, email_sent: false });
    const user = userEvent.setup();
    renderConvidar();
    await emitir(user);
    await screen.findByLabelText('Código do convite');
    vi.spyOn(window.navigator.clipboard, 'writeText').mockRejectedValue(new Error('negado'));

    await user.click(screen.getByRole('button', { name: 'Copiar código' }));

    expect(
      await screen.findByText(
        'Não foi possível copiar sozinho. Selecione o código acima e copie com Ctrl+C.',
      ),
    ).toBeTruthy();
  });

  it('422 mostra o detail em português que a API devolveu', async () => {
    createInviteMock.mockRejectedValue(
      new ApiError(422, 'O e-mail do colaborador não é válido. Confira o endereço.'),
    );
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect((await screen.findByRole('alert')).textContent).toBe(
      'O e-mail do colaborador não é válido. Confira o endereço.',
    );
  });

  it('422 sem detail em texto pede para conferir o endereço, em português', async () => {
    createInviteMock.mockRejectedValue(new ApiError(422, ''));
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect((await screen.findByRole('alert')).textContent).toBe(
      'O e-mail informado não parece válido. Confira o endereço e tente de novo.',
    );
  });

  it('409 (chave de convites que não é a da versão instalada) mostra o detail e mantém o e-mail', async () => {
    const detail =
      'A chave de convites deste computador não é a da versão instalada. Instale a versão mais recente do MCRA e tente de novo.';
    createInviteMock.mockRejectedValue(new ApiError(409, detail));
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect((await screen.findByRole('alert')).textContent).toBe(detail);
    expect((screen.getByLabelText('E-mail do colaborador') as HTMLInputElement).value).toBe(
      'ana@pmjp.gov.br',
    );
  });

  it.each([
    ['erro 5xx', new ApiError(500, 'Internal Server Error')],
    ['rede fora', new TypeError('Failed to fetch')],
  ])('%s mostra a mensagem de conexão e mantém o e-mail', async (_nome, erro) => {
    createInviteMock.mockRejectedValue(erro);
    const user = userEvent.setup();
    renderConvidar();

    await emitir(user);

    expect((await screen.findByRole('alert')).textContent).toBe(
      'Não foi possível conectar ao servidor. Tente novamente.',
    );
    expect((screen.getByLabelText('E-mail do colaborador') as HTMLInputElement).value).toBe(
      'ana@pmjp.gov.br',
    );
  });

});

describe('Convidar — rota', () => {
  it('/convidar abre dentro do Layout, atrás do login', async () => {
    authStore.setToken('tok-valido');
    vi.mocked(api.inviteCapability).mockResolvedValue(true);
    vi.mocked(api.usoHoje).mockResolvedValue({ aberto_s: 0, ativo_s: 0 });
    vi.mocked(api.usoHeartbeat).mockResolvedValue(undefined);
    render(
      <MCRAProvider>
        <DrawerProvider>
          <MemoryRouter initialEntries={['/convidar']}>
            <App />
          </MemoryRouter>
        </DrawerProvider>
      </MCRAProvider>,
    );

    expect(await screen.findByLabelText('E-mail do colaborador')).toBeTruthy();
    // Dentro do Layout: o menu lateral e o título da rota estão na tela.
    expect(screen.getByRole('link', { name: 'Início' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Convidar colaborador' })).toBeTruthy();
    authStore.clearToken();
  });

  it('sem sessão, /convidar manda para o login', async () => {
    authStore.clearToken();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    render(
      <MemoryRouter initialEntries={['/convidar']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeTruthy();
    expect(screen.queryByLabelText('E-mail do colaborador')).toBeNull();
    vi.unstubAllGlobals();
  });
});
