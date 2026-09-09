import { describe, expect, it } from 'vitest';

import { LIMITE_SERVIDOR_S, LIMITE_TICK_MS, RelogioUso } from './relogioUso';

const T0 = 1_000_000;

describe('RelogioUso', () => {
  it('acumula aberto e ativo com a aba visível e interação recente', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.tick(T0 + 60_000);

    const [balde] = relogio.colher();
    expect(balde.rota).toBe('/inicio');
    expect(balde.aberto_s).toBe(60);
    expect(balde.ativo_s).toBe(60);
  });

  it('OCIOSIDADE EM USO NORMAL: para de contar ativo após o limite, mas segue contando aberto (cadência real: tica e colhe a cada 60s)', () => {
    // Cadência real do hook (Task 15): tica e colhe a cada 60s, nunca um
    // salto único. Cada tick aqui (60s) fica bem abaixo de LIMITE_TICK_MS,
    // então nada aqui aciona o teto de gap anômalo — o que se prova é a
    // ociosidade se manifestando ENTRE colheitas sucessivas, não dentro de
    // um tick gigante.
    const relogio = new RelogioUso('/inicio', T0);

    relogio.tick(T0 + 60_000);
    const [c1] = relogio.colher();
    expect(c1.aberto_s).toBe(60);
    expect(c1.ativo_s).toBe(60);

    relogio.tick(T0 + 120_000);
    const [c2] = relogio.colher();
    expect(c2.aberto_s).toBe(60);
    expect(c2.ativo_s).toBe(60);

    // A janela de ociosidade (aberta em T0, nunca renovada) se esgota em
    // T0 + LIMITE_OCIOSIDADE_MS = T0 + 120_000. Nesta terceira colheita a
    // aba seguiu aberta — aberto_s continua 60 — mas o uso ativo parou.
    relogio.tick(T0 + 180_000);
    const [c3] = relogio.colher();
    expect(c3.aberto_s).toBe(60);
    expect(c3.ativo_s).toBe(0);
  });

  it('OCIOSIDADE EM USO NORMAL: volta a contar ativo depois de uma interação (cadência real: tica e colhe a cada 60s)', () => {
    // Chega ao estado ocioso pela mesma cadência realista do teste acima,
    // depois interage e prova que a colheita seguinte volta a creditar
    // ativo_s igual a aberto_s.
    const relogio = new RelogioUso('/inicio', T0);

    relogio.tick(T0 + 60_000);
    relogio.colher();
    relogio.tick(T0 + 120_000);
    relogio.colher();
    relogio.tick(T0 + 180_000);
    const [ocioso] = relogio.colher();
    expect(ocioso.ativo_s).toBe(0); // confirma que chegou ocioso, como acima

    relogio.marcarInteracao(T0 + 180_000);
    relogio.tick(T0 + 240_000);
    const [balde] = relogio.colher();
    expect(balde.aberto_s).toBe(60);
    expect(balde.ativo_s).toBe(balde.aberto_s);
  });

  it('congela os dois relógios com a aba oculta', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.setVisivel(false, T0 + 30_000);
    relogio.tick(T0 + 300_000);

    const [balde] = relogio.colher();
    expect(balde.aberto_s).toBe(30);
    expect(balde.ativo_s).toBe(30);
  });

  it('fecha o balde da rota anterior ao trocar de tela', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.setRota('/pendencias', T0 + 60_000);
    relogio.tick(T0 + 90_000);

    const baldes = relogio.colher();
    expect(baldes).toHaveLength(2);
    expect(baldes.find((b) => b.rota === '/inicio')?.aberto_s).toBe(60);
    expect(baldes.find((b) => b.rota === '/pendencias')?.aberto_s).toBe(30);
  });

  it('colher esvazia os baldes — nada é enviado duas vezes', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.tick(T0 + 60_000);

    expect(relogio.colher()).toHaveLength(1);
    expect(relogio.colher()).toHaveLength(0);
  });

  it('descarta baldes com menos de um segundo', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.tick(T0 + 400);

    expect(relogio.colher()).toHaveLength(0);
  });

  // ---------------------------------------------------------------------
  // Testes extras — duas famílias distintas, de propósito:
  //
  // "OCIOSIDADE EM USO NORMAL" (acima) prova a ociosidade em cadência real
  // — tick e colheita a cada 60s, como o hook realmente opera. Nenhum tick
  // aqui chega perto de LIMITE_TICK_MS; a ociosidade se manifesta ENTRE
  // colheitas, nunca dentro de um tick.
  //
  // "CONTRATO COM O SERVIDOR (gap anômalo)" (abaixo) prova os tetos contra
  // cenários que NÃO acontecem em cadência normal — suspensão de máquina
  // (um único tick com decorrido gigante) e colheita atrasada (muitos
  // ticks pequenos acumulando além do que o servidor aceita). NÃO remova
  // estes testes achando que são paranoia: eles existem porque um bucket
  // sem teto já causou perda silenciosa de uso real (ver histórico do
  // arquivo). Também cobre verificação de arredondamento, que não se
  // encaixa em nenhuma das duas famílias acima.
  // ---------------------------------------------------------------------

  it('CONTRATO COM O SERVIDOR (gap anômalo): suspensão longa com a aba visível — nenhum campo do balde passa de 120', () => {
    // Simula o notebook fechado/hibernado por 1 hora: o próximo tick chega
    // com um `decorrido` gigante porque nenhum tick intermediário rodou.
    // Sem o teto por tick, aberto_s chegaria a 3600 e o servidor rejeitaria
    // (422) o balde inteiro, perdendo a hora inteira de uso.
    const relogio = new RelogioUso('/inicio', T0);
    relogio.tick(T0 + 60 * 60_000);

    const [balde] = relogio.colher();
    // O teto por tick credita só os LIMITE_TICK_MS mais recentes do salto
    // como aberto; o restante (quase uma hora) é tratado como tempo de
    // máquina suspensa e descartado, não recuperado.
    expect(balde.aberto_s).toBe(LIMITE_TICK_MS / 1000);
    // A janela de ociosidade (que começou em T0, sem nenhuma interação) já
    // tinha se esgotado bem antes do intervalo creditado como aberto —
    // então nenhum tempo ativo é creditado.
    expect(balde.ativo_s).toBe(0);
    expect(balde.aberto_s).toBeLessThanOrEqual(LIMITE_SERVIDOR_S);
    expect(balde.ativo_s).toBeLessThanOrEqual(LIMITE_SERVIDOR_S);
  });

  it('CONTRATO COM O SERVIDOR (gap anômalo): ativo_s também é limitado — interações periódicas não escapam do teto quando a colheita demora', () => {
    // Cada tick aqui é pequeno (30s, bem abaixo de LIMITE_TICK_MS) e cada
    // interação reabre a janela de ociosidade antes que ela se esgote — se
    // só existisse o teto por tick, isto acumularia 300s de aberto e de
    // ativo, ambos legítimos segundo a lógica de ociosidade. É o colher()
    // que impede que esse balde, não colhido por 5 minutos, saia do
    // relógio violando o contrato de 120s do servidor.
    const relogio = new RelogioUso('/inicio', T0);
    let agora = T0;
    for (let i = 0; i < 10; i += 1) {
      agora += 30_000;
      relogio.marcarInteracao(agora);
    }

    const [balde] = relogio.colher();
    expect(balde.aberto_s).toBe(LIMITE_SERVIDOR_S);
    expect(balde.ativo_s).toBe(LIMITE_SERVIDOR_S);
    expect(balde.aberto_s).toBeLessThanOrEqual(LIMITE_SERVIDOR_S);
    expect(balde.ativo_s).toBeLessThanOrEqual(LIMITE_SERVIDOR_S);
  });

  // Consolidação: o teste "uso normal não regride" que existia aqui foi
  // removido por ficar redundante — ele só ticava 60s uma vez e colhia,
  // exatamente o que o primeiro teste do arquivo já prova, e exatamente a
  // primeira colheita do teste de ociosidade em cadência real, acima. Não
  // exercitava nenhum teto (nunca chegava perto de 120s), então não
  // pertencia à família "gap anômalo" nem trazia cobertura própria.

  it('não há deriva de arredondamento acumulada entre muitos ticks pequenos', () => {
    // 30 ticks de 1500ms = 45000ms de tempo real decorrido.
    const relogio = new RelogioUso('/inicio', T0);
    let agora = T0;
    for (let i = 0; i < 30; i += 1) {
      agora += 1500;
      relogio.tick(agora);
    }

    const decorridoRealMs = agora - T0;
    const [balde] = relogio.colher();
    // A soma é acumulada em milissegundos e só arredondada (floor) uma vez,
    // na colheita — por isso o total colhido bate exatamente com o tempo
    // real decorrido, sem perder frações a cada tick.
    expect(decorridoRealMs).toBe(45_000);
    expect(balde.aberto_s).toBe(45);
    expect(balde.aberto_s).toBe(Math.floor(decorridoRealMs / 1000));
  });

  it('descartar um balde de rota com menos de 1s não afeta o balde legítimo de outra rota', () => {
    const relogio = new RelogioUso('/inicio', T0);
    relogio.setRota('/pendencias', T0 + 400);
    relogio.tick(T0 + 400 + 60_000);

    const baldes = relogio.colher();
    expect(baldes).toHaveLength(1);
    expect(baldes[0].rota).toBe('/pendencias');
    expect(baldes[0].aberto_s).toBe(60);
  });
});
