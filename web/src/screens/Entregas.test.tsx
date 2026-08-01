// Testes da tela de Entregas — resumo, banner de degradação e coluna de prazo.

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Entregas from './Entregas';
import type { EntregasResponse } from '../types';

const base: EntregasResponse = {
  ano: 2025,
  id_ente: 2507507,
  origem: 'api',
  buscado_em: '2026-07-31T12:00:00Z',
  aviso: null,
  resumo: { total: 4, homologadas: 2, retificadas: 1 },
  entregas: [
    {
      instituicao: 'Prefeitura Municipal de João Pessoa - PB',
      entregavel: 'Relatório Resumido de Execução Orçamentária',
      periodo: 1,
      periodicidade: 'B',
      status: 'RETIFICADO',
      data_status: '2025-04-29T09:39:08Z',
      fim_periodo: '2025-02-28',
      dias_apos_fim_periodo: 60,
      prazo_dias: 30,
      atrasada: true,
    },
  ],
};

vi.mock('../api/client', () => ({
  api: { getEntregas: vi.fn(() => Promise.resolve(base)) },
}));

describe('Entregas', () => {
  // Fixa `Date.now()` no instante de `base.buscado_em` para que `idadeDoDado`
  // ("atualizado há Xh") seja determinístico — sem isso, o texto varia com o
  // horário real de execução e pode colidir com os regex soltos usados abaixo
  // (ex: "atualizado há 11h" também casa com /1/).
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date(base.buscado_em as string).getTime());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mostra a contagem de retificações', async () => {
    render(<Entregas />);
    expect(await screen.findByText(/1/)).toBeTruthy();
    expect(await screen.findByText(/retificad/i)).toBeTruthy();
  });

  it('mostra os dias decorridos mesmo sem prazo configurado', async () => {
    const semPrazo = {
      ...base,
      entregas: [{ ...base.entregas[0], prazo_dias: null, atrasada: null }],
    };
    const { api } = await import('../api/client');
    vi.mocked(api.getEntregas).mockResolvedValueOnce(semPrazo);

    render(<Entregas />);

    expect(await screen.findByText(/60/)).toBeTruthy();
    expect(screen.queryByText(/atrasad/i)).toBeNull();
  });

  it('avisa quando os dados vêm do cache', async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.getEntregas).mockResolvedValueOnce({
      ...base,
      origem: 'cache',
      aviso: 'Não foi possível atualizar com o Siconfi.',
    });

    render(<Entregas />);

    expect(await screen.findByText(/não foi possível atualizar/i)).toBeTruthy();
  });
});
