// Testes da tela "Meu tempo de uso" — carregamento, números do período,
// detalhamento por tela, navegação do período selecionado (‹ › e clique
// direto numa barra/bloco) e tratamento de erro.
//
// A fixture de `dias` usa um mês fixo (setembro/2026) sem relação com o
// `ref` real que `hojeISO()` calcula em tempo de execução — a tela só
// exibe o que a API devolve em `data.dias`, nunca deriva o mês a partir de
// `ref` diretamente. Isso evita depender de congelar o relógio do sistema
// só para este teste. Os testes de navegação (‹ ›) comparam contra o que
// `moverPeriodo` calcularia a partir do `ref` real capturado na primeira
// chamada — pela mesma razão.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api } from '../api/client';
import { descricaoJanela, moverPeriodo } from '../format';
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
 * `dias`. Dois dias da semana 07–13 recebem uso (6h40 cada, somando 13h20),
 * repartido entre duas rotas, para o teste do total por semana ter um valor
 * não trivial de conferir e para a pilha ter mais de um segmento. */
/** Converte o texto de `formatarDuracao` ("1h23" ou "45m") de volta a
 * minutos — só para conferir, em teste, que partes exibidas somam o total
 * exibido sem duplicar a lógica de `formatarDuracao` no teste. */
function minutosDoTexto(texto: string): number {
  const [h, m] = texto.includes('h') ? texto.split('h') : ['0', texto.replace('m', '')];
  return Number(h) * 60 + Number(m);
}

