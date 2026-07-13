// Testes da tela de Pendências — carregamento, filtros e tratamento de erro.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api } from '../api/client';
import type { PendenciasPage } from '../types';
import { Pendencias } from './Pendencias';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: { ...mod.api, pendencias: vi.fn(), exportExcel: vi.fn() },
  };
});

vi.mock('../store/useMCRA', () => ({
  useMCRA: () => ({ siconfi: '2507507EX', competencia: '2025-11' }),
}));

vi.mock('../store/useDrawer', () => ({
  useDrawer: () => ({ openRule: vi.fn(), openConta: vi.fn() }),
}));

const pendenciasMock = vi.mocked(api.pendencias);

const PAGE: PendenciasPage = {
  competencia: '2025-11',
  siconfi: '2507507EX',
  total: 2,
  items: [
    {
      regra_id: 'R082',
      regra_nome: 'Débito = Crédito',
      dimensao: 'Fechamento',
      severidade: 'ERRO',
      conta_contabil: '111110200',
      descricao: 'Débito difere do crédito',
      valor_esperado: '100,00',
      valor_encontrado: '90,00',
      competencia: '2025-11',
    },
    {
      regra_id: 'R054',
      regra_nome: 'Continuidade temporal',
      dimensao: 'Temporal',
      severidade: 'ALERTA',
      conta_contabil: '211110100',
      descricao: 'Saldo inicial difere do final anterior',
      valor_esperado: '50,00',
      valor_encontrado: '40,00',
      competencia: '2025-11',
    },
  ],
};

function renderPendencias(initialEntry = '/pendencias') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Pendencias />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  pendenciasMock.mockReset();
  pendenciasMock.mockResolvedValue(PAGE);
});

describe('Pendencias — carregamento', () => {
  it('busca e lista as pendências da competência ativa', async () => {
    renderPendencias();

    expect(await screen.findByText('Débito difere do crédito')).toBeTruthy();
    expect(screen.getByText('R082')).toBeTruthy();
    expect(screen.getByText('R054')).toBeTruthy();
    expect(pendenciasMock).toHaveBeenCalledWith(
      expect.objectContaining({
        siconfi: '2507507EX',
        competencia: '2025-11',
        offset: 0,
        severidade: undefined,
        dimensao: undefined,
      }),
    );
  });

  it('erro da API exibe alerta com mensagem amigável', async () => {
    pendenciasMock.mockRejectedValue(new ApiError(500, 'boom'));
    renderPendencias();

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Erro interno do servidor. Tente novamente mais tarde.');
  });
});

describe('Pendencias — filtros', () => {
  it('filtro de severidade refaz a busca com o parâmetro e volta à página 1', async () => {
    const user = userEvent.setup();
    renderPendencias();
    await screen.findByText('Débito difere do crédito');

    await user.click(screen.getByRole('radio', { name: 'ERRO' }));

    await waitFor(() => {
      expect(pendenciasMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ severidade: 'ERRO', offset: 0 }),
      );
    });
  });

  it('filtro de dimensão (deep-link na URL) é aplicado na busca', async () => {
    renderPendencias('/pendencias?dimensao=Fechamento');

    await waitFor(() => {
      expect(pendenciasMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ dimensao: 'Fechamento' }),
      );
    });
  });

  it('trocar a dimensão no select refaz a busca com o novo valor', async () => {
    const user = userEvent.setup();
    renderPendencias();
    await screen.findByText('Débito difere do crédito');

    await user.selectOptions(screen.getByRole('combobox'), 'Temporal');

    await waitFor(() => {
      expect(pendenciasMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ dimensao: 'Temporal', offset: 0 }),
      );
    });
  });

  it('"Limpar filtros" remove todos os filtros da busca', async () => {
    const user = userEvent.setup();
    renderPendencias('/pendencias?dimensao=Fechamento');
    await screen.findByText('Débito difere do crédito');
    await user.click(screen.getByRole('radio', { name: 'ERRO' }));
    await waitFor(() => {
      expect(pendenciasMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ severidade: 'ERRO' }),
      );
    });

    await user.click(screen.getByRole('button', { name: 'Limpar filtros' }));

    await waitFor(() => {
      expect(pendenciasMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          severidade: undefined,
          dimensao: undefined,
          regra_id: undefined,
          conta_prefix: undefined,
          offset: 0,
        }),
      );
    });
  });
});
