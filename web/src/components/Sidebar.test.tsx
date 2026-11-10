// Testes do menu lateral — o item "Convidar" só aparece para quem a API diz
// que pode convidar; para todos os outros o menu é o de sempre.

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api } from '../api/client';
import { Sidebar } from './Sidebar';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: { ...mod.api, inviteCapability: vi.fn(), usoHoje: vi.fn() },
  };
});

const inviteCapabilityMock = vi.mocked(api.inviteCapability);

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

function itensDoMenu(): string[] {
  return screen
    .getAllByRole('link')
    .map((link) => link.textContent ?? '')
    .filter((texto) => texto !== '');
}

beforeEach(() => {
  inviteCapabilityMock.mockReset();
  vi.mocked(api.usoHoje).mockResolvedValue({ aberto_s: 0, ativo_s: 0 });
});

describe('Sidebar — item Convidar', () => {
  it('can_invite verdadeiro mostra "Convidar" apontando para /convidar', async () => {
    inviteCapabilityMock.mockResolvedValue(true);
    renderSidebar();

    const link = await screen.findByRole('link', { name: 'Convidar' });
    expect(link.getAttribute('href')).toBe('/convidar');
  });

  it('can_invite falso não mostra "Convidar"', async () => {
    inviteCapabilityMock.mockResolvedValue(false);
    renderSidebar();
    await waitFor(() => expect(inviteCapabilityMock).toHaveBeenCalled());

    expect(screen.queryByRole('link', { name: 'Convidar' })).toBeNull();
  });

  it('falha na consulta (403, rede) não mostra "Convidar" e o menu fica igual ao dos outros', async () => {
    inviteCapabilityMock.mockResolvedValue(false);
    const { unmount } = renderSidebar();
    await waitFor(() => expect(inviteCapabilityMock).toHaveBeenCalled());
    const semPermissao = itensDoMenu();
    unmount();

    inviteCapabilityMock.mockRejectedValue(new ApiError(403, 'Sem permissão'));
    renderSidebar();
    await waitFor(() => expect(inviteCapabilityMock).toHaveBeenCalledTimes(2));

    expect(screen.queryByRole('link', { name: 'Convidar' })).toBeNull();
    expect(screen.queryByText('Administração')).toBeNull();
    expect(itensDoMenu()).toEqual(semPermissao);
  });

  it('o item entra antes do grupo Ajuda e o resto do menu continua o mesmo', async () => {
    inviteCapabilityMock.mockResolvedValue(false);
    const { unmount } = renderSidebar();
    await waitFor(() => expect(inviteCapabilityMock).toHaveBeenCalled());
    const base = itensDoMenu();
    unmount();

    inviteCapabilityMock.mockResolvedValue(true);
    renderSidebar();
    await screen.findByRole('link', { name: 'Convidar' });

    const comConvite = itensDoMenu();
    expect(comConvite.filter((t) => t !== 'Convidar')).toEqual(base);
    expect(comConvite.indexOf('Convidar')).toBe(comConvite.indexOf('Ajuda') - 1);
  });
});
