// Testes da tela "Meu tempo de uso" — carregamento, números do período,
// detalhamento por tela, troca de escala e tratamento de erro.
//
// A fixture de `dias` usa um mês fixo (setembro/2026) sem relação com o
// `ref` real que `hojeISO()` calcula em tempo de execução — a tela só
// exibe o que a API devolve em `data.dias`, nunca deriva o mês a partir de
// `ref` diretamente. Isso evita depender de congelar o relógio do sistema
// só para este teste.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../api/client';
import type { UsoDia, UsoHistorico } from '../types';
import { MeuTempo } from './MeuTempo';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: { ...mod.api, usoHistorico: vi.fn() },
  };
});

const usoHistoricoMock = vi.mocked(api.usoHistorico);

/** Setembro/2026 inteiro, com zeros — mesmo formato que o backend devolve em `dias`. */
function mesFixo(): UsoDia[] {
  return Array.from({ length: 30 }, (_, i) => ({
    dia: `2026-09-${String(i + 1).padStart(2, '0')}`,
    aberto_s: 0,
    ativo_s: 0,
  }));
}

const BASE: UsoHistorico = {
  escala: 'semana',
  ref: '2026-09-09',
  inicio: '2026-09-07',
  fim: '2026-09-13',
  total_aberto_s: 7200, // 2h00
  total_ativo_s: 5400, // 1h30 — ocioso = 1800s = 30m
  dias: mesFixo(),
  rotas: [
    { rota: '/inicio', aberto_s: 5000, ativo_s: 4000 }, // 1h23
    { rota: '/pendencias', aberto_s: 2200, ativo_s: 1400 }, // 36m
  ],
};

describe('MeuTempo', () => {
  it('mostra estado de carregamento antes da resposta', () => {
    usoHistoricoMock.mockReturnValue(new Promise<UsoHistorico>(() => {}));

    render(<MeuTempo />);

    expect(screen.getByText(/carregando/i)).toBeTruthy();
  });

  it('renderiza o total, os três números aberto/ativo/ocioso e as linhas de "Por tela"', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);

    expect((await screen.findByTestId('uso-total')).textContent).toBe('2h00');
    expect(screen.getByTestId('uso-aberto').textContent).toBe('2h00');
    expect(screen.getByTestId('uso-ativo').textContent).toBe('1h30');
    expect(screen.getByTestId('uso-ocioso').textContent).toBe('30m');

    // "Por tela": nome amigável (via ROUTE_TITLES) + tempo formatado.
    expect(screen.getByText('Início')).toBeTruthy();
    expect(screen.getByText('1h23')).toBeTruthy();
    expect(screen.getByText('Pendências')).toBeTruthy();
    expect(screen.getByText('36m')).toBeTruthy();
  });

  it('trocar a escala dispara nova busca com o valor certo, mantendo a mesma referência', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);
    const [primeiraEscala, primeiroRef] = usoHistoricoMock.mock.calls[0];
    expect(primeiraEscala).toBe('semana');

    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));
    const [segundaEscala, segundoRef] = usoHistoricoMock.mock.calls[1];
    expect(segundaEscala).toBe('mes');
    // A referência (data do dia corrente) não muda ao trocar de escala.
    expect(segundoRef).toBe(primeiroRef);
  });

  it('erro na API mostra mensagem e não quebra a tela', async () => {
    const { ApiError } = await import('../api/client');
    usoHistoricoMock.mockRejectedValue(new ApiError(500, 'boom'));

    render(<MeuTempo />);

    expect(await screen.findByRole('alert')).toBeTruthy();
    // A tela segue de pé — o card "Por tela" continua renderizado.
    expect(screen.getByText('Por tela')).toBeTruthy();
  });

  it('"rotas" vazio mostra a mensagem de "sem uso registrado"', async () => {
    usoHistoricoMock.mockResolvedValue({ ...BASE, rotas: [] });

    render(<MeuTempo />);

    expect(await screen.findByText('sem uso registrado no período')).toBeTruthy();
  });
});
