// Testes da tela "Meu tempo de uso" — carregamento, números do período,
// detalhamento por tela, navegação de janela (mês/ano) e tratamento de erro.
//
// A fixture de `dias` usa um mês fixo (setembro/2026) sem relação com o
// `ref` real que `hojeISO()` calcula em tempo de execução — a tela só
// exibe o que a API devolve em `data.dias`, nunca deriva o mês a partir de
// `ref` diretamente. Isso evita depender de congelar o relógio do sistema
// só para este teste. Os testes de navegação (‹ ›) comparam contra o que
// `moverJanela` calcularia a partir do `ref` real capturado na primeira
// chamada — pela mesma razão.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../api/client';
import { moverJanela } from '../format';
import type { UsoAnual, UsoDia, UsoHistorico } from '../types';
import { MeuTempo } from './MeuTempo';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return {
    ...mod,
    api: { ...mod.api, usoHistorico: vi.fn(), usoAnual: vi.fn() },
  };
});

const usoHistoricoMock = vi.mocked(api.usoHistorico);
const usoAnualMock = vi.mocked(api.usoAnual);

/** Setembro/2026 inteiro, com zeros — mesmo formato que o backend devolve em
 * `dias`. Dois dias da semana 07–13 recebem uso (6h40 cada, somando 13h20)
 * para o teste do total por semana ter um valor não trivial de conferir. */
function mesFixo(): UsoDia[] {
  return Array.from({ length: 30 }, (_, i) => {
    const numero = i + 1;
    const aberto_s = numero === 7 || numero === 8 ? 24_000 : 0;
    return {
      dia: `2026-09-${String(numero).padStart(2, '0')}`,
      aberto_s,
      ativo_s: aberto_s,
    };
  });
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

const ANO_FIXTURE: UsoAnual = {
  ano: 2026,
  total_aberto_s: 36_000,
  total_ativo_s: 20_000,
  meses: Array.from({ length: 12 }, (_, i) => ({
    mes: `2026-${String(i + 1).padStart(2, '0')}`,
    aberto_s: (i + 1) * 1000,
    ativo_s: (i + 1) * 500,
  })),
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

  it('o total por semana aparece com o valor certo, com o intervalo de dias', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // Semana de 07–13/09, com 6h40 em cada um de dois dias = 13h20.
    expect(screen.getByText('07 – 13')).toBeTruthy();
    expect(screen.getByText('13h20')).toBeTruthy();
  });

  it('trocar para "Mês" busca o ano e desenha doze barras', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);
    usoAnualMock.mockResolvedValue(ANO_FIXTURE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));

    await waitFor(() => expect(usoAnualMock).toHaveBeenCalledTimes(1));
    expect(usoAnualMock.mock.calls[0][0]).toBe(2026);

    await waitFor(() => {
      expect(container.querySelectorAll('.uso-ano-col').length).toBe(12);
    });
  });

  it('falha no gráfico anual mostra mensagem própria, sem travar o resto da tela', async () => {
    const { ApiError } = await import('../api/client');
    usoHistoricoMock.mockResolvedValue(BASE);
    usoAnualMock.mockRejectedValue(new ApiError(500, 'boom'));

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));

    expect(await screen.findByText('Não foi possível carregar o gráfico do ano.')).toBeTruthy();
    // Sem banner de página inteira — o erro do gráfico não usa `role="alert"`.
    expect(screen.queryByRole('alert')).toBeNull();

    // O resto da tela — números do card e "Por tela" — continua funcionando.
    expect(screen.getByTestId('uso-total').textContent).toBe('2h00');
    expect(screen.getByTestId('uso-aberto').textContent).toBe('2h00');
    expect(screen.getByText('Início')).toBeTruthy();
    expect(screen.getByText('1h23')).toBeTruthy();
  });

  it('‹ navega e dispara nova busca com o ref da janela anterior', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);
    const [primeiraEscala, primeiroRef] = usoHistoricoMock.mock.calls[0];

    fireEvent.click(screen.getByRole('button', { name: 'Período anterior' }));

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));
    const [segundaEscala, segundoRef] = usoHistoricoMock.mock.calls[1];
    expect(segundaEscala).toBe(primeiraEscala);
    expect(segundoRef).toBe(moverJanela(primeiraEscala, primeiroRef, -1));
  });

  it('› fica desabilitado na janela corrente (não navega para o futuro)', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // `ref` inicial é "hoje" — a janela corrente é sempre a mais recente
    // navegável, então "›" já nasce desabilitado, sem precisar congelar o
    // relógio do sistema para este teste.
    const botaoProximo = screen.getByRole('button', { name: 'Próximo período' }) as HTMLButtonElement;
    expect(botaoProximo.disabled).toBe(true);
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
