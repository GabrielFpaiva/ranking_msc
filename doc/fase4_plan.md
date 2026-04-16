# Fase 4 — Plano de Implementação

**Status:** Em andamento (F4-01, F4-02 e F4-04 concluídos)
**Depende de:** Fase 3 (concluída — 35 regras, 471 testes, pipeline completo)
**Referência do backlog:** F4-01 a F4-20

---

## Resumo da Fase 3 (concluída)

| Entrega | Status |
|---------|--------|
| 35 regras implementadas (R001-R081, subset) | Feito |
| 471 testes passando, ruff e mypy limpos | Feito |
| Pipeline web funcional (snapshot + Excel + log) | Feito |
| Pipeline CLI funcional | Feito |
| Relatório Excel com abas Resumo + Pendências + Saldo Devedor | Feito |
| Regras temporais R054, R055, R069 | Feito |

---

## O que é a Fase 4

**Cobertura total de regras + scoring + batch + performance.**

O catálogo tem **78 regras** (67 originais + 11 novas do SIGEF/JPA).
A Fase 3 entregou 35. Restam **43 regras** a implementar — distribuídas nos
tasks F4-07 a F4-19 abaixo. Além disso: scoring 0-100, processamento em lote,
comparação temporal e otimizações de performance.

---

## Tasks F4-01 a F4-20

