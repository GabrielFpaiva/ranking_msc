# Backlog Consolidado — Ranking MSC

> **Atualizado:** 2026-04-27
> **Estado atual:** 35 regras implementadas · 621 testes · Fase 0 concluída

---

## Visão Geral

O projeto contém **78 regras** no catálogo total (67 originais + 11 SIGEF/JPA).
Destas, **35 estão implementadas** e habilitadas. Restam **43 regras** a implementar.

O frontend React+FastAPI (Fase 0) está concluído. O motor Python está estável.

### Resumo por Fase

| Fase | Escopo | Status | Commits |
|---|---|---|---|
| Fase 2 | Infraestrutura + 5 regras piloto + Pipeline | ✅ Concluída | 190 testes |
| Fase 3 | Catálogo expandido → 35 regras | ✅ Concluída | 471 testes |
| Fase 4 | Scoring + Batch + Compare + regras restantes | 🟡 Em andamento (F4-01→F4-06 concluídos) | 621 testes |
| Fase 0 | Frontend MCRA (React+FastAPI replacing Panel) | ✅ Concluída | 8 commits |
| Fase 5 | Produção (auth, deploy, validação final) | 📋 Backlog | — |

---

## Regras Implementadas (35/78)

| Regra | Dimensão | Nome | Sev. | Fase |
|---|---|---|---|---|
| R001 | Estrutura | Colunas obrigatórias presentes | ERRO | F3 ✅ |
| R002 | Estrutura | CONTA preenchida em todas as linhas | ERRO | F3 ✅ |
| R003 | Estrutura | Tipo_valor válido | ERRO | F2 ✅ |
| R004 | Estrutura | Natureza_valor válida | ERRO | F2 ✅ |
| R005 | Estrutura | Valor numérico válido | ERRO | F3 ✅ |
| R010 | PCASP | Conta existe no PCASP Estendido 2026 | ERRO | F2 ✅ |
| R011 | PCASP | Conta é de último nível | ALERTA | F3 ✅ |
| R012 | PCASP | Conta está Ativa no PCASP | ALERTA | F3 ✅ |
| R020 | IC | Conjunto de IC correto para a conta | ERRO | F3 ✅ |
| R021 | PO | PO válido — 5 dígitos e existente na tabela | ERRO | F2 ✅ |
| R022 | IC | FP válido — 1 ou 2 | ERRO | F3 ✅ |
| R023 | IC | DC válido — valor 1 | ERRO | F3 ✅ |
| R024 | IC | FR válido — 4 dígitos, prefixo e tabela FR 2026 | ERRO | F3 ✅ |
| R025 | IC | CO válido — 4 dígitos e existente na tabela CO 2026 | ERRO | F3 ✅ |
| R026 | IC | NR válida — 8 dígitos e existente na tabela NR 2026 | ERRO | F3 ✅ |
| R027 | IC | ND válida — 8 dígitos e existente na tabela ND 2026 | ERRO | F3 ✅ |
| R028 | IC | FS válida — 5 dígitos (função + subfunção) | INFO | F3 ✅ |
| R029 | IC | AI — Ano Inscrição RP válido | ALERTA | F3 ✅ |
| R030 | Fechamento | Débito = Crédito por conta (fechamento patrimonial) | ERRO | F2 ✅ |
| R031 | Fechamento | SF = SI + Movimentos | ERRO | F3 ✅ |
| R032 | PCASP | Natureza do saldo compatível com conta | ERRO | F3 ✅ |
| R040 | Completude | Contas patrimoniais têm saldo inicial | ALERTA | F3 ✅ |
| R041 | Completude | Contas patrimoniais têm saldo final | ALERTA | F3 ✅ |
| R042 | Completude | Contas de resultado sem saldo (apenas movimentos) | ALERTA | F3 ✅ |
| R043 | Completude | Conta totalmente zerada | INFO | F3 ✅ |
| R050 | Interconta | Ativo = Passivo + PL | ERRO | F3 ✅ |
| R051 | Interconta | VPA - VPD = Resultado | ALERTA | F3 ✅ |
| R052 | Interconta | Controles devedores = Controles credores | ALERTA | F3 ✅ |
| R054 | Temporal | SI(N) = SF(N-1) | ALERTA | F3 ✅ |
| R055 | Temporal | Resultado zerado em janeiro | ALERTA | F3 ✅ |
| R060 | PCASP | FP coerente com indicador PCASP | ALERTA | F3 ✅ |
| R069 | Temporal | Resultado zerado no encerramento | ALERTA | F3 ✅ |
| R070 | Estrutura | Sem registros duplicados | ERRO | F3 ✅ |
| R080 | Formato | Formato de conta — 9 dígitos numéricos | ERRO | F3 ✅ |
| R081 | Formato | Formato de IC — dígitos por tipo | ERRO | F3 ✅ |

