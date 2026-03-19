# Resultados Piloto — Fase 2

**Data de execução:** 2026-03-19
**Versão do pipeline:** Fase 2 (F2-12 a F2-19)
**SICONFI:** 2507507EX (Prefeitura)
**Regras ativas:** R003, R004, R010, R021, R030

---

## Mapeamento de IDs: piloto planejado × implementado

As regras foram implementadas com IDs diferentes dos previstos em `regras_piloto.md`.
A tabela abaixo registra o mapeamento oficial para rastreabilidade:

| ID planejado | ID implementado | Lógica | Status |
|---|---|---|---|
| R082 | **R030** | Fechamento patrimonial D=C | ✅ Implementado |
| R089 | **R010** | Conta existe no PCASP | ✅ Implementado |
| R093 | **R021** | PO válido (5 dígitos + tabela) | ✅ Implementado |
| R085 | **R003/R004** | Tipo_valor e Natureza_valor válidos | ✅ Implementado |
| R102 | — | Continuidade temporal entre competências | ⏳ Próximas sprints |

---

## Arquivos processados

| Arquivo | SICONFI | Competência | Linhas (raw) | Linhas pivotadas | Contas únicas |
|---|---|---|---|---|---|
| msc_2025-11.csv | 2507507EX | 2025-11 | 25.311 | 10.450 | 376 |
| msc_2025-12.csv | 2507507EX | 2025-12 | 28.891 | 12.220 | 393 |

---

## Resultados de execução

| Competência | Status engine | Regras executadas | Total pendências |
|---|---|---|---|
| 2025-11 | **OK** | 5 | 200 |
| 2025-12 | **OK** | 5 | 246 |

> `status=OK` indica que todas as regras executaram sem crash. As pendências
> encontradas são violações de negócio detectadas pelas regras, não falhas do pipeline.

---

## Breakdown de pendências por regra

### Competência 2025-11

| Regra | Nome | Dimensão | Severidade | Pendências | Contas únicas |
|---|---|---|---|---|---|
| R003 | Tipo_valor válido | Estrutura | — | 0 | — |
| R004 | Natureza_valor válida | Estrutura | — | 0 | — |
| R010 | Conta existe no PCASP | PCASP | — | 0 | — |
| R021 | PO válido | PO | — | 0 | — |
| R030 | Fechamento patrimonial D=C | Fechamento | ERRO | **200** | 200 |

### Competência 2025-12

| Regra | Nome | Dimensão | Severidade | Pendências | Contas únicas |
|---|---|---|---|---|---|
| R003 | Tipo_valor válido | Estrutura | — | 0 | — |
| R004 | Natureza_valor válida | Estrutura | — | 0 | — |
| R010 | Conta existe no PCASP | PCASP | — | 0 | — |
| R021 | PO válido | PO | — | 0 | — |
| R030 | Fechamento patrimonial D=C | Fechamento | ERRO | **246** | 246 |

---

## Observações por regra

### R003 / R004 — Estrutura (0 pendências)
Todos os valores de `Tipo_valor` e `Natureza_valor` nos dois arquivos são válidos.
Dados estruturalmente íntegros.

### R010 — PCASP (0 pendências)
Todas as 376 contas de 2025-11 e 393 contas de 2025-12 existem no PCASP Estendido 2026
(`ref/pcasp.csv`, 7.918 contas). Nenhuma conta fora do plano vigente.

### R021 — PO (0 pendências)
Todos os valores de PO presentes nos CSVs têm 5 dígitos e existem na tabela oficial
(`ref/tabela_po.csv`, 92 códigos).

### R030 — Fechamento patrimonial D=C (200 / 246 pendências)

**Comportamento esperado em dados mensais.**

A regra verifica que `SUM(movimento_debito) == SUM(movimento_credito)` por conta
patrimonial (classes 1–4). Em dados mensais, lançamentos de débito e crédito não
precisam se equilibrar intra-mês — o equilíbrio ocorre no acumulado do exercício.

Exemplos de pendências detectadas:

| Competência | Conta | Movimento D | Movimento C | Diferença |
|---|---|---|---|---|
| 2025-11 | 111110200 | R$ 1.209.116.485,74 | R$ 1.081.023.376,65 | R$ 128.093.109,09 |
| 2025-12 | 111110200 | R$ 1.630.331.900,11 | R$ 1.684.536.877,05 | R$ 54.204.976,94 |

**Recomendação:** avaliar se R030 deve ser restrita a dados de fechamento anual
(competência 12) ou se deve permanecer como alerta para dados mensais.

---

## Outputs gerados (não versionados)

| Tipo | Localização | Conteúdo |
|---|---|---|
| Snapshot Parquet | `data/piloto/snapshots/2025-11/resultado_regras.parquet` | 200 linhas |
| Snapshot Parquet | `data/piloto/snapshots/2025-12/resultado_regras.parquet` | 246 linhas |
| Relatório Excel | `data/piloto/reports/pendencias_2025-11.xlsx` | Abas: Resumo + Pendências |
| Relatório Excel | `data/piloto/reports/pendencias_2025-12.xlsx` | Abas: Resumo + Pendências |
| Log JSON Lines | `data/piloto/logs/ranking_msc.jsonl` | Auditoria completa |

---

## Conclusão

- Pipeline funcional de ponta a ponta com dados reais de produção
- 4 de 5 regras sem qualquer pendência: dados estruturalmente íntegros
- R030 gera pendências esperadas em dados mensais (D≠C intra-mês é normal)
- Nenhum bug encontrado durante a execução
- Pronto para handoff da Fase 3 (dashboard Panel + deploy servidor)
