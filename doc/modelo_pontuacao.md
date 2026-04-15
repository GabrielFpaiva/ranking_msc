# Modelo de Pontuação — Ranking MSC

> **Versão:** 1.2
> **Fase:** F4 — Scoring
> **Referência:** Indicador de Conformidade Fiscal (ICF) do Ranking Siconfi / STN

---

## 1. Objetivo

Definir a fórmula, pesos e critérios de classificação para produzir uma **nota de conformidade 0–100** a partir dos resultados de validação da MSC (Matriz de Saldos Contábeis). A nota sintetiza o conjunto das 67 regras do catálogo em um único indicador comparável entre entes e entre competências.

---

## 2. Fundamentos

O modelo é inspirado no **Indicador de Conformidade Fiscal (ICF)** do Ranking Siconfi (STN), que avalia a qualidade do preenchimento da MSC com base em percentuais de conformidade por categoria.

Princípios adotados:

1. **Binário por regra** — cada regra resulta em "passou" (0 issues) ou "falhou" (≥ 1 issue). Isso evita distorção por volume: uma regra que falha em 500 linhas não vale 500× mais que uma que falha em 1.
2. **Ponderado por severidade** — regras ERRO têm impacto 2×, regras ALERTA têm impacto 1×, regras INFO não afetam a nota (são apenas informativas).
3. **Ponderado por dimensão** — grupos de categorias com maior impacto contábil recebem maior peso.
4. **Degradação graciosa para Temporal** — se o snapshot do mês anterior não está disponível, a dimensão Temporal é excluída e os pesos são renormalizados.

---

## 3. Mapeamento Categorias → Dimensões

As 20 categorias do catálogo são agrupadas em 5 dimensões:

| Dimensão | Categorias incluídas | Qtd regras | ERRO | ALERTA | INFO |
|---|---|:---:|:---:|:---:|:---:|
| **Estrutura** | Estrutura, Formato, Duplicidade | 14 | 14 | 0 | 0 |
| **Fechamento** | Fechamento, Interconta | 10 | 6 | 4 | 0 |
| **IC/Domínio** | IC, PO, NR, ND, FR, CO, FS, DC, FP, AI | 23 | 13 | 9 | 1 |
| **PCASP/Completude** | PCASP, Completude, Superávit | 14 | 2 | 11 | 1 |
| **Temporal** | Temporal, Qualidade | 6 | 0 | 3 | 3 |
| **Total** | | **67** | **35** | **27** | **5** |

> **Nota:** Regras INFO (INFO = 0 no peso de severidade) não afetam a nota — apenas aparecem no relatório como pontos de atenção.

---

## 4. Pesos das Dimensões

| Dimensão | Peso (W) | Justificativa |
|---|:---:|---|
| Estrutura | **20%** | Regras bloqueadoras — arquivo rejeitado integralmente pelo Siconfi se falhar |
| Fechamento | **25%** | Identidade contábil fundamental: D=C, SF=SI±movimentos |
| IC/Domínio | **30%** | Maior grupo do catálogo; compliance operacional do ente |
| PCASP/Completude | **15%** | Validade do plano de contas e completude das informações |
| Temporal | **10%** | Coerência entre competências; dependente de snapshot anterior |
| **Total** | **100%** | |

> **Quando Temporal indisponível** (snapshot ausente): redistribuir 10% proporcionalmente às demais dimensões.
> Pesos ajustados: Estrutura=22,2%, Fechamento=27,8%, IC/Domínio=33,3%, PCASP/Completude=16,7%.

---

## 5. Fórmula de Cálculo

### 5.1 Peso de uma regra

O peso é determinado pela **severidade observada na execução atual** — não por uma propriedade estática da regra. Várias regras do catálogo produzem ERRO *ou* ALERTA dependendo dos dados (ex.: R024, R026, R027, R028, R029), portanto não existe um `w_r` fixo que represente corretamente todos os cenários.

```
w_r(run) = 2  se a regra produziu ≥1 issue com severidade "ERRO"
           1  nos demais casos (passou sem issues, ou produziu apenas "ALERTA")
           0  se a regra produziu apenas issues "INFO" ou não foi executada
```

> Consequência: o denominador de P_d reflete o **custo real** das falhas observadas,
> não o custo hipotético máximo. ERRO-failures pesam 2×, ALERTA-failures pesam 1×,
> regras que passaram contribuem com baseline 1 (mesmo as que poderiam ter gerado ERRO).

