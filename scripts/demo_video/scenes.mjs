/**
 * As cenas do video de demonstracao, na ordem em que aparecem.
 *
 * Cada cena e uma funcao `async (page, ctx)` independente: recebe a pagina ja
 * autenticada (exceto `abertura` e `login`) e devolve o app num estado que a
 * cena seguinte possa assumir. Assim da para gravar so um trecho durante o
 * ajuste, sem rodar o video inteiro.
 *
 * O texto das legendas aqui e a fonte da verdade do roteiro em
 * `doc/roteiro_video_demo.md` — ao mudar um, mude o outro.
 */

import {
  beat,
  caption,
  clearCaption,
  click,
  hideTitleCard,
  moveTo,
  pausa,
  titleCard,
  type,
} from './overlay.mjs';

const nav = (label) => `.samid-sidebar a:has-text("${label}")`;

export async function abertura(page) {
  await titleCard(
    page,
    'MCRA · PMJP',
    'Validação da Matriz de Saldos Contábeis antes do envio ao Siconfi — '
      + '78 regras aplicadas ao arquivo do mês, com o resultado explicado conta a conta.',
  );
  await pausa(page, 7000);
  await hideTitleCard(page);
  await page.waitForTimeout(900);
}

export async function login(page, { usuario, senha }) {
  await beat(
    page,
    'Acesso',
    'O acesso é por usuário e senha. A sessão expira sozinha, e nenhuma tela abre sem ela.',
  );
  await type(page, '.samid-login-input[type="text"]', usuario);
  await type(page, '.samid-login-input[type="password"]', senha, { delay: 70 });
  await click(page, '.samid-login-submit');
  await page.waitForURL('**/inicio', { timeout: 15000 });
  await page.waitForTimeout(1400);
  await clearCaption(page);
}

export async function execucao(page, { csv }) {
  await beat(
    page,
    'Importar a MSC',
    'O trabalho começa aqui: o mesmo CSV que seria enviado ao Siconfi entra no sistema primeiro.',
  );

  const chooser = page.waitForEvent('filechooser');
  await click(page, '.samid-drop', { after: 200 });
  await (await chooser).setFiles(csv);

  await caption(
    page,
    'Motor rodando',
    'As 78 regras são aplicadas ao arquivo inteiro. Sem planilha paralela e sem conferência manual.',
  );
  await page.waitForSelector('.samid-drop-title:has-text("Processando")', { timeout: 8000 }).catch(() => {});
  await page.waitForSelector('.samid-kv', { timeout: 120000 });
  await page.waitForTimeout(900);

  await moveTo(page, '.samid-kv');
  await beat(
    page,
    'Resultado da execução',
    'Cerca de dez segundos depois: competência reconhecida, status da execução e o total de pendências encontradas.',
  );
  await clearCaption(page);
}

export async function score(page) {
  await moveTo(page, '.samid-score-card');
  await beat(
    page,
    'Score de conformidade',
    'A nota de 0 a 100 e a banda de A a E resumem a competência num número que dá para acompanhar mês a mês.',
  );

  await moveTo(page, '.samid-score-breakdown');
  await beat(
    page,
    'Cinco dimensões',
    'A nota se decompõe em Estrutura, Fechamento, IC/Domínio, PCASP/Completude e Temporal — dá para ver onde a pontuação está sendo perdida.',
  );

  await beat(
    page,
    'Do número ao caso concreto',
    'Cada dimensão é clicável: leva direto às pendências que a derrubaram.',
  );

  await moveTo(page, '.samid-bars');
  await beat(
    page,
    'As regras que mais pesaram',
    'As oito regras com mais ocorrências na competência, da mais frequente para a menos.',
  );

  await click(page, '.samid-bar-row >> nth=0');
  await beat(
    page,
    'O que a regra verifica',
    'Abrindo a regra: o que ela exige, em que norma se apoia e como se comportou nos meses anteriores.',
    { extra: 1200 },
  );
  await click(page, 'button[aria-label="Fechar"]');
  await clearCaption(page);
}

export async function pendencias(page) {
  await click(page, nav('Pendências'), { after: 1400 });
  await beat(
    page,
    'Pendências',
    'A lista completa do que o motor encontrou: a regra, a conta, o valor esperado e o encontrado.',
  );

  await moveTo(page, '.samid-filter-rail');
  await beat(
    page,
    'Separar o que trava do que avisa',
    'ERRO é o que impede um envio limpo. ALERTA é o que merece olhar. O filtro deixa atacar primeiro o que trava.',
  );
  await click(page, '.samid-check:has-text("ERRO") input', { after: 1600 });

  await beat(
    page,
    'Filtrar por regra ou conta',
    'Também dá para isolar uma regra específica ou um prefixo de conta, quando o setor já sabe o que procura.',
  );
  await type(page, '.samid-filter-group:has-text("Regra") input.samid-input', 'R054');
  await pausa(page, 1800);

  await click(page, '.samid-btn:has-text("Limpar filtros")', { after: 1500 });

  await beat(
    page,
    'Da linha para o detalhe',
    'Clicando na conta, o sistema mostra o saldo, a composição e todas as pendências que recaem sobre ela.',
  );
  await click(page, 'table.samid-table tbody tr:nth-child(2) td.mono >> nth=0', { after: 1500 });
  await pausa(page, 2600);
  await click(page, 'button[aria-label="Fechar"]');
  await clearCaption(page);
}

