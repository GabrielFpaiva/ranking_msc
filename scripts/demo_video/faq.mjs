/**
 * Grava os GIFs do FAQ em `web/public/ajuda/<id>.gif`.
 *
 * Mesmo esquema do `record.mjs` (front + back rodando localmente), mas uma
 * gravacao curta por pergunta, em vez de um video unico.
 *
 * Uso:
 *   make dev-backend & make dev-frontend & make faq-gifs
 *
 * Variaveis de ambiente (opcionais): BASE_URL, USUARIO, SENHA, como no
 * `record.mjs`; CENAS para gravar so alguns ids (separados por virgula).
 *
 * Sai com codigo 1 se algum GIF passar de 3 MB ou o total passar de 30 MB.
 */

import { execFile } from 'node:child_process';
import { mkdir, readdir, rm, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { chromium } from 'playwright';

import { iniciarCena, install } from './overlay.mjs';
import { FAQ_CENAS } from './faq_scenes.mjs';
import { execucao, login } from './scenes.mjs';

const execFileAsync = promisify(execFile);

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '../..');

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173';
const USUARIO = process.env.USUARIO ?? 'demo';
const SENHA = process.env.SENHA ?? 'demo2026';

const LARGURA = 1600;
const ALTURA = 900;
const RAW = path.join(RAIZ, 'data/faq/.raw');
const SAIDA = path.join(RAIZ, 'web/public/ajuda');
const CSV = (comp) => path.join(RAIZ, `ref/amostras/msc_${comp}.csv`);

const LIMITE_GIF = 3 * 1024 * 1024;
const LIMITE_TOTAL = 30 * 1024 * 1024;
// fps=10/scale=1000 deu 34 MB no total; este e o ajuste previsto no plano.
const FILTRO = 'fps=8,scale=900:-1:flags=lanczos,split[a][b];'
  + '[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer';

const opcoesContexto = {
  viewport: { width: LARGURA, height: ALTURA },
  acceptDownloads: true,
  locale: 'pt-BR',
  timezoneId: 'America/Fortaleza',
  reducedMotion: 'no-preference',
};

/** Login e duas execucoes (para Comparar ter dois meses), sem gravar. */
async function preparar(browser) {
  const context = await browser.newContext(opcoesContexto);
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await install(page);
  await login(page, { usuario: USUARIO, senha: SENHA });
  for (const comp of ['2025-12', '2026-01']) {
    await execucao(page, { csv: CSV(comp) });
  }
  const estado = await context.storageState();
  await context.close();
  return estado;
}

async function gravar(browser, cena, estado) {
  const dir = path.join(RAW, cena.id);
  await rm(dir, { recursive: true, force: true });
  const context = await browser.newContext({
    ...opcoesContexto,
    ...(cena.logado ? { storageState: estado } : {}),
    recordVideo: { dir, size: { width: LARGURA, height: ALTURA } },
  });
  const page = await context.newPage();
  try {
    await page.goto(`${BASE_URL}${cena.logado ? '/inicio' : '/login'}`, { waitUntil: 'networkidle' });
    await install(page);
    await page.waitForTimeout(600);
    iniciarCena(1);
    await cena.fn(page, { usuario: USUARIO, senha: SENHA, csv: CSV('2026-01') });
  } catch (err) {
    await page.screenshot({ path: path.join(RAW, `${cena.id}-falha.png`) }).catch(() => {});
    throw err;
  } finally {
    await context.close();
  }
  const webm = (await readdir(dir)).find((f) => f.endsWith('.webm'));
  const gif = path.join(SAIDA, `${cena.id}.gif`);
  await execFileAsync('ffmpeg', ['-y', '-i', path.join(dir, webm), '-vf', FILTRO, gif]);
  return (await stat(gif)).size;
}

async function main() {
  const selecionadas = process.env.CENAS
    ? FAQ_CENAS.filter((c) => process.env.CENAS.split(',').includes(c.id))
    : FAQ_CENAS;
  await mkdir(SAIDA, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const tamanhos = {};
  try {
    console.log('  preparando (login + MSC 2025-12 e 2026-01)…');
    const estado = await preparar(browser);
    for (const cena of selecionadas) {
      process.stdout.write(`  ${cena.id} … `);
      const t0 = Date.now();
      tamanhos[cena.id] = await gravar(browser, cena, estado);
      console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s, ${mb(tamanhos[cena.id])}`);
    }
  } finally {
    await browser.close();
  }

  const total = Object.values(tamanhos).reduce((a, b) => a + b, 0);
  const grandes = Object.entries(tamanhos).filter(([, t]) => t > LIMITE_GIF);
  console.log(`\nTotal: ${mb(total)} em ${SAIDA}`);
  if (grandes.length || total > LIMITE_TOTAL) {
    console.error('\nGIFs acima do limite (3 MB cada, 30 MB no total):');
    for (const [id, t] of Object.entries(tamanhos)) console.error(`  ${id}.gif  ${mb(t)}`);
    console.error('Ajuste o FILTRO: primeiro fps=8, depois scale=900.');
    process.exit(1);
  }
}

const mb = (bytes) => `${(bytes / 1024 / 1024).toFixed(2)} MB`;

await main();
