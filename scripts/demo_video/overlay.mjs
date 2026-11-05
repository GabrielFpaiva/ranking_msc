/**
 * Camada visual sobreposta ao app durante a gravacao.
 *
 * Resolve duas ausencias do `recordVideo` do Playwright:
 *
 * 1. **Cursor.** A gravacao nao captura o ponteiro do mouse. Sem um cursor
 *    desenhado, o video mostra campos sendo preenchidos e telas trocando
 *    sozinhas — o espectador nao liga a acao ao lugar da tela.
 * 2. **Narracao.** Nao ha audio. A legenda entra como DOM, entao ja sai
 *    gravada no proprio video, sem passo de edicao depois.
 *
 * Tudo vive num container `pointer-events: none`, para nunca roubar um clique
 * do app. As funcoes sao idempotentes: navegacao SPA preserva o overlay, e um
 * reload real o reinstala via `ensure()`.
 */

const OVERLAY_ID = '__mcra_demo_overlay';

/**
 * Injetado na pagina. Cria (uma vez) o cursor, a legenda e o batimento.
 *
 * O "batimento" e um elemento de 3px, praticamente invisivel, com animacao
 * infinita. Ele existe porque o `recordVideo` so produz quadro quando a pagina
 * repinta: nas pausas de leitura da legenda nada muda, o encoder nao gera
 * quadro, e o video sai mais curto que o tempo real (medimos 47s de video para
 * 59s de sessao). Isso desalinharia os timestamps do roteiro. Com a animacao
 * rodando, ha repintura continua e a duracao do video acompanha o relogio.
 */
function bootstrapOverlay(overlayId) {
  if (document.getElementById(overlayId)) return;

  const style = document.createElement('style');
  style.textContent = `
    #${overlayId} {
      position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    }
    #${overlayId} .cursor {
      position: absolute; top: 0; left: 0; width: 22px; height: 22px;
      margin: -2px 0 0 -2px;
      transition: transform 520ms cubic-bezier(.22,.61,.36,1);
      will-change: transform;
    }
    #${overlayId} .cursor svg { display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,.45)); }
    #${overlayId} .ring {
      position: absolute; top: 0; left: 0; width: 44px; height: 44px;
      margin: -22px 0 0 -22px; border-radius: 50%;
      border: 2px solid #E1251B; opacity: 0; transform: scale(.35);
    }
    #${overlayId} .ring.pulse { animation: mcraPulse 620ms ease-out; }
    @keyframes mcraPulse {
      0%   { opacity: .95; transform: scale(.35); }
      100% { opacity: 0;   transform: scale(1.15); }
    }
    #${overlayId} .caption {
      position: absolute; left: 50%; bottom: 44px; transform: translate(-50%, 14px);
      max-width: 940px; min-width: 420px;
      background: rgba(27,27,31,.95); color: #fff;
      border-left: 4px solid #E1251B; border-radius: 10px;
      padding: 16px 24px 17px; box-shadow: 0 18px 44px rgba(0,0,0,.42);
      opacity: 0; transition: opacity 320ms ease, transform 320ms ease;
    }
    #${overlayId} .caption.on { opacity: 1; transform: translate(-50%, 0); }
    #${overlayId} .caption.top { top: 96px; bottom: auto; }
    #${overlayId} .caption .t {
      font-size: 12px; letter-spacing: .13em; text-transform: uppercase;
      color: #F7A19C; font-weight: 700; margin-bottom: 7px;
    }
    #${overlayId} .caption .b { font-size: 20px; line-height: 1.42; font-weight: 500; }
    #${overlayId} .title-card {
      position: absolute; inset: 0; background: #1B1B1F; color: #fff;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 18px; opacity: 0; transition: opacity 520ms ease;
    }
    #${overlayId} .title-card.on { opacity: 1; }
    #${overlayId} .title-card .h { font-size: 46px; font-weight: 700; letter-spacing: -.02em; }
    #${overlayId} .title-card .s { font-size: 22px; color: #B9BAC2; max-width: 760px; text-align: center; line-height: 1.45; }
    #${overlayId} .title-card .rule { width: 64px; height: 4px; background: #E1251B; border-radius: 2px; }
    /* Ver nota sobre o batimento em bootstrapOverlay. */
    #${overlayId} .heartbeat {
      position: absolute; right: 0; bottom: 0; width: 3px; height: 3px;
      background: #1B1B1F; opacity: .012;
      animation: mcraHeartbeat 1s linear infinite;
    }
    @keyframes mcraHeartbeat {
      from { transform: translateX(0); }
      to   { transform: translateX(2px); }
    }
  `;
  document.head.appendChild(style);

  const root = document.createElement('div');
  root.id = overlayId;
  root.innerHTML = `
    <div class="cursor">
      <div class="ring"></div>
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <path d="M4 2.2 L4 18.4 L8.3 14.3 L11.1 20.3 L13.9 19 L11.2 13.1 L17 13.1 Z"
              fill="#fff" stroke="#1B1B1F" stroke-width="1.4" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="caption"><div class="t"></div><div class="b"></div></div>
    <div class="title-card"><div class="h"></div><div class="rule"></div><div class="s"></div></div>
    <div class="heartbeat"></div>
  `;
  document.body.appendChild(root);

  const cursor = root.querySelector('.cursor');
  const ring = root.querySelector('.ring');
  const caption = root.querySelector('.caption');
  const titleCard = root.querySelector('.title-card');

  // Começa fora de vista para o primeiro movimento não "nascer" no canto.
  cursor.style.transform = 'translate(-60px, -60px)';

  window.__mcraDemo = {
    moveCursor(x, y) {
      cursor.style.transform = `translate(${x}px, ${y}px)`;
    },
    pulse() {
      ring.classList.remove('pulse');
      void ring.offsetWidth; // reinicia a animacao
      ring.classList.add('pulse');
    },
    showCaption(title, body, posicao) {
      caption.querySelector('.t').textContent = title;
      caption.querySelector('.b').textContent = body;
      caption.classList.toggle('top', posicao === 'top');
      caption.classList.add('on');
    },
    hideCaption() {
      caption.classList.remove('on');
    },
    showTitle(heading, subtitle) {
      titleCard.querySelector('.h').textContent = heading;
      titleCard.querySelector('.s').textContent = subtitle;
      titleCard.classList.add('on');
    },
    hideTitle() {
      titleCard.classList.remove('on');
    },
  };
}