---

## Regras Pendentes (43/78)

### Estrutura (6 regras) — Task F4-07

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R006 | Código SICONFI válido | ERRO | SICONFI ≠ vazio e ≥ 7 dígitos |
| R007 | Período válido | ERRO | Período entre 01 e 13 |
| R008 | Separador de campo correto | ERRO | CSV com separador `;` conforme leiaute |
| R009 | Sem colunas extras não previstas | ALERTA | Apenas colunas do leiaute MSC |
| R0010 | Cabeçalho na primeira linha | ERRO | Primeira linha é header, não dados |
| R0011 | Valor não-negativo | ERRO | Campo Valor ≥ 0 (escala R$ 1,00) |

### IC Completude (4 regras) — Task F4-11

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R033 | Pares IC/TIPO presentes | ERRO | Cada IC1 deve ter TIPO1, etc. |
| R034 | PO obrigatório | ERRO | PO deve estar preenchido em todas as linhas |
| R038 | IC × conta conforme leiaute | ERRO | ID_IC da conta determina quais ICs são obrigatórios |
| R082 | Ordem das ICs no arquivo | ALERTA | ICs devem seguir a ordem do leiaute |

### Domínio Complementar (9 regras) — Task F4-12

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R039 | PO compatível com esfera do ente | ALERTA | Ente municipal não pode ter PO de poder federal |
| R044 | NR é valorizável (último nível) | ALERTA | NR sintéticas não devem receber valor |
| R045 | ND é último nível | ALERTA | ND sintéticas não devem receber valor |
| R046 | ND não genérica | ALERTA | ND terminada em 00 é genérica |
| R047 | ND subelementos = elemento pai | ALERTA | Soma dos subelementos deve bater com elemento |
| R048 | FR — 1º dígito válido | ALERTA | 1=corrente, 2=anterior, 9=condicionado |
| R063 | DC só em contas permitidas | ERRO | DC apenas nas 105 contas com ID_IC=8 |
| R064 | CO × tipo de conta | ALERTA | CO de despesa só em conta de despesa |
| R065 | FS combinação atípica | INFO | Combinações função/subfunção incomuns |

### Fechamento por Classe (3 regras) — Task F4-13

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R035 | D=C patrimonial total | ERRO | Débito = Crédito classes 1-4 (patrimonial) |
| R036 | D=C orçamentário | ERRO | Débito = Crédito classes 5-6 (orçamentário) |
| R037 | D=C controle | ERRO | Débito = Crédito classes 7-8 (controle) |

### Superávit + Interconta (3 regras) — Task F4-14

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R053 | INTRA OFSS com contrapartida | ALERTA | Operações intra têm saldo simétrico |
| R061 | Conta Financeira sem FP=2 | ALERTA | Conta financeira (IND_SF=S) não pode ter FP=2 |
| R062 | Conta Permanente sem FP=1 | ALERTA | Conta permanente (IND_SF=N) não pode ter FP=1 |

