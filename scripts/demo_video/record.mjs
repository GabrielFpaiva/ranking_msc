/**
 * Grava o video de demonstracao do MCRA.
 *
 * Dirige o app real (front + back rodando localmente) com Playwright e grava a
 * sessao. O que sai daqui nao e um slideshow de prints: e a aplicacao sendo
 * usada, incluindo uma execucao verdadeira do motor sobre um CSV MSC real.
 *
 * Uso:
 *   cd scripts/demo_video && npm install && npx playwright install chromium
 *   node record.mjs
 *
 * Variaveis de ambiente (todas opcionais):
 *   BASE_URL   endereco do front            (padrao http://localhost:5173)
 *   CSV        CSV MSC a processar          (padrao ref/amostras/msc_2026-01.csv)
 *   USUARIO    login                        (padrao demo)
 *   SENHA      senha                        (padrao demo2026)
 *   OUT        diretorio de saida           (padrao data/demo_video)
 *   CENAS      subconjunto separado por virgula, para ajustar um trecho so
 *   NARRACAO   mp3 da narracao; quando presente, sai tambem a versao narrada
 *
 * Ritmo: as cenas duram o que o audio da narracao pede, conforme
 * `tempos_narracao.json` (duracao de cada trecho, medida no proprio mp3). A
 * primeira execucao mede as cenas e grava `calibracao.json`; a segunda ja sai
 * no ritmo certo. Apagar `calibracao.json` forca nova medicao.
 *
 * Saidas em OUT/: `mcra-demo.mp4` (mudo), `mcra-demo-narrado.mp4` (com voz),
 * `mcra-demo.webm` e `cenas.json` (tempo de cada cena, alvo contra realizado).
 */

import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { chromium } from 'playwright';

import { gastoEmPausas, iniciarCena, install } from './overlay.mjs';
import { ROTEIRO } from './scenes.mjs';

const execFileAsync = promisify(execFile);

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '../..');

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173';
const CSV = path.resolve(RAIZ, process.env.CSV ?? 'ref/amostras/msc_2026-01.csv');
const OUT = path.resolve(RAIZ, process.env.OUT ?? 'data/demo_video');
const USUARIO = process.env.USUARIO ?? 'demo';
const SENHA = process.env.SENHA ?? 'demo2026';

const LARGURA = 1600;
const ALTURA = 900;

const NARRACAO = process.env.NARRACAO
  ? path.resolve(RAIZ, process.env.NARRACAO)
  : null;
const TEMPOS = path.join(AQUI, 'tempos_narracao.json');
const CALIBRACAO = path.join(AQUI, 'calibracao.json');

/**
 * Calcula o fator de ritmo de cada cena.
 *
 * Uma cena gasta tempo em duas coisas: mecanica (digitar, clicar, esperar a UI)
 * e pausa (segurar a tela para ser lida). So a segunda pode esticar ou encolher
 * — apressar a mecanica quebraria a cena. Entao, para uma cena durar `alvo`:
 *
 *     fator = (alvo - mecanica) / pausas
 *
 * `mecanica` e `pausas` vem de uma gravacao anterior (`calibracao.json`), que o
 * proprio script grava. Sem esse arquivo o fator e 1 e a passada serve
 * justamente para produzi-lo.
 */
function fatoresDeRitmo(alvos, calibracao) {
  const fatores = {};
  for (const [cena, alvoS] of Object.entries(alvos)) {
    const cal = calibracao?.[cena];
    if (!cal || !cal.pausasBaseMs) {
      fatores[cena] = 1;
      continue;
    }
    const bruto = (alvoS * 1000 - cal.mecanicaMs) / cal.pausasBaseMs;
    // Limites largos: a abertura precisa de ~4x, e nenhuma cena deve inverter.
    fatores[cena] = Math.min(8, Math.max(0.2, bruto));
  }
  return fatores;
}

async function juntarAudio(video, audio, saida, atrasoS) {
  // O video comeca antes da primeira cena (carga da pagina). O audio entra
  // atrasado desse tanto para a narracao cair junto com o cartao de abertura.
  await execFileAsync('ffmpeg', [
    '-y',
    '-i', video,
    '-itsoffset', atrasoS.toFixed(3),
    '-i', audio,
    '-map', '0:v:0',
    '-map', '1:a:0',
    '-c:v', 'copy',
    '-c:a', 'aac',
    '-b:a', '160k',
    '-movflags', '+faststart',
    saida,
  ]);
}