### 5.2 Resultado de uma regra

```
ok_r = { 1  se a regra não gerou nenhum issue com w_r(run) > 0  (passou, ou apenas INFO)
       { 0  se a regra gerou ≥1 issue com severidade ERRO ou ALERTA
```

### 5.3 Pontuação de uma dimensão

```
P_d = Σ_{r ∈ d} (w_r × ok_r)  /  Σ_{r ∈ d} w_r

onde d = conjunto de regras executadas da dimensão d com w_r > 0
     (exclui regras INFO e regras desabilitadas)
```

Se `Σ w_r = 0` para a dimensão (todas as regras são INFO ou estão desabilitadas),
a dimensão é **excluída** do cálculo e os pesos `W_d` das demais dimensões ativas
são renormalizados para somar 1,0:

```python
# Renormalize quando Σ w_r = 0 para alguma dimensão
active = {d: W[d] for d in dims if sum_w[d] > 0}
w_total = sum(active.values())
W_norm = {d: w / w_total for d, w in active.items()}
```

> Isso garante que dimensões sem regras executadas não recebam crédito integral
> nem inflem artificialmente o score final.

### 5.4 Pontuação final

```
Pontuação = 100 × Σ_{d ∈ ativas} (W_norm_d × P_d)
```

onde `ativas` = dimensões com `Σ w_r > 0` e `W_norm_d` = peso renormalizado.

### 5.5 Resumo em notação compacta

```
Pontuação = 100 × Σ_{d ∈ ativas} [ W_norm_d × ( Σ_{r∈d} w_r·ok_r / Σ_{r∈d} w_r ) ]
```

---

## 6. Bandas de Classificação

Baseadas no ICF do Ranking Siconfi (STN):

| Banda | Score | Conceito |
|:---:|:---:|---|
| **A** | ≥ 95 | Excelente — conformidade quase integral |
| **B** | ≥ 85 e < 95 | Bom — pequenos desvios não bloqueadores |
| **C** | ≥ 75 e < 85 | Regular — desvios relevantes a corrigir |
| **D** | ≥ 65 e < 75 | Baixo — múltiplos ERROs em dimensões críticas |
| **E** | < 65 | Crítico — possível rejeição pelo Siconfi |

---

## 7. Exemplo de Cálculo

Cenário hipotético: competência `2025-01`, ente `250400`.

### Resultado das regras por dimensão

| Dimensão | Passaram | Falharam c/ ALERTA | Falharam c/ ERRO |
|---|:---:|:---:|:---:|
| Estrutura | 14 | 0 | 0 |
| Fechamento | 8 (5 ERRO-cap + 3 ALT-cap) | 1 | 1 |
| IC/Domínio | 18 (11 ERRO-cap + 7 ALT-cap) | 2 | 2 |
| PCASP/Completude | 11 (2 ERRO-cap + 9 ALT-cap) | 2 | 0 |
| Temporal | 3 | 0 | 0 |

> "ERRO-cap" e "ALT-cap" indicam a severidade que a regra PODE produzir.
> Para o cálculo, o que importa é a severidade **observada** nesta execução.

### Cálculo de P_d

**Regra de cálculo:** passaram → `w_r=1`, falhou-ALERTA → `w_r=1`, falhou-ERRO → `w_r=2`.

**Estrutura**
```
Passaram 14 × w=1 → numerador = 14
Denominador = 14 × 1 = 14
P_Estrutura = 14/14 = 1,000  (100%)
```

**Fechamento**
```
Passaram 8 × w=1   → numerador  = 8,   denominador += 8
Falhou ALERTA 1 × w=1            → denominador += 1
Falhou ERRO   1 × w=2            → denominador += 2
P_Fechamento = 8 / (8+1+2) = 8/11 ≈ 0,727  (72,7%)
```

**IC/Domínio**
```
Passaram 18 × w=1  → numerador  = 18,  denominador += 18
Falhou ALERTA 2 × w=1            → denominador += 2
Falhou ERRO   2 × w=2            → denominador += 4
P_IC_Domínio = 18 / (18+2+4) = 18/24 = 0,750  (75,0%)
```