function mesFixo(): UsoDia[] {
  return Array.from({ length: 30 }, (_, i) => {
    const numero = i + 1;
    const aberto_s = numero === 7 || numero === 8 ? 24_000 : 0;
    const por_rota: Record<string, number> = aberto_s > 0 ? { '/inicio': 18_000, '/pendencias': 6_000 } : {};
    return {
      dia: `2026-09-${String(numero).padStart(2, '0')}`,
      aberto_s,
      ativo_s: aberto_s,
      por_rota,
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
    { rota: '/inicio', aberto_s: 5000, ativo_s: 4000 }, // 1h23 (83min)
    { rota: '/pendencias', aberto_s: 2200, ativo_s: 1400 }, // 36,67min "sozinho" — 37m exibido (ver testes)
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
    por_rota: { '/inicio': (i + 1) * 1000 },
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
    // /inicio = 5000s = 83,33min exibidos (1h23, sem resto a distribuir).
    // /pendencias = 2200s = 36,67min "sozinho", mas a distribuição por maior
    // resto dá a ele o minuto que sobra (83 + 36 = 119 ≠ 120 = total exibido)
    // — por isso 37m aqui, não os 36m que `formatarDuracao(2200)` daria
    // isolado. Ver `distribuirMaiorResto` em format.ts.
    expect(screen.getByText('Início')).toBeTruthy();
    expect(screen.getByText('1h23')).toBeTruthy();
    expect(screen.getByText('Pendências')).toBeTruthy();
    expect(screen.getAllByText('37m').length).toBeGreaterThan(0);
  });

  it('"Por tela" mostra o percentual de cada rota e uma entrada "Total aberto", e as partes fecham com o total', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // /inicio = 5000/7200 ≈ 69%, /pendencias = 2200/7200 ≈ 31% — somam 100.
    expect(screen.getByText('69%')).toBeTruthy();
    expect(screen.getByText('31%')).toBeTruthy();
    // "Total aberto", não só "Total": deixa explícito que a faixa decompõe o
    // tempo aberto — não deve ser confundida com "Ocioso", exibido ao lado.
    expect(screen.getByText('Total aberto')).toBeTruthy();

    // As partes exibidas (1h23 = 83min, 37m) somam exatamente o minuto do
    // total exibido (2h00 = 120min) — 83 + 37 = 120, não 119.
    const minutos = [...container.querySelectorAll('.uso-legenda-item:not(.uso-legenda-total) .uso-legenda-tempo')]
      .map((el) => minutosDoTexto(el.textContent ?? ''));
    expect(minutos.reduce((soma, m) => soma + m, 0)).toBe(120);

    const percentuais = [...container.querySelectorAll('.uso-legenda-pct')]
      .map((el) => Number((el.textContent ?? '').replace('%', '')));
    expect(percentuais.reduce((soma, p) => soma + p, 0)).toBe(100);
  });

  it('os ativos exibidos por tela somam o ATIVO do card em cima', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // BASE: /inicio 4000s ativos, /pendencias 1400s — soma 5400s = total_ativo_s
    // (1h30, os mesmos "ATIVO" do card acima). Cada chip mostra o ativo
    // distribuído por maior resto na barrinha ativo/ocioso.
    const minutosAtivos = [...container.querySelectorAll('.uso-legenda-ativo-tempo')].map((el) =>
      minutosDoTexto(el.textContent ?? ''),
    );
    expect(minutosAtivos.reduce((soma, m) => soma + m, 0)).toBe(90); // 1h30 = 90min
  });

  it('chip com ativo muito menor que o aberto (aba esquecida aberta, caso "Início")', async () => {
    // 59min abertos, só 5min de uso de verdade — o caso real que motivou o
    // pedido: sem a barrinha, essa diferença fica invisível na tela.
    const dadosInicioEsquecido: UsoHistorico = {
      ...BASE,
      total_aberto_s: 3540, // 59m
      total_ativo_s: 300, // 5m
      rotas: [{ rota: '/inicio', aberto_s: 3540, ativo_s: 300 }],
    };
    usoHistoricoMock.mockResolvedValue(dadosInicioEsquecido);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // "59m" e "5m" também aparecem no card de cima (aberto/ativo) — a
    // conferência aqui é especificamente no chip "Por tela", não em texto
    // solto na tela inteira.
    const chip = screen.getByText('Início').closest('.uso-legenda-item')!;
    expect(chip.querySelector('.uso-legenda-tempo')?.textContent).toBe('59m'); // aberto — continua o protagonista
    expect(chip.querySelector('.uso-legenda-ativo-tempo')?.textContent).toBe('5m'); // ativo — pequeno, ao lado

    // A barra reflete a proporção: ~8,5% ativo, ~91,5% ocioso — "quase toda
    // esmaecida", como descrito no pedido.
    const trackAtivo = container.querySelector('.uso-legenda-track-ativo') as HTMLElement;
    const trackOcioso = container.querySelector('.uso-legenda-track-ocioso') as HTMLElement;
    const larguraAtivo = Number(trackAtivo.style.width.replace('%', ''));
    const larguraOcioso = Number(trackOcioso.style.width.replace('%', ''));
    expect(larguraAtivo).toBeLessThan(10);
    expect(larguraOcioso).toBeGreaterThan(90);
    expect(larguraAtivo + larguraOcioso).toBeCloseTo(100, 5);
  });

  it('"Outras" soma o ativo (e o aberto) das rotas fora do top 5', async () => {
    const seisRotas = ['/inicio', '/pendencias', '/caixa', '/passivos', '/superavit', '/executivo'];
    // Pesos decrescentes dão rank estável — as cinco primeiras ganham cor
    // própria; a sexta (/executivo) cai em "Outras". Ativo de /executivo é
    // desproporcionalmente baixo (10 de 100) pra distinguir sua barrinha da
    // das demais (metade do aberto) se "Outras" não estivesse somando certo.
    const abertoPorRota = [600, 500, 400, 300, 200, 100];
    const ativoPorRota = [300, 250, 200, 150, 100, 10];
    const diasComSeisRotas: UsoDia[] = Array.from({ length: 30 }, (_, i) => {
      const numero = i + 1;
      if (numero !== 15) {
        return { dia: `2026-09-${String(numero).padStart(2, '0')}`, aberto_s: 0, ativo_s: 0, por_rota: {} };
      }
      const por_rota = Object.fromEntries(seisRotas.map((rota, idx) => [rota, abertoPorRota[idx]]));
      const aberto_s = abertoPorRota.reduce((a, b) => a + b, 0);
      return { dia: '2026-09-15', aberto_s, ativo_s: aberto_s, por_rota };
    });

    const dados: UsoHistorico = {
      escala: 'dia',
      ref: '2026-09-15',
      inicio: '2026-09-15',
      fim: '2026-09-15',
      total_aberto_s: abertoPorRota.reduce((a, b) => a + b, 0),
      total_ativo_s: ativoPorRota.reduce((a, b) => a + b, 0),
      dias: diasComSeisRotas,
      rotas: seisRotas.map((rota, idx) => ({ rota, aberto_s: abertoPorRota[idx], ativo_s: ativoPorRota[idx] })),
    };

    usoHistoricoMock.mockResolvedValue(dados);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    const itemOutras = screen.getByText('Outras').closest('.uso-legenda-item');
    expect(itemOutras).toBeTruthy();

    // "Outras" aqui é só /executivo (100s abertos, 10s ativos) — 10% ativo,
    // bem abaixo dos ~50% de qualquer uma das cinco nomeadas.
    const trackAtivo = itemOutras!.querySelector('.uso-legenda-track-ativo') as HTMLElement;
    expect(trackAtivo.style.width).toBe('10%');
  });

  it('a coluna do dia com duas rotas empilha um segmento por rota', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // Os dias 07 e 08 têm `por_rota` com duas chaves cada — a pilha daquele
    // dia deve ter dois `.uso-barra-seg`, um por rota presente.
    const segmentos = container.querySelectorAll('.uso-barra-pilha .uso-barra-seg');
    expect(segmentos.length).toBeGreaterThanOrEqual(2);
  });

  it('cada bloco de semana tem seu próprio eixo de letras dos dias', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // As semanas agora ficam lado a lado (não empilhadas) — cada bloco
    // precisa da própria grade "S T Q Q S S D", não um cabeçalho único
    // compartilhado acima de todos.
    const blocos = container.querySelectorAll('.uso-semana-bloco');
    expect(blocos.length).toBeGreaterThan(1);
    blocos.forEach((bloco) => {
      const letras = bloco.querySelectorAll('.uso-dias-letras .uso-dia-letra');
      expect(letras.length).toBe(7);
    });
  });

  it('mês de seis semanas (novembro/2026, começa num domingo) ainda renderiza um bloco por semana', async () => {
    // Novembro/2026 começa numa segunda... na verdade num domingo (30 dias,
    // dia 1 é domingo) — o caso em que `agruparEmSemanas` produz 6 blocos,
    // não os 4–5 mais comuns. Sem uso algum no mês, só para isolar o layout.
    const diasNovembro: UsoDia[] = Array.from({ length: 30 }, (_, i) => ({
      dia: `2026-11-${String(i + 1).padStart(2, '0')}`,
      aberto_s: 0,
      ativo_s: 0,
      por_rota: {},
    }));
    const dadosNovembro: UsoHistorico = {
      escala: 'semana',
      ref: '2026-11-02',
      inicio: '2026-11-02',
      fim: '2026-11-08',
      total_aberto_s: 0,
      total_ativo_s: 0,
      dias: diasNovembro,
      rotas: [],
    };
    usoHistoricoMock.mockResolvedValue(dadosNovembro);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    const blocos = container.querySelectorAll('.uso-semana-bloco');
    expect(blocos.length).toBe(6);
    blocos.forEach((bloco) => {
      // Cada bloco, mesmo o último (com um único dia real e o resto vazio),
      // preserva o eixo e os espaços dos dias, sem barras nem destaques
      // que poderiam sugerir uso onde não houve nenhum.
      expect(bloco.querySelectorAll('.uso-dias-letras .uso-dia-letra').length).toBe(7);
      expect(bloco.querySelectorAll('.uso-barra-col').length).toBe(7);
      expect(bloco.querySelectorAll('.uso-barra-pilha').length).toBe(0);
      expect(bloco.querySelectorAll('.uso-barra-col-destaque').length).toBe(0);
    });
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

  it('escala "Mês": clicar numa barra do ano seleciona aquele mês', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);
    usoAnualMock.mockResolvedValue(ANO_FIXTURE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

    // Janeiro de 2026 é passado em relação a "hoje" (setembro/2026) — clicável.
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar jan de 2026' }));

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(3));
    const [escalaChamada, refChamado] = usoHistoricoMock.mock.calls[2];
    expect(escalaChamada).toBe('mes');
    expect(refChamado).toBe('2026-01-01');
  });

  it('escala "Mês": barra de um mês futuro vem desabilitada', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);
    usoAnualMock.mockResolvedValue(ANO_FIXTURE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

    // Dezembro de 2026 é depois de "hoje" (setembro/2026).
    const botaoFuturo = screen.getByRole('button', { name: 'Selecionar dez de 2026' }) as HTMLButtonElement;
    expect(botaoFuturo.disabled).toBe(true);
  });

  it('escala "Semana": clicar num bloco de semana seleciona aquela semana', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // Primeiro bloco do calendário de setembro/2026 (mês começa numa terça) —
    // primeiro dia real é 01/09, no passado em relação a "hoje" (09/09).
    const blocos = container.querySelectorAll('.uso-semana-bloco');
    fireEvent.click(blocos[0]);

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));
    const [escalaChamada, refChamado] = usoHistoricoMock.mock.calls[1];
    expect(escalaChamada).toBe('semana');
    expect(refChamado).toBe('2026-09-01');
  });

  it('trocar para "Dia" mostra a semana do dia selecionado como uma faixa única', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    const { container } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Dia' }));

    await waitFor(() => {
      expect(container.querySelector('[data-testid="uso-dia-grafico"]')).toBeTruthy();
    });

    // Zoom progressivo: "Dia" mostra a semana (7 colunas esticadas), não o
    // mês inteiro em blocos — nada de `.uso-semana-bloco` nem de mais de um
    // rodapé de total.
    expect(container.querySelectorAll('.uso-dia-col').length).toBe(7);
    expect(container.querySelectorAll('.uso-semana-bloco').length).toBe(0);
    expect(container.querySelectorAll('.uso-semana-rodape').length).toBe(1);

    // Semana de 07–13/09, com 6h40 em cada um de dois dias = 13h20 — mesma
    // conta de "o total por semana aparece com o valor certo" abaixo.
    expect(screen.getByText('07 – 13')).toBeTruthy();
    expect(screen.getByText('13h20')).toBeTruthy();
  });

  it('escala "Dia": o cabeçalho descreve o dia selecionado, não a semana nem o mês', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    const [, refInicial] = usoHistoricoMock.mock.calls[0];

    fireEvent.click(screen.getByRole('button', { name: 'Dia' }));

    expect(await screen.findByText(descricaoJanela('dia', refInicial))).toBeTruthy();
  });

  it('escala "Dia": ‹ navega 1 dia por vez, não 1 semana', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Dia' }));
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));
    const [, refAntesDeNavegar] = usoHistoricoMock.mock.calls[1];

    fireEvent.click(screen.getByRole('button', { name: 'Período anterior' }));

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(3));
    const [escalaChamada, refChamado] = usoHistoricoMock.mock.calls[2];
    expect(escalaChamada).toBe('dia');
    expect(refChamado).toBe(moverPeriodo('dia', refAntesDeNavegar, -1));
  });

  it('escala "Dia": clicar numa barra da semana seleciona aquele dia', async () => {
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    fireEvent.click(screen.getByRole('button', { name: 'Dia' }));
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

    // Semana em foco é 07–13/09 (contém 07 e 08, os dias com uso da fixture).
    // 07/09/2026 é uma terça-feira no passado em relação a "hoje" (09/09) —
    // clicável.
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar 07/09' }));

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(3));
    const [escalaChamada, refChamado] = usoHistoricoMock.mock.calls[2];
    expect(escalaChamada).toBe('dia');
    expect(refChamado).toBe('2026-09-07');
  });

  it('escala "Dia": barra de um dia futuro vem desabilitada', async () => {
    // Este teste, ao contrário dos demais do arquivo, depende de "hoje" ser
    // antes de 13/09/2026 (ver comparação em periodoEhFuturo/MeuTempo.tsx
    // contra o relógio real) — sem congelar o relógio aqui, o teste quebra
    // sozinho assim que a data real do sistema ultrapassa 13/09/2026.
    // Só o relógio (Date) é congelado — faking setTimeout/setInterval
    // também travaria o polling assíncrono do waitFor/findByTestId abaixo.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-09-09T12:00:00'));

    try {
      usoHistoricoMock.mockResolvedValue(BASE);

      render(<MeuTempo />);
      await screen.findByTestId('uso-total');

      fireEvent.click(screen.getByRole('button', { name: 'Dia' }));
      await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

      // 13/09/2026 (domingo da semana em foco) é depois de hoje (09/09).
      const botaoFuturo = screen.getByRole('button', { name: 'Selecionar 13/09' }) as HTMLButtonElement;
      expect(botaoFuturo.disabled).toBe(true);
    } finally {
      vi.useRealTimers();
    }
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
    expect(segundoRef).toBe(moverPeriodo(primeiraEscala, primeiroRef, -1));
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

  it('agrupa rotas além do top 5 do domínio em "Outras"', async () => {
    const seisRotas = ['/inicio', '/pendencias', '/caixa', '/passivos', '/superavit', '/executivo'];
    const diasComSeisRotas: UsoDia[] = Array.from({ length: 30 }, (_, i) => {
      const numero = i + 1;
      if (numero !== 15) {
        return { dia: `2026-09-${String(numero).padStart(2, '0')}`, aberto_s: 0, ativo_s: 0, por_rota: {} };
      }
      const por_rota = Object.fromEntries(seisRotas.map((rota, idx) => [rota, (6 - idx) * 100]));
      const aberto_s = Object.values(por_rota).reduce((a, b) => a + b, 0);
      return { dia: '2026-09-15', aberto_s, ativo_s: aberto_s, por_rota };
    });

    const dados: UsoHistorico = {
      escala: 'dia',
      ref: '2026-09-15',
      inicio: '2026-09-15',
      fim: '2026-09-15',
      total_aberto_s: 2100,
      total_ativo_s: 2100,
      dias: diasComSeisRotas,
      rotas: seisRotas.map((rota, idx) => ({ rota, aberto_s: (6 - idx) * 100, ativo_s: (6 - idx) * 100 })),
    };

    usoHistoricoMock.mockResolvedValue(dados);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');

    // A 6ª rota do ranking (/executivo, a menos usada) não ganha cor própria
    // — some da legenda como item nomeado e vira "Outras".
    expect(screen.queryByText('Visão Executiva')).toBeNull();
    expect(screen.getByText('Outras')).toBeTruthy();
  });

  it('"rotas" vazio mostra a mensagem de "sem uso registrado"', async () => {
    usoHistoricoMock.mockResolvedValue({ ...BASE, rotas: [] });

    render(<MeuTempo />);

    expect(await screen.findByText('Sem uso registrado neste período')).toBeTruthy();
  });
});

