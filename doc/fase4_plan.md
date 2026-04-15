# Fase 4 — Plano de Implementação

**Status:** Em andamento (F4-01 concluído)
**Depende de:** Fase 3 (concluída — 35 regras, 471 testes, pipeline completo)
**Referência do backlog:** F4-01 a F4-11

---

## Resumo da Fase 3 (concluída)

| Entrega | Status |
|---------|--------|
| 35 regras implementadas (R001-R081) | Feito |
| 471 testes passando, ruff e mypy limpos | Feito |
| Pipeline web funcional (snapshot + Excel + log) | Feito |
| Pipeline CLI funcional | Feito |
| Relatório Excel com abas Resumo + Pendências + Saldo Devedor | Feito |
| Regras temporais R054, R055, R069 | Feito |

---

## O que é a Fase 4

**Scoring, batch processing e otimização.** A infraestrutura de regras está pronta.
Agora: calcular nota de qualidade, processar múltiplas competências, comparar
evolução entre meses, e otimizar performance para CSVs grandes.

---

## Tasks F4-01 a F4-11

| ID | Task | Descrição | Prioridade | Horas | Depende de | Status |
|---|---|---|---|---|---|---|
| F4-01 | Definir modelo de pontuação (scoring) | Modelo 0-100 inspirado no ICF do Ranking Siconfi: peso por dimensão × severidade. | Crítica | 8 | F3-16 | **Concluído** (P1: renorm dims c/ Σw=0; P2: FP+AI em IC/Domínio) |
| F4-02 | Implementar score_engine.py | Calcular nota por categoria e nota final do ente com base nas pendências. | Crítica | 10 | F4-01 | A Fazer |
| F4-03 | Relatório com score e ranking por categoria | Aba de Score no Excel: nota por categoria + nota geral + bandas A-E. | Alta | 8 | F4-02 | A Fazer |
| F4-04 | Suporte a múltiplas competências (batch) | Pipeline aceita diretório com múltiplos CSVs e gera snapshot + relatório por competência. | Alta | 8 | F3-12 | A Fazer |
| F4-05 | Comparação entre competências (evolução temporal) | Comparar scores entre meses para mostrar evolução da qualidade. | Alta | 8 | F4-02, F4-04 | A Fazer |
| F4-06 | Relatório consolidado multi-competência | Excel com aba de evolução temporal + gráficos. | Alta | 8 | F4-05 | A Fazer |
| F4-07 | Regras adicionais do Ranking Siconfi | Pesquisar e implementar regras adicionais publicadas no manual SICONFI. | Média | 10 | F3-16 | A Fazer |
| F4-08 | Testes de carga com CSVs grandes (>100k linhas) | Benchmark de performance com CSVs reais grandes. | Alta | 6 | F4-04 | A Fazer |
| F4-09 | Otimizar regras com operações vetorizadas | Refatorar regras para usar groupby/vectorized ao invés de loops. Melhoria ≥50%. | Alta | 8 | F4-08 | A Fazer |
| F4-10 | Tratamento robusto de encoding e separadores | Suportar UTF-8/Latin-1/CP1252, separadores `,` `;` `|` e detecção automática. | Média | 6 | — | A Fazer |
| F4-11 | Documentar Fase 4 + fechar sprint | Cobertura ≥85%, docs atualizados, handoff Fase 5. | Alta | 4 | F4-01..F4-10 | A Fazer |

**Total estimado:** ~84 horas

---

## Ordem de execução sugerida

### Semana 8 (S8) — Scoring
1. **F4-01** — Mergear PR #53 (modelo de pontuação já documentado)
2. **F4-02** — Implementar `engine/score_engine.py`
3. **F4-03** — Aba Score no Excel

### Semana 9 (S9) — Batch + Evolução
4. **F4-04** — `scripts/run_batch.py` (múltiplas competências)
5. **F4-05** — `engine/compare_periods.py` (comparação temporal)
6. **F4-06** — Relatório consolidado multi-competência

### Semana 10 (S10) — Performance + Polish
7. **F4-07** — Regras adicionais (se identificadas com Rodrigo)
8. **F4-08** — Benchmark de performance
9. **F4-09** — Otimização vetorizada
10. **F4-10** — Encoding robusto
11. **F4-11** — Documentação + handoff Fase 5

---

## Entregáveis da Fase 4

| Artefato | Descrição |
|----------|-----------|
| `engine/score_engine.py` | Motor de pontuação 0-100 por dimensão |
| `doc/modelo_pontuacao.md` | Documentação do modelo (já em PR #53) |
| `scripts/run_batch.py` | CLI para processar múltiplas competências |
| `engine/compare_periods.py` | Comparação de scores entre meses |
| `outputs/report_consolidado.py` | Excel com evolução temporal |
| `outputs/reports.py` (atualizado) | Aba Score no relatório individual |
| `ref/benchmark_performance.md` | Resultados de benchmark |
| `io/reader_msc.py` (atualizado) | Encoding auto-detect |

---

## Decisão pendente: F3-18 (VPD 13º salário)

O backlog original lista F3-18 como "Regra VPD 13º — verificar provisão mensal
de 13º salário". Na prática, F3-18 foi repurposeada para R055+R069 (temporal
encerramento). A regra de VPD 13º precisa de mapeamento de contas com Rodrigo.

**Sugestão:** mover para F4-07 (regras adicionais) e implementar quando o
mapeamento de contas estiver disponível.
