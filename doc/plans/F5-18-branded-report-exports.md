# F5-18 — Branded Report Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar identidade visual MCRA (navy + dourado) e qualidade profissional ao PDF executivo e ao Excel exportados, sem mudar contratos públicos.

**Architecture:** Novo módulo `brand.py` centraliza a paleta e expõe helpers para openpyxl e reportlab. O PDF é reescrito com `reportlab` (substitui o gerador manual). O Excel é re-estilizado com openpyxl (mantém abas, ganha capa e formatação contábil). As assinaturas de `export_issues_excel`, `render_executive_pdf`, `write_executive_pdf` permanecem estáveis.

**Tech Stack:** Python 3.11, openpyxl, **reportlab (nova dep)**, pandas, pytest.

## Global Constraints

- Python ≥ 3.11; usar `str | None`, `from __future__ import annotations` no topo de cada arquivo.
- Exceções de `ranking_msc.exceptions`; logging via `logging.getLogger("ranking_msc")`, nunca `print()`.
- Docstrings em português; nomes de código em inglês.
- Nova dependência: `reportlab>=4.0` em `pyproject.toml` `dependencies`. Wheel pura-Python (sem libs de sistema). Sem stubs → `ignore_missing_imports`.
- Contratos públicos inalterados: `export_issues_excel(...) -> Path`, `render_executive_pdf(payload) -> bytes`, `write_executive_pdf(payload, path) -> Path`.
- Divisão TECH-04 mantida: PDF executivo 1 página; Excel completo. Não colocar lista de pendências no PDF.
- Paleta (hex sem `#`): navy `0F1E3D`, gold `C9A449`, gold_lt `F3E6BA`, parchment `F6F4EE`, ink `1B1B1F`, graphite `5A5C66`, white `FFFFFF`; bandas A `2F8F5C`, B `6BA642`, C `D9B433`, D `D98B1C`, E `C02B2B`; severidades ERRO `C02B2B`, ALERTA `D98B1C`, INFO `1E5AA8`.
- `make validate` (lint+typecheck+test+frontend) deve passar ao fim.
- Rodar comandos via `.venv/bin/python` / `.venv/bin/pytest`.

---

## File Structure

- Create: `src/ranking_msc/outputs/brand.py` — fonte única de cores + helpers openpyxl/reportlab.
- Create: `tests/test_brand.py` — testes do módulo de marca.
- Create: `tests/test_executive_pdf.py` — testes unitários do renderer PDF.
- Modify: `src/ranking_msc/outputs/executive_pdf.py` — payload estruturado + renderer reportlab.
- Modify: `app/api/routes/exports.py` (função `_build_pdf_payload`, ~linhas 68-134) — popular campos estruturados do payload.
- Modify: `tests/test_api_exports.py` (~linhas 215-217, 263) — ajustar asserts de conteúdo do PDF.
- Modify: `src/ranking_msc/outputs/reports.py` — estilo branded + capa + formato contábil.
- Modify: `tests/test_reports.py` (~linha 106) — incluir aba "Visão Geral".
- Modify: `pyproject.toml` (deps e overrides mypy) — dep reportlab + override.
- Modify: `CLAUDE.md` (§7) e `doc/backlog.md` — registrar decisão e task.

---

### Task 1: Módulo de marca + dependência reportlab

**Files:**
- Modify: `pyproject.toml` (`dependencies` e `[[tool.mypy.overrides]]`)
- Create: `src/ranking_msc/outputs/brand.py`
- Test: `tests/test_brand.py`

**Interfaces produzidas:**
- `NAVY, GOLD, GOLD_LT, PARCHMENT, INK, GRAPHITE, WHITE: str` (hex sem `#`)
- `BAND_A..BAND_E`, `ERRO`, `ALERTA`, `INFO: str`
- `band_hex(banda: str) -> str`; `band_hex_for_score(nota_pct: float) -> str`; `severity_hex(sev: str) -> str`
- `fill(hex_str: str) -> openpyxl.styles.PatternFill`; `HEADER_FILL: PatternFill`; `HEADER_FONT: Font`; `TITLE_FONT: Font`
- `rl_color(hex_str: str) -> reportlab.lib.colors.Color`

Passos: (1) adicionar `"reportlab>=4.0"` em `dependencies` e override mypy `module=["reportlab","reportlab.*"] ignore_missing_imports=true`, rodar `.venv/bin/python -m pip install -e ".[dev]"`; (2) escrever `tests/test_brand.py` cobrindo limites de banda (95/85/75/65/0), severidades + fallback, `fill` retorna PatternFill sólido navy, `HEADER_FONT.bold`, e `rl_color(GOLD)` com componentes `0xC9/0xA4/0x49` normalizados; (3) rodar e ver falhar (`ModuleNotFoundError`); (4) implementar `brand.py` (constantes + funções acima); (5) rodar e passar; (6) commit `F5-18: brand palette module and reportlab dependency`.

Ver as interfaces produzidas acima; o `brand.py` é só constantes + funções puras (sem I/O), implementação direta seguindo a paleta das Global Constraints.

### Task 2: Reescrita do PDF executivo com reportlab

**Files:** Modify `src/ranking_msc/outputs/executive_pdf.py`; Test `tests/test_executive_pdf.py` (novo).

**Interfaces produzidas:** dataclasses `DimItem(nome, pct)`, `RecItem(ordem, titulo, descricao, severidade, referencia)`, `HistItem(competencia, score, banda)`; `ExecutivePdfPayload` com campos antigos preservados (defaults) + `dimensions/recommendations/history/data_geracao`; `render_executive_pdf(payload)->bytes` e `write_executive_pdf(payload,path)->Path` estáveis.

