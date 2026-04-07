# Design — F3-14: Regras R050–R052 (Interconta)

**Data:** 2026-04-07
**Task:** F3-14
**Status:** Aprovado

---

## Contexto

Implementação das três regras de Interconta da Fase 3. São verificações de equilíbrio
global entre classes contábeis (não por linha). Todas dependem de R031 (SF = SI + Mov)
já implementada.

---

## Regras

### R050 — Ativo = Passivo + PL
- **Severidade:** ERRO | **Prioridade:** P1
- **Dimensão:** Interconta

**Lógica:**
```
ativo   = SUM(saldo_final_debito - saldo_final_credito)  para conta[0] == "1"
passivo = SUM(saldo_final_credito - saldo_final_debito)  para conta[0] == "2"
SE abs(ativo - passivo) > TOLERANCIA_CENTAVO → ERRO
```

Uma única pendência global por competência. `conta_contabil` vazia na pendência.

---

### R051 — VPA − VPD = Resultado
- **Severidade:** ALERTA | **Prioridade:** P2
- **Dimensão:** Interconta

**Lógica:**
```
vpa_liq   = SUM(movimento_credito - movimento_debito)  para conta[0] == "4"
vpd_liq   = SUM(movimento_debito  - movimento_credito) para conta[0] == "3"
resultado = vpa_liq - vpd_liq

delta_pl  = [SUM(SF_C - SF_D) - SUM(SI_C - SI_D)]  para conta[:3] == "214"
SE abs(resultado - delta_pl) > TOLERANCIA_CENTAVO → ALERTA
```

Compara resultado operacional (VPA−VPD) com a variação do grupo Resultados Acumulados
(PCASP 2.1.4, códigos prefixo "214"). Uma única pendência global.

**Limitação conhecida:** ajustes diretos no PL que não transitam por classes 3/4
(doações, correções) podem gerar falso ALERTA. Isso é esperado e por isso a severidade
é ALERTA.

**Edge case:** se o DF não tiver nenhuma conta com prefixo "214", a regra retorna vazio
(sem pendência) — não é possível validar sem os dados de PL.

---

### R052 — Controles devedores = Controles credores (7/8)
- **Severidade:** ALERTA | **Prioridade:** P3
- **Dimensão:** Interconta

**Lógica:**
```
ctrl_d = SUM(saldo_final_debito - saldo_final_credito)  para conta[0] == "7"
ctrl_c = SUM(saldo_final_credito - saldo_final_debito)  para conta[0] == "8"
SE abs(ctrl_d - ctrl_c) > TOLERANCIA_CENTAVO → ALERTA
```

Uma única pendência global. `conta_contabil` vazia na pendência.

---

## Arquitetura

### Abordagem escolhida
Uma regra por arquivo, sem helper compartilhado (Abordagem A). Lógica de classe de conta
via `conta[0]` — simples demais para justificar abstração.

### Arquivos a criar
| Arquivo | Conteúdo |
|---|---|
| `src/ranking_msc/rules/r050.py` | Classe R050 |
| `src/ranking_msc/rules/r051.py` | Classe R051 |
| `src/ranking_msc/rules/r052.py` | Classe R052 |
| `tests/test_r050_r052.py` | Testes das 3 regras |

### Arquivos a modificar
| Arquivo | Mudança |
|---|---|
| `src/ranking_msc/rules/__init__.py` | 3 imports (R050, R051, R052) |
| `config/settings.yaml.example` | Adicionar R050, R051, R052 na lista enabled |
| `doc/fase3_plan.md` | F3-13 → concluída; F3-14 → concluída |

---

## Testes

### R050
- `test_r050_balanceado_sem_pendencia` — ativo == passivo+PL → sem pendência
- `test_r050_desequilibrio_gera_erro` — ativo ≠ passivo+PL → 1 pendência, severidade ERRO
- `test_r050_df_vazio_sem_pendencia` — DF vazio → sem pendência

### R051
- `test_r051_consistente_sem_pendencia` — VPA−VPD == delta_PL → sem pendência
- `test_r051_divergencia_gera_alerta` — resultado ≠ delta_PL → 1 pendência, severidade ALERTA
- `test_r051_sem_contas_214_sem_pendencia` — sem contas 214 → sem pendência (skip)

### R052
- `test_r052_balanceado_sem_pendencia` — ctrl_7 == ctrl_8 → sem pendência
- `test_r052_desequilibrio_gera_alerta` — ctrl_7 ≠ ctrl_8 → 1 pendência, severidade ALERTA
- `test_r052_sem_contas_controle_sem_pendencia` — DF sem classes 7/8 → sem pendência

---

## Padrão de pendência

Todas as regras retornam uma pendência com:
- `conta_contabil`: `""` (verificação global)
- `valor_esperado`: valor calculado (ex: `"ativo=1000.00"`)
- `valor_encontrado`: valor real (ex: `"passivo_pl=999.99"`)
- `descricao`: mensagem em português explicando a divergência
