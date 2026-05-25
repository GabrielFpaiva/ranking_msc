# Backlog Consolidado — Ranking MSC

> **Atualizado:** 2026-05-25
> **Estado atual:** 78 regras implementadas · 944 testes coletados · **Fase 4 concluída (F4-01→F4-20)** · Fase 5 em andamento (F5-01, F5-02, F5-03 e F5-05 ✅) · gate `validate` verde na branch corrente

---

## Visão Geral

O projeto contém **78 regras** no catálogo total (67 originais + 11 SIGEF/JPA).
Destas, **78 estão implementadas** e habilitadas. Restam **0 regras** a implementar.

O frontend React+FastAPI (Fase 0) está concluído. O motor Python está estável.

### Resumo por Fase

| Fase | Escopo | Status | Commits |
|---|---|---|---|
| Fase 2 | Infraestrutura + 5 regras piloto + Pipeline | ✅ Concluída | 190 testes |
| Fase 3 | Catálogo expandido → 35 regras | ✅ Concluída | 471 testes |
| Fase 4 | Scoring + Batch + Compare + regras restantes | ✅ Concluída | 944 testes |
| Fase 0 | Frontend MCRA (React+FastAPI replacing Panel) | ✅ Concluída | 8 commits |
| Fase 5 | Produção (export, auth, deploy, docs, entrega) | 📋 Backlog | — |

---

## Regras Implementadas (78/78)

| Regra | Dimensão | Nome | Sev. | Fase |
|---|---|---|---|---|
| R001 | Estrutura | Colunas obrigatórias presentes | ERRO | F3 ✅ |
| R002 | Estrutura | CONTA preenchida em todas as linhas | ERRO | F3 ✅ |
| R003 | Estrutura | Tipo_valor válido | ERRO | F2 ✅ |
| R004 | Estrutura | Natureza_valor válida | ERRO | F2 ✅ |
| R005 | Estrutura | Valor numérico válido | ERRO | F3 ✅ |
| R006 | Estrutura | Código SICONFI válido | ERRO | F4 ✅ |
| R007 | Estrutura | Período válido | ERRO | F4 ✅ |
| R008 | Estrutura | Separador de campo correto | ERRO | F4 ✅ |
| R009 | Estrutura | Sem colunas extras não previstas | ALERTA | F4 ✅ |
| R0010 | Estrutura | Header após metadata | ERRO | P0 ✅ |
| R0011 | Estrutura | Valor não-negativo | ERRO | P0 ✅ |
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
| R033 | IC | Pares IC/TIPO presentes | ERRO | F4 ✅ |
| R034 | IC | PO obrigatório | ERRO | F4 ✅ |
| R038 | IC | IC × conta conforme leiaute | ERRO | F4 ✅ |
| R082 | IC | Ordem das ICs no arquivo | ALERTA | F4 ✅ |
| R035 | Fechamento | D=C patrimonial (classes 1-4) | ERRO | F4 ✅ |
| R036 | Fechamento | D=C orçamentário (classes 5-6) | ERRO | F4 ✅ |
| R037 | Fechamento | D=C controle (classes 7-8) | ERRO | F4 ✅ |
| R053 | Interconta | INTRA OFSS com contrapartida | ALERTA | F4 ✅ |
| R061 | Superávit | Conta Financeira sem FP=2 | ALERTA | F4 ✅ |
| R062 | Superávit | Conta Permanente sem FP=1 | ALERTA | F4 ✅ |
| R066 | Completude | Receita presente (classe 4) | ALERTA | F4 ✅ |
| R067 | Completude | Despesa presente (classe 3) | ALERTA | F4 ✅ |
| R068 | Completude | 8 classes presentes | ALERTA | F4 ✅ |
| R071 | Qualidade | Valores com > 2 decimais | INFO | F4 ✅ |
| R072 | Qualidade | Contas com registros atípicos | INFO | F4 ✅ |
| R073 | Qualidade | Valores outliers extremos | INFO | F4 ✅ |
| R074 | Completude | Cada chave com SF ou PC | ALERTA | F4 ✅ |
| R039 | PO | PO compatível com esfera do ente | ALERTA | F4 ✅ |
| R044 | IC | NR é valorizável (último nível) | ALERTA | F4 ✅ |
| R045 | IC | ND é último nível | ALERTA | F4 ✅ |
| R046 | IC | ND não genérica | ALERTA | F4 ✅ |
| R047 | IC | ND subelementos = elemento pai | ALERTA | F4 ✅ |
| R048 | IC | FR — 1º dígito válido | ALERTA | F4 ✅ |
| R063 | IC | DC só em contas permitidas | ERRO | F4 ✅ |
| R064 | IC | CO × tipo de conta | ALERTA | F4 ✅ |
| R065 | IC | FS combinação atípica | INFO | F4 ✅ |
| R086 | SIGEF Saldo | Ativo credor invertido | ALERTA | F4 ✅ |
| R087 | SIGEF Saldo | Passivo devedor invertido | ALERTA | F4 ✅ |
| R088 | SIGEF Saldo | PL invertido | ALERTA | F4 ✅ |
| R089 | SIGEF IC | Receita sem FR | ALERTA | F4 ✅ |
| R090 | SIGEF IC | Receita sem NR | ALERTA | F4 ✅ |
| R091 | SIGEF IC | Despesa sem ND | ALERTA | F4 ✅ |
| R092 | SIGEF IC | Despesa sem FS | ALERTA | F4 ✅ |
| R093 | SIGEF IC | Despesa sem FR | ALERTA | F4 ✅ |
| R083 | SIGEF Temporal | Dados executivo iguais entre meses | ALERTA | F4 ✅ |
| R084 | SIGEF Temporal | Conta Financeira sem FR | ALERTA | F4 ✅ |
| R085 | SIGEF Temporal | Depreciação sem movimentação | ALERTA | F4 ✅ |