**PCASP/Completude**
```
Passaram 11 × w=1  → numerador  = 11,  denominador += 11
Falhou ALERTA 2 × w=1            → denominador += 2
P_PCASP = 11 / (11+2) = 11/13 ≈ 0,846  (84,6%)
```

**Temporal**
```
Passaram 3 × w=1   → numerador  = 3,   denominador += 3
P_Temporal = 3/3 = 1,000  (100%)
```

### Pontuação final

```
Pontuação = 100 × (0,20×1,000 + 0,25×0,727 + 0,30×0,750 + 0,15×0,846 + 0,10×1,000)
          = 100 × (0,200 + 0,182 + 0,225 + 0,127 + 0,100)
          = 100 × 0,834
          = 83,4
```

**Banda: C (Regular)**

---

## 8. Comportamentos Especiais

### 8.1 Regras INFO

Regras com `severidade = INFO` têm `w_r = 0`. Elas **não afetam a nota** mas devem aparecer no relatório Excel de pendências com severidade `INFO` para ciência do analista.

### 8.2 Dimensão Temporal indisponível

Quando o snapshot do mês anterior não está disponível (primeira competência do ano ou arquivo ausente):
- `P_Temporal` não é calculado
- Os 10% de peso da dimensão Temporal são redistribuídos proporcionalmente:

```python
# pesos ajustados quando Temporal indisponível
adjusted = {d: w / 0.90 for d, w in pesos.items() if d != "Temporal"}
```

### 8.3 Score mínimo

O score é **sempre ≥ 0**. Não há penalidade extra além das regras do catálogo.

### 8.4 Regras desabilitadas

Regras desabilitadas em `settings.yaml` são tratadas como "não executadas". Uma regra não executada **não conta no denominador** — equivale a removê-la da dimensão para aquela execução.

Se **todas** as regras de uma dimensão forem desabilitadas, `Σ w_r = 0` para essa dimensão e o comportamento é idêntico ao da seção 5.3: a dimensão é excluída e os pesos das demais são renormalizados. Isso impede que uma dimensão com rollout parcial de regras inflacione artificialmente o score.

---

## 9. Evolução Temporal

Para comparação entre competências, o motor deve armazenar:

```
scoring/<YYYY-MM>/<siconfi>.json
{
  "competencia": "2025-01",
  "siconfi": "250400",
  "pontuacao": 88.2,
  "banda": "B",
  "por_dimensao": {
    "Estrutura": 1.0,
    "Fechamento": 0.813,
    "IC_Dominio": 0.829,
    "PCASP_Completude": 0.867,
    "Temporal": 1.0
  },
  "regras_executadas": 67,
  "regras_falhas": { "ERRO": 3, "ALERTA": 5 }
}
```

Isso permite:
- Gráfico de evolução da nota mês a mês
- Identificação de regressões entre competências
- Benchmark entre entes do mesmo estado

---

## 10. Limitações e Decisões de Design

| Decisão | Alternativa rejeitada | Motivo |
|---|---|---|
| Binário por regra (passou/falhou) | Contar linhas com issue | Evita distorção por volume (1 ERRO em 500 linhas ≠ 500× pior) |
| INFO não afeta nota | INFO = peso 0,5 | INFO é informativo; não representa violação de conformidade |
| 5 dimensões agregadas | 18 categorias como dimensões | Granularidade excessiva → volatilidade alta entre entes |
| Pesos fixos por dimensão | Pesos configuráveis por ente | Simplidade; ajuste via configuração pode ser adicionado em F4-03+ |
| Bandas A–E ICF Siconfi | Nota 0–10 estilo escolar | Manter coerência com o benchmark nacional do Ranking Siconfi |
| `w_r` dinâmico (severidade observada) | `w_r` estático (metadata da regra) | Várias regras (R024, R026–R029) produzem ERRO ou ALERTA dependendo dos dados; `w_r` fixo forçaria uma escolha arbitrária que superpenaliza ou subpenaliza; `w_r` dinâmico = custo real da falha observada |

---

## 11. Referências

- Leiaute MSC 2026 — STN
- Portaria STN 642 — Regras Gerais MSC (`ref/2026_Anexo_I_Portaria_STN_642_Regras_Gerais_MSC.pdf`)
- MCASP — Manual de Contabilidade Aplicada ao Setor Público
- `backlog_regras_msc_completo.xlsx` — aba "Resumo por Categoria"
- `ref/regras_catalogo.md`