export async function regras(page) {
  await click(page, nav('Regras'), { after: 1500 });
  await beat(
    page,
    'Catálogo das 78 regras',
    'Toda regra aplicada está documentada aqui, com a dimensão a que pertence e o que verifica.',
  );

  // O heatmap vem recolhido por padrao; a cena precisa abri-lo.
  await click(page, '.samid-heat-legend-row button:has-text("Mostrar")', { after: 1400 });
  // As primeiras regras do eixo (R001…) passam em todas as competencias: o topo
  // do mapa e um retangulo cinza. Descer ate R054, a de maior incidencia, para
  // que a legenda sobre "onde a regra disparou" tenha o que apontar.
  await moveTo(page, '.samid-heat-row:has(b:text-is("R054"))');
  await beat(
    page,
    'Regras × competências',
    'O mapa de calor mostra em que meses cada regra disparou — o que é ponto fora da curva e o que é problema recorrente.',
  );

  await type(page, 'input[aria-label="Buscar regras"]', 'fonte de recurso');
  await pausa(page, 2400);
  await clearCaption(page);
}

export async function exportacoes(page) {
  await click(page, nav('Início'), { after: 1500 });
  await beat(
    page,
    'Levar o resultado para fora',
    'Duas saídas, dois públicos: a planilha para o setor contábil trabalhar, e o PDF de uma página para a gestão.',
  );

  await click(page, '.samid-topbar-actions .samid-btn:has-text("Excel")', { after: 2600 });
  await caption(
    page,
    'Excel de pendências',
    'A lista completa, filtrável, para distribuir entre os responsáveis por cada correção.',
  );
  await pausa(page, 3400);

  await click(page, '.samid-topbar-actions .samid-btn:has-text("Exportar PDF")', { after: 3000 });
  await beat(
    page,
    'PDF executivo',
    'Uma página com score, dimensões e recomendações — no padrão visual da Prefeitura.',
  );
  await clearCaption(page);
}

export async function entregas(page) {
  await click(page, nav('Entregas'), { after: 2200 });
  await beat(
    page,
    'A dimensão que ninguém acompanhava',
    'O Ranking do Tesouro avalia quatro dimensões. Esta é a Gestão da Informação: prazo de entrega e número de retificações.',
  );

  // A tela abre no exercicio corrente (2026), que ainda esta em curso e sem
  // prazos configurados. O exercicio fechado de 2025 e o que tem a historia:
  // as tres retificacoes de que as legendas seguintes falam.
  await moveTo(page, 'select[aria-label="Trocar exercício"]');
  await page.selectOption('select[aria-label="Trocar exercício"]', '2025');
  await pausa(page, 1800);

  await page.waitForSelector('[data-testid="resumo-total"]', { timeout: 30000 }).catch(() => {});
  await moveTo(page, '[data-testid="resumo-retificadas"]');
  await beat(
    page,
    'Três retificações em 2025',
    'Cada retificação custa pontos no Ranking. Foram três no exercício: RGF do 3º quadrimestre, RREO do 1º e do 6º bimestres.',
  );

  await moveTo(page, 'table.samid-table >> nth=0');
  await beat(
    page,
    'Entregue no prazo, retificado depois',
    'A tabela separa as duas coisas. Nenhuma entrega original atrasou: os 9 registros de RREO e RGF homologados saíram entre 28 e 30 dias.',
  );

  await beat(
    page,
    'Sem veredicto sem base',
    'Onde o prazo não está fundamentado em norma, o sistema não julga: mostra a data e se cala. Não inventa "no prazo".',
  );
  await clearCaption(page);
}

export async function comparar(page) {
  await click(page, nav('Comparar'), { after: 700 });

  // O padrao compara as duas competencias mais recentes — hoje 2025-13 contra
  // 2026-01, ou seja, um periodo de encerramento contra um mes de janeiro. O
  // salto de pendencias ai e estrutural, nao regressao, e a tela carimba
  // "piora" por causa dele. Dois meses comuns comparam like-for-like.
  //
  // Os dois selects sao trocados ANTES de qualquer pausa, e sem passeio de
  // cursor: com a narracao por cima, cada segundo em que o selo "piora" fica
  // visivel e um segundo em que a voz fala de evolucao contra uma tela que diz
  // o oposto. O gesto de apontar vem depois, ja com o valor certo.
  const pickers = page.locator('.samid-compare-pickers select.samid-select');
  await pickers.nth(0).selectOption('2025-11');
  await pickers.nth(1).selectOption('2025-12');
  await page.waitForTimeout(900);
  await moveTo(page, pickers.nth(1));

  await beat(
    page,
    'Um mês contra o outro',
    'A comparação entre competências mostra se o trabalho de correção está surtindo efeito: score, pendências e o que mudou por dimensão.',
    { extra: 1500 },
  );
  await clearCaption(page);
}

export async function encerramento(page) {
  await click(page, '.samid-logout', { after: 1800 });
  await beat(
    page,
    'Fim da sessão',
    'Ao sair, o token é descartado e as telas protegidas deixam de abrir.',
  );
  await clearCaption(page);

  await titleCard(
    page,
    'Antes do envio, não depois',
    'O ganho não é a tela: é descobrir a inconsistência enquanto ainda dá para corrigir.',
  );
  await pausa(page, 6500);
  await hideTitleCard(page);
  await page.waitForTimeout(1200);
}

/** Ordem de execucao. `record.mjs` percorre esta lista. */
export const ROTEIRO = [
  { id: 'abertura', fn: abertura },
  { id: 'login', fn: login },
  { id: 'execucao', fn: execucao },
  { id: 'score', fn: score },
  { id: 'pendencias', fn: pendencias },
  { id: 'regras', fn: regras },
  { id: 'exportacoes', fn: exportacoes },
  { id: 'entregas', fn: entregas },
  { id: 'comparar', fn: comparar },
  { id: 'encerramento', fn: encerramento },
];
