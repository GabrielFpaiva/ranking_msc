// Testes do badge de tempo de uso na sidebar — estado de carregamento,
// duração formatada e queda silenciosa em caso de falha na API.

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../api/client';
import type { UsoHoje } from '../types';
import { UsoMini } from './UsoMini';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: { ...mod.api, usoHoje: vi.fn() },
  };
});

const usoHojeMock = vi.mocked(api.usoHoje);

function renderUsoMini() {
  return render(
    <MemoryRouter>
      <UsoMini />
    </MemoryRouter>,
  );
}

describe('UsoMini', () => {
  it('mostra "—" antes da requisição resolver', () => {
    // Promise nunca resolve neste teste — captura o estado inicial.
    usoHojeMock.mockReturnValue(new Promise<UsoHoje>(() => {}));

    renderUsoMini();

    expect(screen.getByText('—')).toBeTruthy();
  });

  it('mostra a duração formatada depois que a requisição resolve', async () => {
    usoHojeMock.mockResolvedValue({ aberto_s: 3660, ativo_s: 1200 });

    renderUsoMini();

    expect(await screen.findByText('1h01')).toBeTruthy();
  });

  it('mostra "—" quando a requisição falha, sem lançar erro', async () => {
    usoHojeMock.mockRejectedValue(new Error('falhou'));

    renderUsoMini();

    await waitFor(() => {
      expect(usoHojeMock).toHaveBeenCalled();
    });
    expect(screen.getByText('—')).toBeTruthy();
  });
});