Pontos-chave: renderer com `reportlab.pdfgen.canvas.Canvas(buf, pagesize=A4, pageCompression=0)` — **compressão desligada** para manter texto greppável nos testes; faixa navy + wordmark MCRA/gold; bloco herói (nota grande na cor da banda + `/100 · BANDA X` + delta); barras horizontais por dimensão coloridas por `band_hex_for_score`; histórico recente; cards de recomendação com tag de severidade; rodapé. Acentos PT-BR sobrevivem (Helvetica/WinAnsi).

Passos TDD: teste valida `startswith(b"%PDF")`, termina com `%%EOF`, `/Count 1`, contém `Conformidade MSC`/`2026-01`/`Estrutura`/`Fechamento`, e `"Visão".encode("latin-1") in data`. Implementar; rodar; commit `F5-18: render executive PDF with reportlab and MCRA branding`.

### Task 3: Popular o payload estruturado na rota de exports

**Files:** Modify `app/api/routes/exports.py` (`_build_pdf_payload`); Test ajustar `tests/test_api_exports.py`.

Ajustar asserts antigos: `b"2025-11: score"` → `b"2025-11"` (o histórico passa a ser `competência <score> · banda <X>`), e `b"2026-01: score" not in` → `b"2026-01" in` (competência ativa aparece no cabeçalho/score). Importar `DimItem/RecItem/HistItem`. Montar `dimensions` (de `score.dimensions`, pct = score*100, ordenado), `history` (de `history_periods[-6:]`), `recommendations` (converter os `Recommendation` de `derive_recommendations` em `RecItem` com `ordem` enumerado), `data_geracao` (timestamp local `%Y-%m-%d %H:%M`), e passar tudo ao `ExecutivePdfPayload` mantendo os campos antigos. Commit `F5-18: feed structured data into branded executive PDF payload`.

### Task 4: Excel branded (cabeçalhos, bordas, formato contábil)

**Files:** Modify `src/ranking_msc/outputs/reports.py`; Test estender `tests/test_reports.py`.

Substituir constantes locais de cor por `brand.*` (`_HEADER_FILL=brand.HEADER_FILL`, `_HEADER_FONT=brand.HEADER_FONT`, `_SEVERITY_COLORS` e `_BAND_FILLS` via `brand`). Adicionar `_apply_currency_format(ws)` (colunas "Valor Esperado"/"Valor Encontrado" → `number_format='R$ #,##0.00'` quando numéricas) e `_apply_borders(ws)` (`Border` fino cinza) chamadas em `_write_pendencias_sheet`, `_add_score_sheet`, `_add_saldo_devedor_sheet`. Teste novo `TestExcelBranding`: cabeçalho com fill `0F1E3D`, fonte branca/bold, e coluna de valor com `R$` no `number_format`. Atualizar qualquer assert antigo de cor de cabeçalho (`DDEBF7`→`0F1E3D`). Commit `F5-18: brand Excel headers, borders and accounting number format`.

### Task 5: Aba de capa "Visão Geral" no Excel

**Files:** Modify `src/ranking_msc/outputs/reports.py` (`_add_cover_sheet` + chamada); Test atualizar `tests/test_reports.py` (`sheetnames`).

`_add_cover_sheet(writer, competencia, score_result)` cria `writer.book.create_sheet("Visão Geral", 0)` (índice 0 = primeira aba), gridlines off, banner navy mesclado com `TITLE_FONT` ("MCRA · PMJP — Conformidade MSC"), competência, nota grande colorida pela banda, banda, e mini-tabela de dimensões (nome · nota% colorida por `band_hex_for_score`). Chamar como **primeira** instrução dentro do `with pd.ExcelWriter(...)`. Atualizar assert: `sheetnames[0] == "Visão Geral"` e `sheetnames[1:3] == ["Resumo","Pendências"]`; novo teste confere que a capa contém "MCRA" e "Conformidade". Commit `F5-18: add branded Visão Geral cover sheet to Excel export`.

### Task 6: Documentação + validação final

**Files:** Modify `CLAUDE.md` (§7) e `doc/backlog.md`.

Atualizar a linha "Relatórios" da tabela §7 (separar Excel openpyxl+brand e PDF reportlab). Registrar `F5-18` no backlog (concluída: PDF reportlab branded + Excel com capa/estilo). Rodar `make validate` (ou pytest+ruff+mypy+`cd web && npm run build`) — tudo verde. Commit `F5-18: document branded report exports decision and backlog`.

---

## Self-Review (cobertura do spec)

- Módulo de marca → Task 1. PDF reportlab branded (header/score/dimensões/recos/histórico/acentos) → Task 2+3. Excel header/bordas/moeda → Task 4. Capa → Task 5. Dep reportlab + CLAUDE.md §7 → Task 1 + Task 6. Testes em todas. Contratos públicos preservados (Tasks 2,4,5). Sem placeholders de implementação — código completo referenciado vive no spec/este plano.

## Verificação manual (pós-implementação)

Subir API+front, logar, exportar Excel e PDF de `2026-01`, abrir e conferir visual (navy/gold, capa, score, barras, acentos). Confirmar PDF em **1 página** com 5 recomendações + 6 meses de histórico (ajustar espaçamento se estourar).

> **Nota:** os blocos de código completos (brand.py, executive_pdf.py renderer, helpers de reports.py e todos os testes) foram desenvolvidos junto deste plano; ao executar cada task, escrever exatamente o código descrito nas interfaces e pontos-chave acima, seguindo o ciclo TDD (teste falha → implementação mínima → teste passa → commit).
