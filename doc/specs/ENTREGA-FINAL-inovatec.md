# ENTREGA-FINAL — Fechamento e Entrega do Repositório para a Inovatec

> **Data:** 2026-07-08
> **Fase:** Fechamento final de entrega (pós-apresentação PMJP)
> **Status:** design aprovado, aguardando revisão do spec
> **Origem:** feedback da apresentação. Novos arquivos de teste recebidos (gabarito
> confirmado pelo Tesouro), necessidade de limpeza do repositório para envio à
> Inovatec, consolidação da documentação e emissão de um Termo de Conformidade
> assinável.

## Problema

O projeto está na reta final de entrega. Antes de enviar o repositório para a
Inovatec faltam seis frentes:

1. **Validar o motor** contra os novos arquivos de teste (`2507507EX-2025-12` e
   `2507507EX-2025-13`) — arquivos MSC cujo conteúdo já foi **confirmado como
   conforme pelo Tesouro Nacional**. São, na prática, um **gabarito**.
2. **Limpar o repositório** de arquivos inúteis (caches, temporários, `.DS_Store`,
   backups) para uma entrega enxuta, tanto via **git** quanto via **zip**.
3. **Consolidar a documentação** de como rodar/testar o sistema e a estrutura de
   pastas — hoje há duas pastas (`doc/` e `docs/`) e uma é redundante.
4. **Emitir um Termo de Conformidade** assinável (PDF) para o Rodrigo assinar,
   declarando que os requisitos estão atendidos e o sistema está funcional.
5. **Dar lugar às atas de reunião** no repositório (pasta + template padronizado).
6. **Registrar** a evolução futura (cross-validation MSC × relatórios SICONFI) sem
   implementá-la agora.

## Critério de aceite central (testes)

Os CSVs novos são **gabarito** (Tesouro confirmou ~100% de acertividade). Logo:

- ✅ **Esperado:** ao processar `2025-12` e `2025-13`, a conformidade deve ser
  **alta** e o número de pendências **baixo**.
- 🚩 **Se houver muitos erros/pendências:** o defeito está **no nosso motor**
  (falso-positivo nas regras), **não** nos dados. Nesse caso o trabalho **pausa** e
  entra em investigação (systematic-debugging) antes de qualquer relatório de
  "dados com erro". Não se reporta o gabarito como não-conforme.

## Escopo desta entrega (o que fazer agora)

### A. Testes de validação

- Rodar o pipeline nos dois CSVs novos via CLI (`scripts/run_pipeline.py`), gerando
  snapshot + score + pendências para cada competência.
- Conferir o resultado contra o critério de aceite acima.
- Rodar a suíte completa: `make validate` (pytest + ruff + mypy + frontend
  lint/typecheck/build). Reportar o resultado real, incluindo o estado do
  `tests/test_api_run.py` modificado no working tree.
- **Saída:** evidência de que o motor concorda com o gabarito e de que a suíte passa.

### B. Limpeza do repositório (git limpo + zip enxuto)

**Deletar fisicamente** (lixo, boa parte já gitignored mas presente no disco):

- Todos os `.DS_Store` (raiz, `ref/`, `ref/amostras/`, `doc/`, `docs/`…)
- `.coverage`, `.reports_test_tmp/`, `.snapshot_test_tmp/`
- Caches: `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`
- `config/settings.yaml.bak.20260616-115952`
- `.claude/settings.local.json` (config pessoal)

**Consolidar pastas de doc:**

- `docs/` (plural) contém **apenas** `docs/superpowers/` (scratch do workflow, já
  gitignored) → **remover**. `doc/` (singular) passa a ser a única casa de docs.

**Git — commitar o que falta na branch:**

- `uv.lock` (⚠️ lockfile crítico para instalação reproduzível — está untracked)
- `tests/test_api_run.py` (modificado)
- Os CSVs MSC novos como dados de teste (`ref/amostras/2507507EX-2025-12-001.csv`,
  `…-2025-13-001.csv`)

**Arquivos xlsx da raiz:**