/** mm:ss a partir de milissegundos — o formato usado no roteiro. */
function marca(ms) {
  const total = Math.round(ms / 1000);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

async function converterParaMp4(webm, mp4) {
  // O ffmpeg que acompanha o Playwright so tem VP8/WebM. Para um arquivo que
  // abra em PowerPoint e WhatsApp e preciso H.264, entao usamos o ffmpeg do
  // sistema. Sem ele, o .webm ainda fica valido.
  try {
    await execFileAsync('ffmpeg', [
      '-y',
      '-i', webm,
      '-c:v', 'libx264',
      '-preset', 'slow',
      '-crf', '20',
      '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart',
      mp4,
    ]);
    return true;
  } catch (err) {
    console.warn(`\n! Conversao para mp4 falhou (${err.message.split('\n')[0]}).`);
    console.warn('  O .webm continua utilizavel. Para o mp4: brew install ffmpeg');
    return false;
  }
}

async function main() {
  const selecionadas = process.env.CENAS
    ? ROTEIRO.filter((c) => process.env.CENAS.split(',').includes(c.id))
    : ROTEIRO;

  await rm(OUT, { recursive: true, force: true });
  await mkdir(OUT, { recursive: true });
  const dirVideo = path.join(OUT, '.raw');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: LARGURA, height: ALTURA },
    recordVideo: { dir: dirVideo, size: { width: LARGURA, height: ALTURA } },
    acceptDownloads: true,
    locale: 'pt-BR',
    timezoneId: 'America/Fortaleza',
    reducedMotion: 'no-preference',
  });

  const page = await context.newPage();
  // A gravacao comeca aqui, nao na primeira cena. Os timestamps do roteiro
  // precisam ser medidos deste instante, senao ficam adiantados em relacao ao
  // video pelo tempo de carga inicial da pagina.
  const t0 = Date.now();

  // Os relatorios exportados vao para junto do video: no fim da gravacao eles
  // sao a prova de que os botoes de export fizeram algo de verdade.
  const baixados = [];
  page.on('download', async (download) => {
    const destino = path.join(OUT, 'exportados', download.suggestedFilename());
    await mkdir(path.dirname(destino), { recursive: true });
    await download.saveAs(destino);
    baixados.push(path.basename(destino));
  });

  const ctx = { usuario: USUARIO, senha: SENHA, csv: CSV };
  const marcacoes = [];
  let duracao = '00:00';

  // Alvos de duracao por cena, medidos no audio da narracao. Sem o arquivo, o
  // video roda no ritmo proprio (modo mudo, como era antes da narracao existir).
  const tempos = JSON.parse(await readFile(TEMPOS, 'utf-8'));
  const alvos = Object.fromEntries(tempos.cenas.map((c) => [c.cena, c.alvo]));
  const calibracaoAnterior = existsSync(CALIBRACAO)
    ? JSON.parse(await readFile(CALIBRACAO, 'utf-8'))
    : null;
  const fatores = fatoresDeRitmo(alvos, calibracaoAnterior);
  const calibracao = {};
  if (!calibracaoAnterior) {
    console.log('  (sem calibracao — esta passada mede as cenas; rode de novo para o ritmo final)\n');
  }

  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await install(page);
  await page.waitForTimeout(600);

  // Instante em que a primeira cena comeca: e o ponto onde o audio deve entrar.
  let offsetAudioMs = null;

  try {
    for (const cena of selecionadas) {
      const inicio = Date.now() - t0;
      if (offsetAudioMs === null) offsetAudioMs = inicio;
      const fator = fatores[cena.id] ?? 1;
      process.stdout.write(`  ${marca(inicio)}  ${cena.id} (×${fator.toFixed(2)}) … `);

      iniciarCena(fator);
      await cena.fn(page, ctx);
      const pausas = gastoEmPausas();

      // Sobrou tempo para o alvo? Segura a tela onde ela esta. Isso absorve o
      // erro do fator e impede que o atraso de uma cena empurre as seguintes.
      const alvoMs = (alvos[cena.id] ?? 0) * 1000;
      const gastoMs = Date.now() - t0 - inicio;
      const sobra = alvoMs - gastoMs;
      if (sobra > 250) await page.waitForTimeout(sobra);

      const fim = Date.now() - t0;
      calibracao[cena.id] = {
        duracaoMs: gastoMs,
        mecanicaMs: gastoMs - pausas.escalada,
        pausasBaseMs: pausas.base,
      };
      marcacoes.push({
        cena: cena.id,
        inicio: marca(inicio),
        fim: marca(fim),
        alvoS: alvos[cena.id] ?? null,
        realS: Number(((fim - inicio) / 1000).toFixed(1)),
      });
      const desvio = (fim - inicio) / 1000 - (alvos[cena.id] ?? 0);
      const aviso = Math.abs(desvio) > 1.5 ? `  <-- ${desvio > 0 ? '+' : ''}${desvio.toFixed(1)}s` : '';
      console.log(`${((fim - inicio) / 1000).toFixed(1)}s / alvo ${alvos[cena.id] ?? '—'}s${aviso}`);
    }
  } catch (err) {
    console.error(`\nFALHOU: ${err.message}`);
    await page.screenshot({ path: path.join(OUT, 'falha.png') }).catch(() => {});
    throw err;
  } finally {
    // Medir aqui, antes do close e da conversao: o que interessa e a duracao
    // do video, nao o tempo total do script.
    duracao = marca(Date.now() - t0);
    // O arquivo de video so e finalizado no close do contexto.
    await context.close();
    await browser.close();
  }

  const bruto = (await readdir(dirVideo)).find((f) => f.endsWith('.webm'));
  const webm = path.join(OUT, 'mcra-demo.webm');
  await rename(path.join(dirVideo, bruto), webm);
  await rm(dirVideo, { recursive: true, force: true });

  const mp4 = path.join(OUT, 'mcra-demo.mp4');
  const temMp4 = await converterParaMp4(webm, mp4);

  await writeFile(CALIBRACAO, `${JSON.stringify(calibracao, null, 2)}\n`);
  await writeFile(
    path.join(OUT, 'cenas.json'),
    `${JSON.stringify({ duracao, cenas: marcacoes, exportados: baixados }, null, 2)}\n`,
  );

  let final = temMp4 ? mp4 : webm;
  if (NARRACAO && temMp4) {
    const comAudio = path.join(OUT, 'mcra-demo-narrado.mp4');
    await juntarAudio(mp4, NARRACAO, comAudio, offsetAudioMs / 1000);
    final = comAudio;
  }

  console.log(`\nDuracao: ${duracao}`);
  console.log(`Video:   ${final}`);
  if (baixados.length) console.log(`Exports: ${baixados.join(', ')}`);
  console.log(`Cenas:   ${path.join(OUT, 'cenas.json')}`);
}

await main();
