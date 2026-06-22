# F5-18 — Branded Report Exports (PDF + Excel)

> **Data:** 2026-06-22
> **Task:** F5-18
> **Status:** design aprovado, aguardando revisão do spec
> **Origem:** feedback do Gabriel — "o Excel exportado é muito feio" + "o PDF também".

## Problema

As exportações funcionam (bytes válidos, conteúdo correto) mas são visualmente
cruas:

- **PDF executivo** (`src/ranking_msc/outputs/executive_pdf.py`): gerado à mão em
  sintaxe PDF pura para evitar dependências (decisão CLAUDE.md §7). Resultado:
  texto preto corrido em Helvetica, sem cor, caixa, marca ou hierarquia visual.
  Acentos são removidos (`latin-1`/escape manual).
- **Excel** (`src/ranking_msc/outputs/reports.py`): tem boa estrutura (abas
  Resumo, Pendências, por-dimensão, Saldo Devedor, Score; cores por severidade;
  cabeçalho congelado; auto-filtro) mas estética default: cabeçalho azul-claro,
  sem bordas, sem banner de marca, valores sem formato contábil.

## Objetivo

Deixar PDF e Excel com a identidade visual do app MCRA (navy + dourado),
profissionais e prontos para distribuição à gestão e à equipe contábil — sem
mudar contratos públicos das funções de exportação nem a divisão acordada
(TECH-04: PDF executivo 1 página + Excel completo).

## Identidade visual (fonte: paleta do app, `web/src`)

| Token | Hex | Uso |
|---|---|---|
| navy (midnight) | `#0F1E3D` | faixas de cabeçalho, títulos |
| gold | `#C9A449` | acento/régua, wordmark |
| gold claro | `#F3E6BA` | realces sutis |
| parchment | `#F6F4EE` | fundo de seção / zebra |
| ink | `#1B1B1F` | texto principal |
| graphite | `#5A5C66` | texto secundário |
| banda A | `#2F8F5C` | score/dimensão ≥ 95 |
| banda B | `#6BA642` | ≥ 85 |
| banda C | `#D9B433` | ≥ 75 |
| banda D | `#D98B1C` | ≥ 65 |
| banda E | `#C02B2B` | < 65 |
| erro / alerta / info | `#C02B2B` / `#D98B1C` / `#1E5AA8` | severidades |

Marca: **wordmark tipográfico** "MCRA · PMJP" (sem arquivo de logo). Sem brasão.

## Arquitetura

### Novo módulo: `src/ranking_msc/outputs/brand.py`

Fonte única da paleta e da tipografia, evitando duplicação de cores hoje
espalhada em `reports.py`. Expõe:

- constantes de cor (hex `str`, ex. `NAVY = "0F1E3D"`);
- `band_hex(banda: str) -> str` e `band_hex_for_score(nota: float) -> str`;
- `severity_hex(sev: str) -> str`;
- helpers openpyxl: `fill(hex) -> PatternFill`, fontes pré-montadas
  (`HEADER_FONT`, `TITLE_FONT`);
- helpers reportlab: `color(hex) -> reportlab.lib.colors.Color`.

`reports.py` e `executive_pdf.py` passam a importar daqui. As constantes locais
de cor em `reports.py` (`_SEVERITY_COLORS`, `_BAND_FILLS`, `_HEADER_FILL`…)
migram para `brand.py`.

### Dependência nova: `reportlab`

- Adicionada em `pyproject.toml` (`dependencies`).
- Wheel pura-Python, **sem libs de sistema** → instala no Docker via o mesmo
  `pip install -e .` já existente. Sem mudança no `Dockerfile`.
- CLAUDE.md §7: atualizar a linha de "Relatórios" e a nota de "PDF na mão" para
  registrar a decisão (reportlab para o PDF executivo).

### PDF executivo — reescrita de `executive_pdf.py` com reportlab

Mantém as assinaturas públicas **estáveis**:
`render_executive_pdf(payload) -> bytes` e
`write_executive_pdf(payload, path) -> Path`. A rota `app/api/routes/exports.py`
não muda.

`ExecutivePdfPayload` ganha campos **estruturados** para permitir layout gráfico
(mantendo os antigos para compatibilidade de quem ainda passa linhas):

