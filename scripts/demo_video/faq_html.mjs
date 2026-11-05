// Gera o FAQ em HTML unico (CSS e GIFs embutidos) para anexar ao convite do treinamento.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Cores de web/src/styles/tokens.css.
const CSS = `
:root { --red:#E1251B; --red-lt:#FDE8E7; --ink:#1B1B1F; --graphite:#5A5C66; --canvas:#F7F7F8; --line:#E4E4E7; }
* { box-sizing: border-box; }
body { margin:0; background:var(--canvas); color:var(--ink); font:16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:760px; margin:0 auto; padding:32px 20px 64px; }
h1 { margin:0 0 4px; font-size:28px; color:var(--red); }
.sub { margin:0 0 24px; color:var(--graphite); }
details { background:#fff; border:1px solid var(--line); border-radius:10px; margin:0 0 10px; }
summary { cursor:pointer; padding:14px 18px; font-weight:600; }
details[open] summary { color:var(--red); border-bottom:1px solid var(--line); background:var(--red-lt); border-radius:10px 10px 0 0; }
.corpo { padding:8px 18px 18px; }
ol { padding-left:22px; color:var(--graphite); }
img { display:block; max-width:100%; margin-top:12px; border:1px solid var(--line); border-radius:8px; }
`;

function renderItem(item, lerGif) {
  const passos = item.passos.map((p) => `<li>${esc(p)}</li>`).join('');
  const buf = item.gif ? lerGif(item.gif) : null;
  const img = buf
    ? `<img alt="${esc(item.pergunta)}" src="data:image/gif;base64,${buf.toString('base64')}">`
    : '';
  return `<details><summary>${esc(item.pergunta)}</summary><div class="corpo"><ol>${passos}</ol>${img}</div></details>`;
}

export function renderFaqHtml(itens, lerGif) {
  return `<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCRA · Perguntas frequentes</title><style>${CSS}</style></head>
<body><main><h1>MCRA · Perguntas frequentes</h1><p class="sub">Clique na pergunta para ver o passo a passo.</p>
${itens.map((i) => renderItem(i, lerGif)).join('\n')}
</main></body></html>
`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const itens = JSON.parse(readFileSync(join(RAIZ, 'web/src/ajuda/faq.json'), 'utf8'));
  const lerGif = (nome) => {
    const caminho = join(RAIZ, 'web/public/ajuda', nome);
    if (existsSync(caminho)) return readFileSync(caminho);
    console.warn(`aviso: GIF ausente, seguindo so com o texto: ${caminho}`);
    return null;
  };
  const saida = join(RAIZ, 'data/faq/FAQ-MCRA.html');
  const html = renderFaqHtml(itens, lerGif);
  mkdirSync(dirname(saida), { recursive: true });
  writeFileSync(saida, html);
  console.log(`${saida} (${(Buffer.byteLength(html) / 1024).toFixed(1)} KB)`);
}