### Completude + Qualidade (7 regras) — Task F4-15

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R066 | Receita presente | ALERTA | Classe 4 (VPA) deve ter registros |
| R067 | Despesa presente | ALERTA | Classe 3 (VPD) deve ter registros |
| R068 | 8 classes presentes | ALERTA | Todas as 8 classes contábeis devem estar na MSC |
| R074 | Cada chave com SF ou PC | ALERTA | Toda chave contábil deve ter saldo final ou movimentação |
| R071 | Valores com > 2 decimais | INFO | Valores devem estar em R$ 1,00 (sem centavos parciais) |
| R072 | Contas com registros atípicos | INFO | Contagem de registros outlier para uma conta |
| R073 | Valores outliers extremos | INFO | Valores muito acima/abaixo do esperado para a conta |

### SIGEF — Saldo Invertido (3 regras) — Task F4-16

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R086 | Ativo credor invertido | ALERTA | Conta de Ativo (classe 1) com saldo credor anômalo |
| R087 | Passivo devedor invertido | ALERTA | Conta de Passivo (classe 2) com saldo devedor anômalo |
| R088 | PL invertido | ALERTA | PL (classe 2.3) com saldo devedor anômalo |

### SIGEF — IC Detalhamento Faltante (5 regras) — Task F4-17

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R089 | Receita sem FR | ALERTA | Contas de receita devem ter Fonte de Recursos |
| R090 | Receita sem NR | ALERTA | Contas de receita devem ter Natureza da Receita |
| R091 | Despesa sem ND | ALERTA | Contas de despesa devem ter Natureza da Despesa |
| R092 | Despesa sem FS | ALERTA | Contas de despesa devem ter Função/Subfunção |
| R093 | Despesa sem FR | ALERTA | Contas de despesa devem ter Fonte de Recursos |

### SIGEF — Temporal/Completude (3 regras) — Task F4-18

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R083 | Dados executivo iguais entre meses | ALERTA | Saldos idênticos ao mês anterior indicam falta de movimentação |
| R084 | Conta Financeira sem FR | ALERTA | Conta financeira deve ter FR preenchida |
| R085 | Depreciação sem movimentação | ALERTA | Contas de depreciação devem ter período_change |

---

## Tasks por Fase — Estado Atualizado

### Fase 0 — Frontend MCRA ✅ Concluída

| ID | Descrição | Status |
|---|---|---|
| F0-00.A | Scaffold (Vite+React+TS, tokens, layout shell, FastAPI shell) | ✅ `64fb6ee` |
| F0-00.B | Run + Pendências + Score (upload → score → 6m → top 8) | ✅ `8626586` |
| F0-00.C | Regras + Drawers (heatmap 35×6, drawer Regra/Conta) | ✅ `3f964a3` |
| F0-00.D | Caixa / Passivos / Superávit (listagens contábeis) | ✅ `1fe127e` |
| F0-00.E | Visões (Executivo, Comparar, Execução, Ranking) | ✅ `26053d8` |
| F0-00.F | Polish + cutover Panel + README + a11y | ✅ `12951ea` |

### Fase 3 — Regras Core ✅ Concluída

| ID | Descrição | Status |
|---|---|---|
| F3-01 | R001–R005 (Estrutura) | ✅ |
| F3-02 | R011–R012 (PCASP nível e status) | ✅ |
| F3-03 | R020 (Conjunto IC correto) | ✅ |
| F3-04 | R080–R081 (Formato CONTA e IC) | ✅ |
| F3-05 | R022–R023 (FP e DC) | ✅ |
| F3-06 | R024–R025 (FR e CO) | ✅ |
| F3-07 | R026–R028 (NR, ND, FS) | ✅ |
| F3-08 | R029 (AI — Ano Inscrição RP) | ✅ |
| F3-09 | R031 (SF = SI + Movimentos) | ✅ |
| F3-10 | R032 (Natureza saldo compatível) | ✅ |
| F3-11 | R070 (Duplicidade) | ✅ |
| F3-12 | Testes integração CSV real | ✅ |
| F3-13 | R040–R043 (Completude) | ✅ |
| F3-14 | R050–R052 (Interconta) | ✅ |
| F3-15 | R060 (FP vs IND_SF) | ✅ |
| F3-16 | Relatório com todas regras + categorias | ⏳ Parcial (Excel OK, mas sem aba separada por categoria) |