- Mover `2026_Anexo_II_Portaria_STN_642_Leiaute_MSC_16012026 (1).xlsx` → `ref/`
  (leiaute MSC = referência legítima), renomeando para tirar o sufixo `(1)`.
- Remover `backlog_regras_msc_completo.xlsx` (superado por `doc/backlog.md`).

**Zip enxuto:** gerar pacote de entrega excluindo `.venv/`, `web/node_modules/`,
`data/`, `web/dist/`, `.git/`, todos os caches e temporários.

**`.gitignore`:** ajustar se surgir buraco durante a limpeza.

### C. Documentação (revisar e corrigir gaps, sem reescrever)

Revisar e garantir que cobrem, de forma correta e atual:

- **Como rodar** (dev + prod) — README + `doc/guia_operacao.md`
- **Como testar** — comandos de teste (`make validate`, `pytest`, pipeline via CLI)
- **Estrutura de pastas** — árvore comentada do repositório (README)
- **Manual do usuário** — `doc/manual_usuario.md`

Corrigir pontualmente apenas o que estiver faltando, desatualizado ou incorreto.

### D. Termo de Conformidade (PDF assinável)

- Fonte editável em Markdown: `doc/termo_conformidade.md`.
- Gerar **PDF branded** (via `reportlab`, mesma identidade visual de
  `outputs/brand.py` / relatórios), pronto para impressão e assinatura.
- Conteúdo:
  - Cabeçalho: projeto (MCRA PMJP — Ranking MSC), versão, ente, data.
  - Tabela **Requisito × Status de Conformidade** derivada do `doc/backlog.md`
    (78/78 regras, motor, API FastAPI, frontend React, relatórios Excel/PDF,
    deploy Docker/nginx/TLS, documentação).
  - Declaração de **funcionalidade em operação**, referenciando a evidência dos
    testes (workstream A).
  - Bloco de assinatura para **Rodrigo** (nome, cargo, data — placeholders) e para
    o responsável técnico.

### E. Atas de reunião no repositório

- Criar pasta `doc/atas/`.
- Criar `doc/atas/_template_ata.md` com campos padronizados: data, participantes,
  pauta, decisões, ações e responsáveis, links relacionados (backlog, specs).
- Semear 1 ata stub da **Reunião Bruno (2026-06-22)** a partir da menção no
  `doc/backlog.md`, com `<a preencher>` onde o conteúdo não é conhecido.

## Fora do escopo (registrar como fase futura)

### F. Cross-validation MSC × relatórios SICONFI (DCA / RGF / RREO)

Feature **nova** — o sistema hoje é MSC/CSV-only e nem lê `.xls`. Requer:

- Ingestão de `.xls` legados (OLE2) — adicionar dependência `xlrd`.
- Parsers para DCA (Contas Anuais), RGF (Gestão Fiscal) e RREO (Execução
  Orçamentária).
- Módulo de **regras de cruzamento** MSC × relatórios (consistência de valores).

**Ação nesta entrega:** apenas registrar no `doc/backlog.md` como próxima fase
(spec próprio depois). Os 3 `.xls` permanecem em `ref/amostras/` como material de
referência.

## Entregáveis

1. Evidência dos testes (log de execução do pipeline nos CSVs novos + `make validate`).
2. Repositório limpo na branch, com `uv.lock`/testes/dados commitados.
3. Pacote zip enxuto pronto para envio.
4. Documentação revisada (rodar / testar / estrutura de pastas).
5. `doc/termo_conformidade.md` + PDF assinável.
6. `doc/atas/` com template e ata semente.
7. Entrada no `doc/backlog.md` para a fase de cross-validation.

## Riscos e mitigações

- **Motor discorda do gabarito (muitos erros):** trata-se como bug de regra
  (falso-positivo); investigar antes de reportar. É o risco de maior impacto.
- **Deletar algo útil na limpeza:** revisar cada alvo antes de remover; itens
  ambíguos (xlsx de referência) são movidos, não apagados.
- **Perda de rastreabilidade no zip:** o zip exclui `.git/`, então a entrega
  "oficial" versionada é a via git; o zip é conveniência.
