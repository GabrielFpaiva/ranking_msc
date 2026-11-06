/**
 * As cenas dos GIFs do FAQ (`web/public/ajuda/<id>.gif`), uma por pergunta.
 *
 * Cada GIF mostra um fluxo curto (8 a 25 s). As legendas seguem os passos de
 * `web/src/ajuda/faq.json`: ao mudar um passo la, confira a legenda aqui.
 * Onde a cena do video de demonstracao ja cabe (envio, comparar), ela e
 * reaproveitada; as demais sao versoes curtas, com o texto do FAQ.
 */

import { beat, caption, clearCaption, click, moveTo, pausa, type } from './overlay.mjs';
import { comparar, execucao } from './scenes.mjs';

const nav = (label) => `.samid-sidebar a:has-text("${label}")`;
const fechar = 'button[aria-label="Fechar"]';

async function loginESair(page, { usuario, senha }) {
  await beat(page, 'Entrar', 'Digite seu e-mail e sua senha e clique em Entrar.');
  await type(page, '.samid-login-input[type="text"]', usuario);
  await type(page, '.samid-login-input[type="password"]', senha, { delay: 70 });
  await click(page, '.samid-login-submit');
  await page.waitForURL('**/inicio', { timeout: 15000 });
  await beat(page, 'Pronto', 'A tela Início abre. Pronto, você já está dentro.');
  await click(page, '.samid-logout', { after: 1200 });
  await beat(page, 'Sair', 'Para sair, clique em Sair, no canto de baixo do menu à esquerda.');
  await clearCaption(page);
}

async function score(page) {
  await moveTo(page, '.samid-score-card');
  await beat(page, 'Score', 'O score vai de 0 a 100. A letra ao lado é a banda, de A até E.');
  await moveTo(page, '.samid-bars');
  await beat(page, 'Regras mais violadas', 'Logo abaixo ficam as regras mais violadas. Comece por elas.');
  await clearCaption(page);
}

async function pendencias(page) {
  await click(page, nav('Pendências'), { after: 1400 });
  await click(page, '.samid-check:has-text("ERRO") input', { after: 1200 });
  await beat(page, 'Filtros', 'Filtre por severidade. ERRO é o mais grave: resolva primeiro.');
  await type(page, '.samid-filter-group:has-text("Regra") input.samid-input', 'R020');
  await beat(page, 'Filtrar por regra', 'Ou digite uma regra, por exemplo R020.');
  await click(page, '.samid-btn:has-text("Limpar filtros")', { after: 1200 });
  await beat(page, 'Limpar filtros', 'Clique em Limpar filtros para voltar à lista completa.');
  await clearCaption(page);
}

async function regras(page) {
  await click(page, nav('Regras'), { after: 1400 });
  await type(page, 'input[aria-label="Buscar regras"]', 'R054');
  await beat(page, 'Buscar', 'Use a busca para achar a regra por número, nome ou dimensão.');
  await click(page, 'table.samid-table tbody tr >> nth=0', { after: 1200 });
  await beat(
    page,
    'Painel da regra',
    'O painel mostra o nome, a dimensão, a descrição e o histórico por mês.',
  );
  await click(page, fechar);
  await clearCaption(page);
}

async function conta(page) {
  await click(page, nav('Pendências'), { after: 1400 });
  await caption(page, 'Abrir a conta', 'Em Pendências, clique no número da conta.');
  await click(page, 'table.samid-table tbody tr:nth-child(2) td.mono >> nth=0', { after: 1200 });
  await beat(page, 'Detalhes da conta', 'Abre um painel lateral com os dados daquela conta.');
  await caption(page, 'Fechar', 'Para fechar, clique fora do painel ou no botão de fechar.');
  await click(page, fechar, { after: 1200 });
  await clearCaption(page);
}

async function contas(page) {
  await click(page, nav('Caixa'), { after: 1600 });
  await beat(page, 'Caixa', 'Caixa e equivalentes: saldo inicial, movimento do mês e saldo final.');
  await click(page, nav('Passivos'), { after: 1600 });
  await beat(page, 'Passivos', 'Passivo circulante e não circulante: confira obrigações e saldos.');
  await click(page, nav('Superávit'), { after: 1600 });
  await beat(
    page,
    'Superávit',
    'Resultado financeiro por Fonte de Recursos. A área contábil valida antes de usar.',
  );
  await clearCaption(page);
}

async function entregas(page) {
  await click(page, nav('Entregas'), { after: 1800 });
  await moveTo(page, 'select[aria-label="Trocar exercício"]');
  await page.selectOption('select[aria-label="Trocar exercício"]', '2025');
  await beat(page, 'Exercício', 'Escolha o exercício no topo da tela.');
  await page.waitForSelector('[data-testid="resumo-total"]', { timeout: 30000 }).catch(() => {});
  await moveTo(page, '[data-testid="resumo-total"]');
  await beat(page, 'Resumo', 'O resumo mostra quantas entregas foram feitas, homologadas e retificadas.');
  await moveTo(page, 'table.samid-table >> nth=0');
  await beat(page, 'Como estamos', 'A tabela lista cada entrega, com status, período e data.');
  await clearCaption(page);
}

async function exportacoes(page) {
  await beat(page, 'Exportar', 'Na tela Início, depois de processar a MSC do mês.');
  await click(page, '.samid-topbar-actions .samid-btn:has-text("Excel")', { after: 2400 });
  await beat(page, 'Excel', 'O Excel traz o resumo, a lista de pendências e as evidências.');
  await click(page, '.samid-topbar-actions .samid-btn:has-text("Exportar PDF")', { after: 2400 });
  await beat(page, 'PDF', 'O PDF é a versão de uma página, boa para reunião.');
  await pausa(page, 600);
  await clearCaption(page);
}

/** Um item por pergunta do FAQ com GIF. `logado: false` comeca na tela de login. */
export const FAQ_CENAS = [
  { id: 'login', fn: loginESair, logado: false },
  { id: 'enviar-msc', fn: execucao, logado: true },
  { id: 'score', fn: score, logado: true },
  { id: 'pendencias', fn: pendencias, logado: true },
  { id: 'regras', fn: regras, logado: true },
  { id: 'conta', fn: conta, logado: true },
  { id: 'contas', fn: contas, logado: true },
  { id: 'comparar', fn: comparar, logado: true },
  { id: 'entregas', fn: entregas, logado: true },
  { id: 'exportacoes', fn: exportacoes, logado: true },
];