### Fase 4 — Scoring + Cobertura Total 🟡 Em Andamento

| ID | Descrição | Horas | Dep. | Status |
|---|---|---|---|---|
| F4-01 | Modelo de pontuação (scoring 0-100) | 8 | — | ✅ |
| F4-02 | `score_engine.py` (nota por dimensão + banda A-E) | 10 | F4-01 | ✅ |
| F4-03 | Aba Score no Excel | 8 | F4-02 | ✅ |
| F4-04 | Batch — processar múltiplos CSVs | 8 | — | ✅ |
| F4-05 | `compare_periods.py` (evolução temporal) | 8 | F4-02 | ✅ |
| F4-06 | Relatório consolidado multi-competência | 8 | F4-05 | ✅ |
| F4-07 | Regras Estrutura R006–R0011 (6 regras) | 6 | — | ❌ A Fazer |
| F4-08 | Benchmark de performance (>100k linhas) | 6 | F4-04 | ❌ A Fazer |
| F4-09 | Otimizar regras com operações vetorizadas | 8 | F4-08 | ❌ A Fazer |
| F4-10 | Encoding robusto (UTF-8/Latin-1/CP1252 auto) | 6 | — | ❌ A Fazer |
| F4-11 | Regras IC completude R033, R034, R038, R082 | 5 | R020 | ❌ A Fazer |
| F4-12 | Regras domínio complementares (9 regras) | 10 | R020-R028 | ❌ A Fazer |
| F4-13 | Regras Fechamento por classe R035–R037 | 4 | R030 | ❌ A Fazer |
| F4-14 | Superávit + Interconta R053, R061, R062 | 4 | R060, R010 | ❌ A Fazer |
| F4-15 | Completude + Qualidade (7 regras) | 8 | R026, R027 | ❌ A Fazer |
| F4-16 | SIGEF — Saldo invertido R086–R088 | 4 | R032, R010 | ❌ A Fazer |
| F4-17 | SIGEF — IC detalhamento R089–R093 | 5 | R020, R024-R028 | ❌ A Fazer |
| F4-18 | SIGEF — Temporal/Completude R083–R085 | 5 | R054, R022 | ❌ A Fazer |
| F4-19 | Extrair helpers CLI compartilhados | 3 | F4-04 | ❌ A Fazer |
| F4-20 | Documentação Fase 4 + handoff Fase 5 | 4 | tudo | ❌ A Fazer |

### Fase 0 — Tasks Pós-Frontend (pendentes do plan)

| ID | Descrição | Prioridade | Status |
|---|---|---|---|
| F0-01 | Lint + build TS no CI (GitHub Action) | Alta | ❌ A Fazer |
| F0-02 | Recommendations engine (heurísticas avançadas) | Média | ❌ A Fazer |
| F0-03 | Ranking Regional — fonte de dados (dataset de outros entes) | Baixa | ❌ A Fazer |
| F0-04 | Superávit financeiro por FR (derivação contábil) | Média | ❌ A Fazer |
| F0-05 | Panel cutover definitivo (remover `web_app_legacy.py` + deps) | Alta | ❌ Bloqueado (esperar 1-2 sprints) |
| F0-06 | Exportar PDF (HTML→PDF para Visão Executiva) | Alta | ❌ A Fazer |
| F0-07 | Autenticação multiusuário (JWT + namespacing) | Alta | ❌ A Fazer |
| F0-08 | Deploy (Docker multi-stage + nginx + compose) | Alta | ❌ A Fazer |

---

## Gap de Regras por Categoria