// DEFEITO 2 (F6-01): a tela ficava parada enquanto aberta — buscava só na
// montagem e na troca de escala/ref, sem acompanhar a mesma cadência de 60s
// do `UsoMini` da sidebar. Só `setInterval`/`clearInterval` são fakeados
// (`toFake`): `waitFor`/`findBy*` da Testing Library continuam usando o
// `setTimeout` real por baixo para fazer polling, então não travam.
describe('MeuTempo — atualização periódica', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('refaz a busca de histórico depois do intervalo de 60s', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(60_000);

    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));
  });

  it('não busca de novo enquanto a aba está oculta', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    usoHistoricoMock.mockResolvedValue(BASE);
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(60_000);
    await Promise.resolve(); // dá chance a qualquer microtask pendente

    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);
  });

  it('mantém os dados anteriores visíveis durante o refresh, sem voltar para "Carregando…"', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let resolverSegunda: (valor: UsoHistorico) => void = () => {};
    usoHistoricoMock
      .mockResolvedValueOnce(BASE)
      .mockImplementationOnce(
        () =>
          new Promise<UsoHistorico>((resolve) => {
            resolverSegunda = resolve;
          }),
      );

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    expect(screen.getByTestId('uso-total').textContent).toBe('2h00');

    vi.advanceTimersByTime(60_000);
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

    // A segunda busca ainda está pendente (a promise não foi resolvida) — a
    // tela não pode voltar para o skeleton de carregamento nem perder o
    // número já exibido.
    expect(screen.queryByText(/carregando/i)).toBeNull();
    expect(screen.getByTestId('uso-total').textContent).toBe('2h00');

    resolverSegunda({ ...BASE, total_aberto_s: 7260 }); // 2h01
    await waitFor(() => expect(screen.getByTestId('uso-total').textContent).toBe('2h01'));
  });

  it('o gráfico anual também refaz a busca depois do intervalo de 60s', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    usoHistoricoMock.mockResolvedValue(BASE);
    usoAnualMock.mockResolvedValue(ANO_FIXTURE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    fireEvent.click(screen.getByRole('button', { name: 'Mês' }));
    await waitFor(() => expect(usoAnualMock).toHaveBeenCalledTimes(1));

    vi.advanceTimersByTime(60_000);

    await waitFor(() => expect(usoAnualMock).toHaveBeenCalledTimes(2));
  });

  it('cancela o timer ao desmontar — nenhuma busca depois disso', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    usoHistoricoMock.mockResolvedValue(BASE);

    const { unmount } = render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    unmount();

    vi.advanceTimersByTime(120_000);
    await Promise.resolve();

    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);
  });

  it('trocar de escala cancela o timer anterior — sem duplicar a busca periódica', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    usoHistoricoMock.mockResolvedValue(BASE);

    render(<MeuTempo />);
    await screen.findByTestId('uso-total');
    expect(usoHistoricoMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Dia' }));
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(2));

    vi.advanceTimersByTime(60_000);

    // Se o timer da escala anterior não tivesse sido cancelado no cleanup do
    // efeito, este avanço geraria 2 chamadas a mais (uma de cada timer), não 1.
    await waitFor(() => expect(usoHistoricoMock).toHaveBeenCalledTimes(3));
  });
});
