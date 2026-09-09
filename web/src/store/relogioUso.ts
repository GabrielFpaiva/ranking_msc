// Contagem de tempo de uso no browser.
//
// Separado do hook de propósito: a lógica de ociosidade, visibilidade e troca
// de rota é onde moram os bugs, e testá-la através de um hook React exigiria
// fake timers. Aqui os carimbos de tempo entram por parâmetro.

/** Sem interação por este tempo, o relógio de uso ativo pausa. */
export const LIMITE_OCIOSIDADE_MS = 120_000;

/**
 * Teto de milissegundos que um único `tick()` pode creditar aos baldes.
 *
 * Este número está amarrado ao teto de segundos que o servidor aceita por
 * heartbeat (`LIMITE_SERVIDOR_S`, abaixo, e o schema de
 * `POST /api/uso/heartbeat`) — se um mudar, o outro precisa mudar junto.
 *
 * Um tick cujo `decorrido` passe deste teto não significa que a pessoa usou
 * o sistema o intervalo inteiro: significa que os ticks pararam de disparar
 * — a máquina foi suspensa, o SO hibernou, a aba ficou congelada. Tempo de
 * máquina suspensa não é tempo de uso: a pessoa não estava lá. Por isso não
 * tentamos "recuperar" esse intervalo — só deixamos de creditá-lo.
 */
export const LIMITE_TICK_MS = 120_000;

/**
 * Teto de segundos que o servidor aceita por campo, por heartbeat (ver
 * schema de `POST /api/uso/heartbeat`). Defesa em profundidade: mesmo com o
 * teto por tick acima, ticks sucessivos entre duas colheitas ainda podem
 * somar mais que isso num mesmo balde. `colher()` nunca devolve um valor
 * que o servidor rejeitaria — isto protege o contrato com o servidor
 * independentemente da cadência dos ticks. A perda em casos raros (um
 * balde que fica muito tempo sem ser colhido) é aceitável para telemetria.
 */
export const LIMITE_SERVIDOR_S = 120;

export interface BaldeUso {
  rota: string;
  aberto_s: number;
  ativo_s: number;
}

interface Balde {
  abertoMs: number;
  ativoMs: number;
}

export class RelogioUso {
  private rota: string;
  private visivel = true;
  private ultimoTick: number;
  private ultimaInteracao: number;
  private baldes = new Map<string, Balde>();

  constructor(rota: string, agora: number) {
    this.rota = rota;
    this.ultimoTick = agora;
    this.ultimaInteracao = agora;
  }

  /** Avança os relógios até `agora`, creditando o intervalo à rota atual. */
  tick(agora: number): void {
    const decorridoReal = agora - this.ultimoTick;
    this.ultimoTick = agora;
    if (decorridoReal <= 0 || !this.visivel) return;

    // Só o que cabe no teto por tick é creditado aos baldes — o resto é
    // tratado como tempo de máquina suspensa, não como uso (ver
    // LIMITE_TICK_MS acima). `ultimoTick` já avançou para o `agora` real,
    // então o intervalo descartado nunca é contado de novo.
    const decorrido = Math.min(decorridoReal, LIMITE_TICK_MS);

    const balde = this.baldeAtual();
    balde.abertoMs += decorrido;

    // Fração do intervalo em que ainda havia interação recente. Sem isso, um
    // intervalo que cruza o limite de ociosidade seria contado inteiro ou
    // descartado inteiro.
    const fimDaJanelaAtiva = this.ultimaInteracao + LIMITE_OCIOSIDADE_MS;
    const inicio = agora - decorrido;
    const ativoAte = Math.min(agora, fimDaJanelaAtiva);
    if (ativoAte > inicio) balde.ativoMs += ativoAte - inicio;
  }

  /** Registra interação do usuário (clique, tecla, scroll). */
  marcarInteracao(agora: number): void {
    this.tick(agora);
    this.ultimaInteracao = agora;
  }

  /** Liga ou desliga a contagem conforme a visibilidade da aba. */
  setVisivel(visivel: boolean, agora: number): void {
    this.tick(agora);
    this.visivel = visivel;
    // Voltar à aba conta como presença, mas não como interação: o relógio de
    // uso ativo só volta a correr quando a pessoa realmente mexer em algo.
  }

  /** Fecha o balde da rota atual e passa a creditar a nova. */
  setRota(rota: string, agora: number): void {
    this.tick(agora);
    this.rota = rota;
  }

  /**
   * Devolve os baldes fechados em segundos e zera o acumulado.
   *
   * Cada campo é limitado a `LIMITE_SERVIDOR_S` — o contrato com
   * `POST /api/uso/heartbeat` não aceita mais que isso, e nenhum balde deve
   * sair daqui violando esse contrato, não importa o histórico de ticks que
   * o formou.
   */
  colher(): BaldeUso[] {
    const colhidos: BaldeUso[] = [];
    for (const [rota, balde] of this.baldes) {
      const aberto_s = Math.min(Math.floor(balde.abertoMs / 1000), LIMITE_SERVIDOR_S);
      const ativo_s = Math.min(Math.floor(balde.ativoMs / 1000), LIMITE_SERVIDOR_S);
      if (aberto_s > 0) colhidos.push({ rota, aberto_s, ativo_s });
    }
    this.baldes.clear();
    return colhidos;
  }

  private baldeAtual(): Balde {
    let balde = this.baldes.get(this.rota);
    if (!balde) {
      balde = { abertoMs: 0, ativoMs: 0 };
      this.baldes.set(this.rota, balde);
    }
    return balde;
  }
}
