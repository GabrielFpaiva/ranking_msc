import test from 'node:test';
import assert from 'node:assert/strict';
import { renderFaqHtml } from './faq_html.mjs';

const item = (i, extra = {}) => ({ id: `p${i}`, pergunta: `Pergunta ${i}?`, passos: ['um', 'dois'], ...extra });

test('gera uma secao por pergunta', () => {
  const itens = Array.from({ length: 12 }, (_, i) => item(i));
  const html = renderFaqHtml(itens, () => null);
  assert.equal(html.match(/<details/g).length, 12);
  for (const it of itens) assert.ok(html.includes(`<summary>${it.pergunta}</summary>`));
});

test('embute gif como data uri', () => {
  const html = renderFaqHtml([item(1, { gif: 'a.gif' })], () => Buffer.from('GIF89a'));
  assert.ok(html.includes('src="data:image/gif;base64,R0lGODlh'));
});

test('sem gif ou gif ausente nao gera img', () => {
  const html = renderFaqHtml([item(1), item(2, { gif: 'x.gif' })], () => null);
  assert.ok(!html.includes('<img'));
});

test('nao referencia nada externo', () => {
  const html = renderFaqHtml([item(1, { gif: 'a.gif' })], () => Buffer.from('GIF89a'));
  assert.doesNotMatch(html, /(src|href)="https?:/);
});

test('escapa html do conteudo', () => {
  const html = renderFaqHtml([item(1, { pergunta: 'A < B & "C"' })], () => null);
  assert.ok(html.includes('A &lt; B &amp; &quot;C&quot;'));
});
