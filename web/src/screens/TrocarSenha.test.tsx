// Testes da tela /senha — troca de senha pelo próprio usuário. A API é simulada.

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api } from '../api/client';
import { TrocarSenha } from './TrocarSenha';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return { ...mod, api: { ...mod.api, changePassword: vi.fn() } };
});

const changeMock = vi.mocked(api.changePassword);

function renderTela() {
  return render(
    <MemoryRouter initialEntries={['/senha']}>
      <TrocarSenha />
    </MemoryRouter>,
  );
}

async function preencher(
  user: ReturnType<typeof userEvent.setup>,
  atual: string,
  nova: string,
  confirmacao = nova,
) {
  await user.type(screen.getByLabelText('Senha atual'), atual);
  await user.type(screen.getByLabelText('Senha nova'), nova);
  await user.type(screen.getByLabelText('Repita a senha nova'), confirmacao);
  await user.click(screen.getByRole('button', { name: 'Trocar senha' }));
}

beforeEach(() => {
  changeMock.mockReset();
});

describe('TrocarSenha', () => {
  it('envia a senha atual e a nova e confirma a troca', async () => {
    const user = userEvent.setup();
    changeMock.mockResolvedValue(undefined);
    renderTela();

    await preencher(user, 'senha-atual-1', 'senha-nova-22');

    expect(changeMock).toHaveBeenCalledWith('senha-atual-1', 'senha-nova-22');
    expect((await screen.findByRole('status')).textContent).toContain('Senha trocada');
    expect((screen.getByLabelText('Senha nova') as HTMLInputElement).value).toBe('');
  });

  it('confirmação diferente não chama a API', async () => {
    const user = userEvent.setup();
    renderTela();

    await preencher(user, 'senha-atual-1', 'senha-nova-22', 'senha-nova-23');

    expect((await screen.findByRole('alert')).textContent).toContain('não é igual');
    expect(changeMock).not.toHaveBeenCalled();
  });

  it('senha nova curta não chama a API', async () => {
    const user = userEvent.setup();
    renderTela();

    await preencher(user, 'senha-atual-1', 'curta');

    expect((await screen.findByRole('alert')).textContent).toContain('mínimo 8');
    expect(changeMock).not.toHaveBeenCalled();
  });

  it('senha atual incorreta (400) mostra o detail da API', async () => {
    const user = userEvent.setup();
    changeMock.mockRejectedValue(new ApiError(400, 'Senha atual incorreta.'));
    renderTela();

    await preencher(user, 'errada-errada', 'senha-nova-22');

    expect((await screen.findByRole('alert')).textContent).toBe('Senha atual incorreta.');
  });
});