---

## Regras Pendentes (0/78)

### ~~Domínio Complementar (9 regras) — Task F4-12~~ ✅ Concluído

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

### ~~Fechamento por Classe (3 regras) — Task F4-13~~ ✅ Concluído

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R035 | D=C patrimonial total | ERRO | Débito = Crédito classes 1-4 (patrimonial) |
| R036 | D=C orçamentário | ERRO | Débito = Crédito classes 5-6 (orçamentário) |
| R037 | D=C controle | ERRO | Débito = Crédito classes 7-8 (controle) |

### ~~Superávit + Interconta (3 regras) — Task F4-14~~ ✅ Concluído

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R053 | INTRA OFSS com contrapartida | ALERTA | Operações intra têm saldo simétrico |
| R061 | Conta Financeira sem FP=2 | ALERTA | Conta financeira (IND_SF=S) não pode ter FP=2 |
| R062 | Conta Permanente sem FP=1 | ALERTA | Conta permanente (IND_SF=N) não pode ter FP=1 |

### ~~Completude + Qualidade (7 regras) — Task F4-15~~ ✅ Concluído

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R066 | Receita presente | ALERTA | Classe 4 (VPA) deve ter registros |
| R067 | Despesa presente | ALERTA | Classe 3 (VPD) deve ter registros |
| R068 | 8 classes presentes | ALERTA | Todas as 8 classes contábeis devem estar na MSC |
| R074 | Cada chave com SF ou PC | ALERTA | Toda chave contábil deve ter saldo final ou movimentação |
| R071 | Valores com > 2 decimais | INFO | Valores devem estar em R$ 1,00 (sem centavos parciais) |
| R072 | Contas com registros atípicos | INFO | Contagem de registros outlier para uma conta |
| R073 | Valores outliers extremos | INFO | Valores muito acima/abaixo do esperado para a conta |

### ~~Estrutura residual (2 regras) — Issue #80~~ ✅ Concluído

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R0010 | Cabeçalho na primeira linha | ERRO | Primeira linha é header, não dados |
| R0011 | Valor não-negativo | ERRO | Campo Valor ≥ 0 (escala R$ 1,00) |

### ~~SIGEF — Saldo Invertido (3 regras) — Task F4-16~~ ✅ Concluído

| Regra | Nome | Sev. | Descrição |
|---|---|---|---|
| R086 | Ativo credor invertido | ALERTA | Conta de Ativo (classe 1) com saldo credor anômalo |
| R087 | Passivo devedor invertido | ALERTA | Conta de Passivo (classe 2) com saldo devedor anômalo |
| R088 | PL invertido | ALERTA | PL (classe 2.3) com saldo devedor anômalo |

### ~~SIGEF — IC Detalhamento Faltante (5 regras) — Task F4-17~~ ✅ Concluído

