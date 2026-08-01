// Testes da tela de Entregas — resumo, banner de degradação e coluna de prazo.
//
// As queries evitam regex frouxo (`/1/`, `/retificad/i`) contra o texto
// inteiro da página: usam `data-testid` para os contadores do resumo e match
// exato (`getByText('RETIFICADO')`, `getByText('60 dias')`) para o restante.
// A tela mostra status e período por extenso — a colisão de texto se resolve
// no teste, não simplificando a tela.

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
  // horário real de execução.
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date(base.buscado_em as string).getTime());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mostra a contagem de retificações, o status por extenso e a idade do dado', async () => {
    render(<Entregas />);

    const retificadas = await screen.findByTestId('resumo-retificadas');
    expect(retificadas.textContent).toBe('1');
    expect(screen.getByText('Retificadas')).toBeTruthy();

    // Status renderizado por extenso na tabela — quem lê é a contabilidade
    // procurando exatamente esta palavra, não uma abreviação. A mesma entrega
    // aparece em duas seções ("O que vence agora" e "Como estamos"), por isso
    // getAllByText em vez de getByText.
    expect(screen.getAllByText('RETIFICADO').length).toBeGreaterThan(0);

    // idadeDoDado — caminho feliz, Date.now() == buscado_em ⇒ "atualizado agora".
    expect(screen.getByText('atualizado agora')).toBeTruthy();
  });

  it('mostra os dias decorridos mesmo sem prazo configurado, sem rótulo de situação', async () => {
    const semPrazo = {
      ...base,
      entregas: [{ ...base.entregas[0], prazo_dias: null, atrasada: null }],
    };
    const { api } = await import('../api/client');
    vi.mocked(api.getEntregas).mockResolvedValueOnce(semPrazo);

    render(<Entregas />);

    expect(await screen.findByText('60 dias')).toBeTruthy();
    // situacaoPrazo nunca imprime a palavra "atrasada" — o texto proibido é
    // especificamente "no prazo" (e "fora do prazo"), que o ternário
    // produziria se a guarda de `atrasada === null` fosse removida.
    expect(screen.queryByText(/no prazo/i)).toBeNull();
    expect(screen.queryByText(/fora do prazo/i)).toBeNull();
  });

  it('avisa quando os dados vêm do cache degradado (aviso preenchido)', async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.getEntregas).mockResolvedValueOnce({
      ...base,
      origem: 'cache',
      aviso: 'Não foi possível atualizar com o Siconfi.',
    });

    render(<Entregas />);

    expect(await screen.findByText(/não foi possível atualizar/i)).toBeTruthy();
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('cache dentro do TTL (origem=cache, aviso=null) NÃO mostra banner de degradação', async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.getEntregas).mockResolvedValueOnce({
      ...base,
      origem: 'cache',
      aviso: null,
    });

    render(<Entregas />);

    // Espera o carregamento terminar antes de afirmar ausência do banner.
    await screen.findByTestId('resumo-retificadas');
    expect(screen.queryByRole('status')).toBeNull();
  });
});