| Categoria | Implementadas | Total | Faltam | Task |
|---|:---:|:---:|:---:|---|
| Estrutura | 6 | 12 | 6 | F4-07 |
| PCASP | 5 | 5 | 0 | — |
| IC | 9 | 14 | 5 | F4-11 (+1 em F4-12) |
| PO | 1 | 2 | 1 | F4-12 |
| Fechamento | 2 | 6 | 4 | F4-13 (3) + F3-16 (1) |
| Interconta | 3 | 4 | 1 | F4-14 |
| Superávit | 1 | 3 | 2 | F4-14 |
| Completude | 4 | 8 | 4 | F4-15 |
| Temporal | 3 | 3 | 0 | — |
| Duplicidade | 1 | 1 | 0 | — |
| Formato | 2 | 2 | 0 | — |
| Qualidade | 0 | 3 | 3 | F4-15 |
| SIGEF Saldo | 0 | 3 | 3 | F4-16 |
| SIGEF IC | 0 | 5 | 5 | F4-17 |
| SIGEF Temporal | 0 | 3 | 3 | F4-18 |
| **Total** | **35** | **78** | **43** | |

---

## Prioridade Sugerida (Próximos Passos)

### 🔴 Prioridade 1 — Cobertura de Regras (Motor)

1. **F4-07** — Estrutura R006–R0011 (bloqueadores, simples) — ~6h
2. **F4-11** — IC completude R033–R034, R038, R082 — ~5h
3. **F4-13** — Fechamento por classe R035–R037 — ~4h
4. **F4-14** — Superávit R061–R062 + Interconta R053 — ~4h
5. **F4-12** — Domínio complementar (9 regras) — ~10h

### 🟡 Prioridade 2 — Qualidade + SIGEF

6. **F4-15** — Completude + Qualidade (7 regras) — ~8h
7. **F4-16** — SIGEF saldo invertido R086–R088 — ~4h
8. **F4-17** — SIGEF IC detalhamento R089–R093 — ~5h
9. **F4-18** — SIGEF temporal/completude R083–R085 — ~5h

### 🟢 Prioridade 3 — Infra + Polish

10. **F4-08** — Benchmark de performance — ~6h
11. **F4-09** — Otimização vetorizada — ~8h
12. **F4-10** — Encoding robusto — ~6h
13. **F0-01** — CI lint+build — ~2h
14. **F4-19** — Extrair helpers CLI — ~3h

### 🔵 Prioridade 4 — Produção

15. **F0-06** — Exportar PDF — ~6h
16. **F0-07** — Autenticação multiusuário — ~8h
17. **F0-08** — Deploy Docker — ~8h
18. **F0-05** — Panel cutover definitivo — ~2h

### ⚪ Prioridade 5 — Nice-to-have

19. **F0-02** — Recommendations engine avançado — ~6h
20. **F0-03** — Ranking Regional (fonte de dados) — ~10h
21. **F0-04** — Superávit financeiro por FR — ~6h
22. **F4-20** — Documentação final — ~4h

---

## Métricas Atuais

| Métrica | Valor |
|---|---|
| Regras implementadas | 35 / 78 (44.9%) |
| Testes passando | 621 |
| Cobertura de categorias | 12/15 com ≥1 regra |
| Frontend telas | 10/10 navegáveis |
| Endpoints API | 19 |
| Lint (ruff + mypy + tsc + eslint) | ✅ Limpo |
| Vite build | ✅ Passando |

---

## Referências

- [regras_catalogo.md](../ref/regras_catalogo.md) — Especificação completa das 78 regras
- [fase0_plan.md](fase0_plan.md) — Plano do frontend (concluído)
- [fase3_plan.md](fase3_plan.md) — Plano de regras core (concluído)
- [fase4_plan.md](fase4_plan.md) — Plano de cobertura total + scoring
- [modelo_pontuacao.md](modelo_pontuacao.md) — Modelo de scoring 0-100 (A-E)
- [backlog_regras_msc_completo.xlsx](../backlog_regras_msc_completo.xlsx) — Planilha original do catálogo