| Regra | Nome | Sev. | Status |
|---|---|---|---|
| R089 | Receita sem FR | ALERTA | ✅ |
| R090 | Receita sem NR | ALERTA | ✅ |
| R091 | Despesa sem ND | ALERTA | ✅ |
| R092 | Despesa sem FS | ALERTA | ✅ |
| R093 | Despesa sem FR | ALERTA | ✅ |

### ~~SIGEF — Temporal/Completude (3 regras) — Task F4-18~~ ✅ Concluído

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

### Fase 4 — Scoring + Cobertura Total ✅ Concluída

| ID | Descrição | Horas | Dep. | Status |
|---|---|---|---|---|
| F4-01 | Modelo de pontuação (scoring 0-100) | 8 | — | ✅ |
| F4-02 | `score_engine.py` (nota por dimensão + banda A-E) | 10 | F4-01 | ✅ |
| F4-03 | Aba Score no Excel | 8 | F4-02 | ✅ |
| F4-04 | Batch — processar múltiplos CSVs | 8 | — | ✅ |
| F4-05 | `compare_periods.py` (evolução temporal) | 8 | F4-02 | ✅ |
| F4-06 | Relatório consolidado multi-competência | 8 | F4-05 | ✅ |
| F4-07 | Regras Estrutura R006–R009 (4 regras) | 6 | — | ✅ PR #63 |
| F4-08 | Benchmark de performance (>100k linhas) | 6 | F4-04 | ✅ PR #64 |
| F4-09 | Otimizar regras com operações vetorizadas | 8 | F4-08 | ✅ PR #67 |
| F4-10 | Encoding robusto (UTF-8/Latin-1/CP1252 auto) | 6 | — | ✅ PR #68 |
| F4-11 | Regras IC completude R033, R034, R038, R082 | 5 | R020 | ✅ Concluído |
| F4-12 | Regras domínio complementares (9 regras) | 10 | R020-R028 | ✅ Concluído |
| F4-13 | Regras Fechamento por classe R035–R037 | 4 | R030 | ✅ Concluído |
| F4-14 | Superávit + Interconta R053, R061, R062 | 4 | R060, R010 | ✅ Concluído |
| F4-15 | Completude + Qualidade (7 regras) | 8 | R026, R027 | ✅ Concluído |
| F4-16 | SIGEF — Saldo invertido R086–R088 | 4 | R032, R010 | ✅ Concluído |
| F4-17 | SIGEF — IC detalhamento R089–R093 | 5 | R020, R024-R028 | ✅ Concluído |
| F4-18 | SIGEF — Temporal/Completude R083–R085 | 5 | R054, R022 | ✅ Concluído |
| F4-19 | Extrair helpers CLI compartilhados | 3 | F4-04 | ✅ Concluído |
| F4-20 | Documentação Fase 4 + handoff Fase 5 | 4 | tudo | ✅ Concluído |

### Fase 5 — Produção + Entrega 📋 Backlog

> Os itens originais F5-01 a F5-06 do Excel (Dashboard Panel) foram absorvidos pela
> Fase 0 (React+FastAPI). A Fase 5 agora foca em produção, entrega e fechamento.

| ID | Descrição | Horas | Dep. | Status | Origem |
|---|---|---|---|---|---|
| F5-01 | CI completo — adicionar lint+build TS no GitHub Action | 2 | — | ✅ Concluído | F0-01 |
| F5-02 | Cutover Panel — remover `web_app_legacy.py` + deps | 1 | — | ✅ Concluído | F0-05 |
| F5-03 | Exportar PDF — Visão Executiva HTML→PDF | 6 | — | ✅ Concluído | F0-06 / F5-06(xlsx) |
| F5-04 | Autenticação multiusuário (JWT + namespacing) | 8 | — | ❌ A Fazer | F0-07 |
| F5-05 | Deploy Docker (multi-stage + compose + .dockerignore) | 8 | — | ✅ Concluído | F0-08 / F5-07(xlsx) |
| F5-06 | Testes end-to-end no ambiente de deploy | 4 | F5-05 | ❌ A Fazer | F5-08(xlsx) |
| F5-07 | Manual do usuário + guia de operação | 6 | — | ❌ A Fazer | F5-09(xlsx) |
| F5-08 | Documentar settings.yaml + variáveis de ambiente prod | 2 | F5-05 | ❌ A Fazer | Novo |
| F5-09 | Buffer: correção de bugs e ajustes finais (`validate` restaurado em 2026-05-25) | 4 | — | 🟡 Parcial | F5-10(xlsx) |
| F5-10 | Treinamento / demo para equipe contábil | 4 | F5-07 | ❌ A Fazer | F5-11(xlsx) |
| F5-11 | Entrega final + handoff operacional | 2 | tudo | ❌ A Fazer | F5-12(xlsx) |