/** Garante o overlay na pagina atual (apos reload real, por exemplo). */
export async function ensure(page) {
  await page.evaluate(bootstrapOverlay, OVERLAY_ID);
}

/**
 * Registra o overlay para toda pagina futura e instala na atual.
 * Chamar uma vez, logo apos abrir a pagina.
 */
export async function install(page) {
  await page.addInitScript(
    ([fn, id]) => {
      const boot = new Function(`return ${fn}`)();
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => boot(id));
      } else {
        boot(id);
      }
    },
    [bootstrapOverlay.toString(), OVERLAY_ID],
  );
  await ensure(page);
}

/**
 * Mostra a legenda. `posicao: 'top'` para quando o rodape esconderia justamente
 * o que a cena precisa mostrar (o botao de login, por exemplo).
 */
export async function caption(page, title, body, { posicao = 'bottom' } = {}) {
  await ensure(page);
  await page.evaluate(
    ([t, b, p]) => window.__mcraDemo.showCaption(t, b, p),
    [title, body, posicao],
  );
}

export async function clearCaption(page) {
  await ensure(page);
  await page.evaluate(() => window.__mcraDemo.hideCaption());
}

export async function titleCard(page, heading, subtitle) {
  await ensure(page);
  await page.evaluate(
    ([h, s]) => window.__mcraDemo.showTitle(h, s),
    [heading, subtitle],
  );
}

export async function hideTitleCard(page) {
  await ensure(page);
  await page.evaluate(() => window.__mcraDemo.hideTitle());
}

/** Move o cursor desenhado E o mouse real para o centro do elemento. */
export async function moveTo(page, locator, { settle = 620 } = {}) {
  const target = typeof locator === 'string' ? page.locator(locator) : locator;
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) throw new Error(`Elemento sem bounding box: ${target}`);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await ensure(page);
  await page.evaluate(([px, py]) => window.__mcraDemo.moveCursor(px, py), [x, y]);
  await page.mouse.move(x, y);
  await page.waitForTimeout(settle);
  return { x, y };
}

/** Move ate o elemento, pulsa o anel e clica de verdade. */
export async function click(page, locator, opts = {}) {
  const { x, y } = await moveTo(page, locator, opts);
  await page.evaluate(() => window.__mcraDemo.pulse());
  await page.waitForTimeout(180);
  await page.mouse.click(x, y);
  await page.waitForTimeout(opts.after ?? 420);
}

/** Clica no campo e digita em ritmo humano. */
export async function type(page, locator, text, { delay = 85 } = {}) {
  await click(page, locator, { after: 120 });
  const target = typeof locator === 'string' ? page.locator(locator) : locator;
  await target.type(text, { delay });
  await page.waitForTimeout(280);
}

// --- Ritmo -----------------------------------------------------------------
//
// As pausas de leitura sao dimensionadas pelo tamanho da legenda, o que serve
// para um video mudo. Com narracao por cima, quem manda no tempo e a voz: cada
// cena precisa durar exatamente o trecho de audio que fala dela.
//
// `fator` estica ou encolhe TODAS as pausas de uma cena de uma vez. Ele nao e
// escolhido a mao: `record.mjs` calcula por cena a partir de uma gravacao de
// calibracao (ver `calibrar()` la). Esperas mecanicas — aguardar a UI assentar
// depois de um clique — continuam em `waitForTimeout` cru, porque encurta-las
// quebraria a cena em vez de apenas apressa-la.

const PAUSA_MINIMA_MS = 900;

let fator = 1;
let pausasEscaladasMs = 0;
let pausasBaseMs = 0;

/** Zera os acumuladores e define o fator de ritmo da proxima cena. */
export function iniciarCena(novoFator = 1) {
  fator = novoFator;
  pausasEscaladasMs = 0;
  pausasBaseMs = 0;
}

/**
 * Tempo que a cena passou em pausas, nas duas medidas que a calibracao precisa.
 *
 * `escalada` e o que de fato decorreu nesta gravacao; serve para separar o
 * tempo de mecanica (`duracao - escalada`). `base` e o que teria decorrido com
 * fator 1 — e sobre ela que o proximo fator sera aplicado. Guardar so a
 * escalada realimentaria a calibracao com o proprio ajuste e o fator
 * convergiria para 1, desfazendo o encolhimento das cenas que precisam dele.
 */
export function gastoEmPausas() {
  return { escalada: pausasEscaladasMs, base: pausasBaseMs };
}

/** Espera escalavel: usar para SEGURAR uma tela, nao para aguardar a UI. */
export async function pausa(page, ms) {
  const espera = Math.max(PAUSA_MINIMA_MS, Math.round(ms * fator));
  pausasBaseMs += ms;
  pausasEscaladasMs += espera;
  await page.waitForTimeout(espera);
}

/** Legenda + pausa para leitura, proporcional ao tamanho do texto. */
export async function beat(page, title, body, { extra = 0, posicao } = {}) {
  await caption(page, title, body, { posicao });
  const leitura = Math.min(9000, 1500 + body.length * 52);
  await pausa(page, leitura + extra);
}