- `dimensions: list[tuple[str, float]]` — (nome, pct 0–100) para as barras;
- `recommendations: list[RecItem]` — (ordem, título, descrição, severidade,
  referência) para os cards;
- `history: list[tuple[str, float]]` — (competência, score) para o mini-histórico;
- `data_geracao: str` — timestamp de geração.

`exports.py` é ajustado para preencher esses campos a partir do `ScoreResult` /
recomendações que já calcula.

Layout (A4 retrato, 1 página):

1. **Faixa navy no topo** (full width): à esquerda wordmark "MCRA" em dourado +
   "PMJP · Ranking MSC"; à direita "Visão Executiva", `competência` e
   `data de geração`.
2. **Bloco herói do score**: número grande (ex. `76,4`) na cor da banda + chip
   "BANDA C" + "/100 · Conformidade MSC"; delta vs período anterior (▲/▼) quando
   houver.
3. **Linha de stats** (pills): regras pontuáveis · erros · alertas.
4. **Desempenho por dimensão**: barras horizontais coloridas por banda, com
   rótulo de % e nome (Estrutura 100%, Fechamento 55%…).
5. **Histórico recente**: mini-tabela/linha das últimas competências (score+banda).
6. **Ações prioritárias**: 3–5 cards (nº, regra/título, nº pendências, tag de
   severidade colorida).
7. **Rodapé**: "Gerado em … · Fonte: SICONFI · Detalhe completo no Excel" +
   numeração de página.

Acentuação correta (reportlab Helvetica com encoding WinAnsi cobre PT-BR).

### Excel — restyle de `reports.py` (sem nova dependência)

Estrutura de abas **preservada**. Mudanças estéticas, dirigidas por `brand.py`:

- **Nova aba 1 "Visão Geral"** (capa): banner navy com wordmark + ente +
  competência + data; score/banda em destaque (célula grande colorida pela
  banda); mini-tabela de dimensões (nome · % · banda). As abas existentes
  (Resumo, Pendências, por-dimensão, Saldo Devedor, Score) seguem depois.
- **Cabeçalhos**: faixa navy com texto branco/bold (substitui o azul-claro);
  régua dourada opcional na linha de título.
- **Bordas finas** nas tabelas; **zebra** parchment nas abas sem cor de
  severidade (Score, Visão Geral); cores de banda/severidade alinhadas à paleta.
- **Formatos de número**: colunas de valor (`valor_esperado`, `valor_encontrado`,
  saldos) em formato contábil `R$ #.##0,00`; contagens como inteiro.
- Mantém freeze de cabeçalho, auto-filtro e auto-fit de largura já existentes.

## Contratos / compatibilidade

- Assinaturas de `export_issues_excel`, `render_executive_pdf`,
  `write_executive_pdf` inalteradas → rotas e CLIs não mudam.
- Saída continua sendo `.xlsx` válido e `%PDF` de 1 página válido.

## Testes (TDD)

Escrever testes **antes** da implementação de cada parte:

- `tests/test_brand.py` (novo): cor↔fill, `band_hex_for_score` nos limites
  (95/85/75/65), `severity_hex`.
- `tests/test_executive_pdf.py`: bytes começam com `%PDF`, terminam com `%%EOF`,
  1 página, textos esperados presentes no stream (competência, "Conformidade",
  banda, nomes de dimensão), acentos preservados.
- `tests/test_reports.py` (estender): aba "Visão Geral" existe e é a primeira;
  todas as abas esperadas presentes; cabeçalho com fill navy; valores de score
  corretos; colunas de valor com `number_format` contábil. Ajustar asserts que
  presumiam o estilo antigo.
- `make validate` (lint+typecheck+test+frontend) verde ao final.

## Fora de escopo (parking lot)

- Seletor de competência na TopBar (#1) e clareza do Comparar (#2) — tema
  separado, adiado a pedido do Gabriel. A infra (`store.setCurrent`,
  `GET /api/competencias`) já existe; é trabalho de UI.
- Brasão oficial da PMJP no cabeçalho (sem arquivo hoje).

## Critério de aceite

PDF e Excel saem com a identidade MCRA (navy/gold), 1 página executiva no PDF
com score/dimensões/recomendações legíveis e branded, Excel com capa e formatação
contábil; contratos públicos intactos; `make validate` verde.