### Nice-to-have (sem fase atribuída)

| ID | Descrição | Horas | Status |
|---|---|---|---|
| F0-02 | Recommendations engine (heurísticas avançadas) | 6 | ❌ A Fazer |
| F0-03 | Ranking Regional — fonte de dados (dataset de outros entes) | 10 | ❌ A Fazer |
| F0-04 | Superávit financeiro por FR (derivação contábil) | 6 | ✅ Concluído |
| #98 | Separar `compare_periods` de `outputs.snapshot` | 4 | ✅ Concluído |

### Backlog Executável — Superávit por FR (F0-04)

> Objetivo: substituir o `501` atual da rota `/api/superavit` por uma visão
> funcional de resultado financeiro por Fonte de Recursos (FR), usando os
> snapshots já gerados pelo motor.

| ID | Task | Entrega | Dep. | Estimativa | Status |
|---|---|---|---|---|---|
| S1 | Definir regra contábil do cálculo | Lista fechada de contas/prefixos de ativo financeiro e passivo financeiro, com convenção de sinal validada | — | 2-4h | ✅ Concluído |
| S2 | Implementar agregador puro no motor | Função nova em `src/ranking_msc/outputs/aggregations.py` para agrupar por `FR` e calcular ativo, passivo e resultado | S1 | 3-5h | ✅ Concluído |
| S3 | Criar schema da API | Modelos novos em `app/api/schemas.py` para payload do superávit | S2 | 1h | ✅ Concluído |
| S4 | Implementar rota `/api/superavit` | Substituir `501` em `app/api/routes/superavit.py` por resposta funcional | S2, S3 | 1-2h | ✅ Concluído |
| S5 | Tipar integração do frontend | Atualizar `web/src/types.ts` e `web/src/api/client.ts` para consumir payload tipado | S3, S4 | 1h | ✅ Concluído |
| S6 | Implementar tela funcional | Substituir placeholder em `web/src/screens/Superavit.tsx` por total + tabela por FR | S5 | 2-4h | ✅ Concluído |
| S7 | Cobrir com testes | Testes unitários do agregador + API + ajuste do teste que hoje espera `501` | S2-S6 | 2-4h | ✅ Concluído |

**Especificação S1 — regra contábil proposta**

- **Base normativa interna do projeto:** usar o campo `ind_sf` do `pcasp.csv`
  como critério de classificação contábil, coerente com as regras `R061` e
  `R062`.
- **Filtro de escopo:** considerar apenas linhas da MSC normalizada com `fr`
  informada e não vazia. A visão é “resultado financeiro por FR”, então linha
  sem `FR` não entra no cálculo consolidado.
- **Bloco Ativo Financeiro:** linhas cuja `conta_contabil` esteja no PCASP com
  `ind_sf == "Financeiro"` e natureza de saldo devedora líquida.
- **Bloco Passivo Financeiro:** linhas cuja `conta_contabil` esteja no PCASP com
  `ind_sf == "Financeiro"` e natureza de saldo credora líquida.
- **Bloco híbrido (`Financeiro/Permanente`):** excluir da primeira versão do
  cálculo. Essas contas exigem critério adicional e não devem contaminar o
  resultado da `S2`.
- **Bloco Permanente:** excluir do cálculo. Contas com `ind_sf == "Permanente"`
  não participam do superávit financeiro por FR.
- **Valor base por linha:** usar saldo final líquido da linha:
  `saldo_final_debito - saldo_final_credito`.
- **Sinal contábil consolidado:**
  ativo financeiro positivo = `saldo_final_debito - saldo_final_credito`;
  passivo financeiro positivo = `saldo_final_credito - saldo_final_debito`.
- **Agregação por FR:**
  1. somar os valores do bloco de ativo financeiro por `FR`;
  2. somar os valores do bloco de passivo financeiro por `FR`;
  3. calcular `resultado_financeiro = ativo_financeiro - passivo_financeiro`.
- **Campos mínimos esperados na resposta:** `fr`, `ativo_financeiro`,
  `passivo_financeiro`, `resultado_financeiro`.
- **Ordenação padrão da visão:** por `resultado_financeiro` decrescente, com
  opção futura de ordenar por código `FR`.