| ID | Task | Descrição | Prioridade | Horas | Depende de | Status |
|---|---|---|---|---|---|---|
| F4-01 | Definir modelo de pontuação (scoring) | Modelo 0-100 inspirado no ICF do Ranking Siconfi: peso por dimensão × severidade. | Crítica | 8 | F3-16 | **Concluído** (P1: renorm dims c/ Σw=0; P2: FP+AI em IC/Domínio) |
<<<<<<< Updated upstream
| F4-02 | Implementar score_engine.py | Calcular nota por categoria e nota final com base nas pendências. | Crítica | 10 | F4-01 | Em andamento |
| F4-03 | Relatório com score e ranking por categoria | Aba Score no Excel: nota por categoria + nota geral + bandas A-E. | Alta | 8 | F4-02 | A Fazer |
| F4-04 | Suporte a múltiplas competências (batch) | `run_batch.py`: diretório com N CSVs → snapshot + relatório por competência. | Alta | 8 | F3-12 | **Concluído** |
=======
| F4-02 | Implementar score_engine.py | Calcular nota por categoria e nota final do ente com base nas pendências. | Crítica | 10 | F4-01 | **Concluído** (is_scoring em Rule ABC; calculate_score w/ dynamic w_r + renorm; 23 testes; PR #57) |
| F4-03 | Relatório com score e ranking por categoria | Aba de Score no Excel: nota por categoria + nota geral + bandas A-E. | Alta | 8 | F4-02 | A Fazer |
| F4-04 | Suporte a múltiplas competências (batch) | Pipeline aceita diretório com múltiplos CSVs e gera snapshot + relatório por competência. | Alta | 8 | F3-12 | A Fazer |
>>>>>>> Stashed changes
| F4-05 | Comparação entre competências (evolução temporal) | Comparar scores entre meses para mostrar evolução da qualidade. | Alta | 8 | F4-02, F4-04 | A Fazer |
| F4-06 | Relatório consolidado multi-competência | Excel com aba de evolução temporal + gráficos. | Alta | 8 | F4-05 | A Fazer |
| F4-07 | Regras de Estrutura — R006 a R0011 | 6 regras de formato do CSV: siconfi/período válidos, separador, colunas, cabeçalho, valores não-negativos. | Alta | 6 | — | A Fazer |
| F4-08 | Testes de carga com CSVs grandes (>100k linhas) | Benchmark de performance com CSVs reais grandes. | Alta | 6 | F4-04 | A Fazer |
| F4-09 | Otimizar regras com operações vetorizadas | Refatorar regras para usar groupby/vectorized ao invés de loops. Melhoria ≥50%. | Alta | 8 | F4-08 | A Fazer |
| F4-10 | Tratamento robusto de encoding e separadores | Suportar UTF-8/Latin-1/CP1252, separadores `,` `;` `\|` e detecção automática. | Média | 6 | — | A Fazer |
| F4-11 | Regras IC completude — R033, R034, R038, R082 | R033: pares IC/TIPO · R034: PO obrigatório · R038: IC×conta do leiaute · R082: ordem de ICs. | Alta | 5 | R020 | A Fazer |
| F4-12 | Regras de domínio complementares — 9 regras | R039 (PO×esfera) · R044 (NR valorizável) · R045-R047 (ND nível/genérica/subelementos) · R048 (FR 1º dígito) · R063 (DC contas permitidas) · R064 (CO×conta) · R065 (FS combinação atípica). | Alta | 10 | R020-R028 | A Fazer |
| F4-13 | Regras Fechamento por classe — R035, R036, R037 | R035: D=C patrimonial total · R036: D=C orçamentário · R037: D=C controle. Complementam R030. | Alta | 4 | R030 | A Fazer |
| F4-14 | Regras Superávit completo + Interconta R053 | R061: conta Financeira com FP=2 · R062: conta Permanente com FP=1 · R053: INTRA OFSS com contrapartida. | Alta | 4 | R060, R010 | A Fazer |
| F4-15 | Regras Completude + Qualidade — 7 regras | R066 (receita presente) · R067 (despesa presente) · R068 (8 classes) · R074 (SF ou PC) · R071 (decimais) · R072 (outlier registros) · R073 (outlier valor). | Média | 8 | R026, R027 | A Fazer |
| F4-16 | SIGEF — Saldo invertido por classe — R086, R087, R088 | R086: Ativo credor invertido · R087: Passivo devedor invertido · R088: PL invertido. SIGEF V5/V9/V10. | Alta | 4 | R032, R010 | A Fazer |
| F4-17 | SIGEF — IC detalhamento faltante — R089 a R093 | R089: receita sem FR · R090: receita sem NR · R091: despesa sem ND · R092: despesa sem FS · R093: despesa sem FR. SIGEF V13-V17. | Alta | 5 | R020, R024-R028 | A Fazer |
| F4-18 | SIGEF — Temporal + Completude especial — R083, R084, R085 | R083: dados executivo iguais entre meses · R084: conta Financeira sem FR · R085: depreciação sem movimentação. SIGEF V7/V11/V19. | Alta | 5 | R054, R022 | A Fazer |
| F4-19 | Extrair helpers CLI compartilhados | Mover `OutputPaths`, `_resolve_output_paths`, `_resolve_config_path`, `_log_failure` para `src/ranking_msc/cli_utils.py`. Evitar triplicação quando F4-05/F4-06 adicionarem novos CLIs. | Média | 3 | F4-04 | A Fazer |
| F4-20 | Documentar Fase 4 + fechar sprint | Cobertura ≥85%, docs atualizados, handoff Fase 5. | Alta | 4 | F4-01..F4-19 | A Fazer |

**Total estimado:** ~138 horas

---

## Gap de regras — resumo

| Categoria | Implementadas | Total | Faltam | Task |
|---|:---:|:---:|:---:|---|
| Estrutura | 5 | 11 | 6 | F4-07 |
| IC | 1 | 5 | 4 | F4-11 |
| PO | 1 | 2 | 1 | F4-12 |
| DC | 1 | 2 | 1 | F4-12 |
| FR | 1 | 2 | 1 | F4-12 |
| CO | 1 | 2 | 1 | F4-12 |
| NR | 1 | 2 | 1 | F4-12 |
| ND | 1 | 4 | 3 | F4-12 |
| FS | 1 | 2 | 1 | F4-12 |
| AI | 1 | 1 | 0 | — |
| Fechamento | 3 | 6 | 3 | F4-13 |
| Interconta | 3 | 4 | 1 | F4-14 |
| Superávit | 1 | 3 | 2 | F4-14 |
| Completude | 4 | 8 | 4 | F4-15 |
| Temporal | 3 | 3 | 0 | — |
| Duplicidade | 1 | 1 | 0 | — |
| Formato | 2 | 2 | 0 | — |
| Qualidade | 0 | 3 | 3 | F4-15 |
| SIGEF saldo | 0 | 3 | 3 | F4-16 |
| SIGEF IC detail | 0 | 5 | 5 | F4-17 |
| SIGEF temporal | 0 | 3 | 3 | F4-18 |
| **Total** | **35** | **78** | **43** | |

---

## Ordem de execução sugerida

### Semana 8 (S8) — Scoring + Rules P0/P1
1. **F4-02** — `engine/score_engine.py` (outro dev)
2. **F4-07** — Estrutura R006-R0011 (regras P0, simples)
3. **F4-11** — IC completude R033, R034, R038, R082
4. **F4-03** — Aba Score no Excel (depende F4-02)

### Semana 9 (S9) — Rules P1/P2 + Batch
5. **F4-13** — Fechamento por classe R035-R037
6. **F4-14** — Superávit + Interconta R053, R061-R062
7. **F4-12** — Domínio complemento (9 regras)
8. **F4-05** — Comparação temporal (depende F4-02, F4-04)

### Semana 10 (S10) — Rules P2/P3 + SIGEF
9. **F4-15** — Completude + Qualidade (7 regras)
10. **F4-16** — SIGEF saldo invertido R086-R088
11. **F4-17** — SIGEF IC detalhamento R089-R093
12. **F4-18** — SIGEF temporal/completude R083-R085

### Semana 11 (S11) — Performance + Polish
13. **F4-06** — Relatório consolidado multi-competência (depende F4-05)
14. **F4-08** — Benchmark de performance
15. **F4-09** — Otimização vetorizada
16. **F4-10** — Encoding robusto
17. **F4-19** — Extrair helpers CLI
18. **F4-20** — Documentação + handoff Fase 5

---

## Entregáveis da Fase 4

| Artefato | Descrição |
|----------|-----------|
| `engine/score_engine.py` | Motor de pontuação 0-100 por dimensão |
| `doc/modelo_pontuacao.md` | Documentação do modelo (F4-01, concluído) |
| `scripts/run_batch.py` | CLI para processar múltiplas competências (F4-04, concluído) |
| `engine/compare_periods.py` | Comparação de scores entre meses |
| `outputs/report_consolidado.py` | Excel com evolução temporal |
| `outputs/reports.py` (atualizado) | Aba Score no relatório individual |
| `src/ranking_msc/cli_utils.py` | Helpers compartilhados pelos CLIs |
| `ref/benchmark_performance.md` | Resultados de benchmark |
| `io/reader_msc.py` (atualizado) | Encoding auto-detect |
| `rules/r006.py` … `rules/r093.py` | 43 regras restantes do catálogo |

---

## Decisão pendente: F3-18 (VPD 13º salário)

O backlog original lista F3-18 como "Regra VPD 13º — verificar provisão mensal
de 13º salário". Na prática, F3-18 foi repurposeada para R055+R069 (temporal
encerramento). A regra de VPD 13º precisa de mapeamento de contas com Rodrigo.

**Decisão:** mover para Fase 5 (pós-entrega completa do catálogo).