- **Tratamento de qualidade de dado:**
  linhas com conta sem match no PCASP ficam fora do cálculo;
  linhas com `FR` vazia ficam fora do cálculo;
  linhas com `ind_sf` ausente ficam fora do cálculo.
- **Validação cruzada recomendada antes do go-live:** comparar o total por `FR`
  com um recorte manual de 1 competência real do PMJP para confirmar que a
  classificação `Financeiro` no PCASP basta para a visão desejada.

**Observação de escopo:**

- Esta especificação privilegia consistência com o que já existe no projeto
  hoje (`PCASP.ind_sf`, `R061`, `R062`, `FP`, `FR`) e minimiza heurística por
  prefixo de conta.
- Se a área contábil exigir inclusão de contas `Financeiro/Permanente`, isso
  deve gerar uma revisão explícita da `S1` antes de implementar a `S2`.

**Resumo técnico:**

- Arquivos principais: `app/api/routes/superavit.py`, `app/api/schemas.py`,
  `src/ranking_msc/outputs/aggregations.py`, `web/src/types.ts`,
  `web/src/api/client.ts`, `web/src/screens/Superavit.tsx`.
- Status atual: backend, frontend e testes do `superavit` concluídos; eventual
  refinamento futuro depende apenas de validação contábil fina com a equipe.
- Risco principal: definição contábil incorreta dos blocos de ativo/passivo
  financeiro.
- Faixa estimada total: **10-20h**.

### Backlog Executável — Ranking Regional (F0-03)

> Objetivo: recolocar o ranking regional na superfície pública quando existir
> uma visão comparativa real do PMJP frente a outros entes, baseada em uma
> fonte benchmark externa ou consolidada.

| ID | Task | Entrega | Dep. | Estimativa | Status |
|---|---|---|---|---|---|
| R1 | Definir fonte oficial do benchmark | Decisão entre planilha consolidada, import manual de CSVs ou outra base comparável | — | 2-6h | ❌ A Fazer |
| R2 | Definir formato canônico da base regional | Esquema mínimo com ente, `siconfi`, competência, pontuação, banda e pendências | R1 | 1-2h | ❌ A Fazer |
| R3 | Criar loader/serviço da base regional | Módulo novo em `src/ranking_msc/io/` ou `src/ranking_msc/outputs/` para leitura/normalização do benchmark | R2 | 3-5h | ❌ A Fazer |
| R4 | Implementar agregação de ranking | Cálculo de posição do PMJP, total de entes, mediana, top 10 e vizinhos | R3 | 2-4h | ❌ A Fazer |
| R5 | Criar schema da API | Modelos novos em `app/api/schemas.py` para payload do ranking | R4 | 1h | ❌ A Fazer |
| R6 | Implementar rota `/api/ranking` | Reintroduzir a rota pública com resposta funcional quando a base benchmark existir | R4, R5 | 1-2h | ❌ A Fazer |
| R7 | Tipar integração do frontend | Atualizar `web/src/types.ts` e `web/src/api/client.ts` para consumir payload tipado | R5, R6 | 1h | ❌ A Fazer |
| R8 | Implementar tela funcional | Reintroduzir a tela pública de ranking com posição, mediana e tabela comparativa | R7 | 2-4h | ❌ A Fazer |
| R9 | Cobrir com testes | Testes do loader, agregação e API; ajuste dos contratos ao reexpor a feature | R3-R8 | 2-4h | ❌ A Fazer |

**Resumo técnico:**

- Arquivos principais: `app/api/routes/ranking.py`, `app/api/schemas.py`,
  `web/src/types.ts`, `web/src/api/client.ts`, `web/src/screens/Ranking.tsx`,
  mais um módulo novo para leitura/agregação da base benchmark.
- Risco principal: indisponibilidade ou má definição da base comparativa.
- Status de execução: permanece bloqueado até definição e obtenção da base
  benchmark externa. Não há implementação parcial iniciada nesta frente.
- Faixa estimada total: **13-28h** fora o esforço político/operacional para
  obtenção da base.

---

## Gap de Regras por Categoria

| Categoria | Implementadas | Total | Faltam | Task |
|---|:---:|:---:|:---:|---|
| Estrutura | 12 | 12 | 0 | Issue #80 ✅ |
| PCASP | 5 | 5 | 0 | — |
| IC | 21 | 22 | 0 | F4-12 ✅ |
| PO | 2 | 2 | 0 | F4-12 ✅ |
| Fechamento | 5 | 6 | 1 | F3-16 (1) |
| Interconta | 4 | 4 | 0 | F4-14 ✅ |
| Superávit | 3 | 3 | 0 | F4-14 ✅ |
| Completude | 8 | 8 | 0 | F4-15 ✅ |
| Temporal | 3 | 3 | 0 | — |
| Duplicidade | 1 | 1 | 0 | — |
| Formato | 2 | 2 | 0 | — |
| Qualidade | 3 | 3 | 0 | F4-15 ✅ |
| SIGEF Saldo | 3 | 3 | 0 | F4-16 ✅ |
| SIGEF IC | 5 | 5 | 0 | F4-17 ✅ |
| SIGEF Temporal | 3 | 3 | 0 | F4-18 ✅ |
| **Total** | **78** | **78** | **0** | |

---

## Prioridade Sugerida (Próximos Passos)

### 🟡 Prioridade 1 — Hardening de Produção

1. **F5-06** — Testes E2E no ambiente de deploy — ~4h
2. **F5-08** — Documentar `settings.yaml` + variáveis de ambiente de produção — ~2h
3. **F5-04** — Autenticação multiusuário (JWT + namespacing) — ~8h
4. **F5-09** — Buffer de bugs e ajustes finais — manter aberto até fechar os itens acima

### 🟢 Prioridade 2 — Operação e Entrega

5. **F5-07** — Manual do usuário + guia de operação — ~6h
6. **F5-10** — Treinamento / demo para equipe contábil — ~4h
7. **F5-11** — Entrega final + handoff operacional — ~2h

### 🔵 Prioridade 3 — Nice-to-have

8. **F0-02** — Recommendations engine — ~6h
9. **F0-03** — Ranking Regional — ~10h
10. Refinamento contábil do superávit por FR, se a equipe exigir tratar contas `Financeiro/Permanente`

---

## Métricas Atuais

| Métrica | Valor |
|---|---|
| Regras implementadas | 78 / 78 (100%) |
| Testes coletados | 944 |
| Cobertura de categorias | 15/15 com ≥1 regra |
| Gate `validate` | Verde em 2026-05-25 (`ruff` + `mypy` + `pytest` + frontend lint/typecheck/build) |
| Frontend telas | 10/10 navegáveis |
| Endpoints API | 19 |
| Lint (ruff + mypy + tsc + eslint) | ✅ OK (ESLint com 2 warnings de Fast Refresh) |
| Vite build | ✅ Passando |

---

## Rastreabilidade — Fase 5 Excel Original vs. Atual

| ID Excel | Descrição Excel Original | Mapeamento Atual |
|---|---|---|
| F5-01 | Setup Dashboard Panel | ✅ Absorvido pela Fase 0 (React+FastAPI) |
| F5-02 | Upload CSV via dashboard | ✅ Absorvido pela Fase 0 |
| F5-03 | Aba Score e ranking visual | ✅ Absorvido pela Fase 0 |
| F5-04 | Pendências com filtros interativos | ✅ Absorvido pela Fase 0 |
| F5-05 | Evolução temporal | ✅ Absorvido pela Fase 0 |
| F5-06 | Export do relatório | ✅ Excel e PDF entregues → F5-03 novo concluído |
| F5-07 | Deploy local Docker | ✅ Entregue → F5-05 novo concluído |
| F5-08 | Testes E2E deploy | ❌ Pendente → F5-06 novo |
| F5-09 | Manual do usuário | ❌ Pendente → F5-07 novo |
| F5-10 | Buffer bugs/ajustes | 🟡 Parcial → F5-09 novo |
| F5-11 | Treinamento/demo | ❌ Pendente → F5-10 novo |
| F5-12 | Entrega final + handoff | ❌ Pendente → F5-11 novo |

---

## Referências

- [regras_catalogo.md](../ref/regras_catalogo.md) — Especificação completa das 78 regras
- [README.md](../README.md) — Visão geral, setup e comandos
- [CLAUDE.md](../CLAUDE.md) — Convenções operacionais do repositório
- [fase0_plan.md](fase0_plan.md) — Plano do frontend e pendências F0-03/F0-04
- [modelo_pontuacao.md](modelo_pontuacao.md) — Modelo de scoring 0-100 (A-E)
- [backlog_regras_msc_completo.xlsx](../backlog_regras_msc_completo.xlsx) — Planilha original do catálogo
