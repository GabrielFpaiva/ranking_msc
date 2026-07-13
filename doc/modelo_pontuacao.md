# Modelo de Pontuação — Ranking MSC

> **Versão:** 1.3
> **Fase:** F4 — Scoring
> **Referência:** Indicador de Conformidade Fiscal (ICF) do Ranking Siconfi / STN

---

## 1. Objetivo

Definir a fórmula, pesos e critérios de classificação para produzir uma **nota de conformidade 0–100** a partir dos resultados de validação da MSC (Matriz de Saldos Contábeis). A nota sintetiza o conjunto das 78 regras do catálogo em um único indicador comparável entre entes e entre competências.

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

> **Quando Temporal indisponível** (snapshot ausente): ver seção 8.2 — a dimensão é excluída
> e os pesos das demais são renormalizados pela fórmula geral de 5.3 (`w_total = sum(active)`).
> Os valores finais dependem de quais outras dimensões estejam ativas no run; não há pesos fixos pré-calculados.

---

## 5. Fórmula de Cálculo

### 5.1 Peso de uma regra

O peso é determinado pela **severidade observada na execução atual** — não por uma propriedade estática da regra. Várias regras do catálogo produzem ERRO *ou* ALERTA dependendo dos dados (ex.: R024, R026, R027, R028, R029), portanto não existe um `w_r` fixo que represente corretamente todos os cenários.

```
w_r(run) = 2   se a regra produziu ≥1 issue com severidade "ERRO"
           1   se a regra produziu ≥1 issue com severidade "ALERTA" (sem ERRO)
           1   se a regra passou sem issues E é pontuável (pode produzir ERRO ou ALERTA)
           0   se a regra é INFO-only (só pode produzir INFO) — mesmo que passe sem issues
           0   se a regra não foi executada
```

> **Regra pontuável** é toda regra que pode produzir issues ERRO ou ALERTA. Regras INFO-only
> têm `w_r = 0` independentemente do resultado da execução — elas não participam de
> nenhum somatório do score (nem numerador nem denominador). A classificação como INFO-only
> deve ser declarada na classe da regra via atributo `is_scoring: ClassVar[bool] = False`.
>
> Consequência: o denominador de P_d reflete o custo real das falhas observadas.
> ERRO-failures pesam 2×, ALERTA-failures pesam 1×, regras pontuáveis que passaram
> contribuem com baseline 1. INFO-only rules são transparentes ao score.

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
| Temporal | 3 (3 ALT-cap; 3 INFO excluídas) | 0 | 0 |

> "ERRO-cap" e "ALT-cap" indicam a severidade que a regra PODE produzir. Regras INFO-only
> (`is_scoring = False`) não entram nas contagens nem no denominador.
> Para o cálculo, o que importa é a severidade **observada** nesta execução.

### Cálculo de P_d

**Regra de cálculo:** passou (pontuável) → `w_r=1`, falhou-ALERTA → `w_r=1`, falhou-ERRO → `w_r=2`, INFO-only → `w_r=0` (excluída do cálculo).

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

Regras INFO-only têm `w_r = 0` **sempre** — inclusive quando passam sem issues. Elas não entram no numerador nem no denominador de nenhuma dimensão. Devem aparecer no relatório Excel de pendências com severidade `INFO` para ciência do analista.

Identificação: a classe da regra declara `is_scoring: ClassVar[bool] = False`. O score engine deve filtrar `[r for r in rules if r.is_scoring]` antes de calcular P_d. Regras sem esse atributo têm `is_scoring = True` por padrão (compatível com o ABC existente).

### 8.2 Dimensão Temporal indisponível

Quando o snapshot do mês anterior não está disponível (primeira competência do ano ou arquivo ausente):
- `P_Temporal` não é calculado — Temporal é tratada como dimensão com `Σ w_r = 0`
- O comportamento é idêntico ao da seção 5.3: usa a fórmula geral de renormalização

```python
# Fórmula geral — cobre Temporal ausente e qualquer outra combinação de dimensões inativas
excluidas = {d for d in dims if sum_w[d] == 0}   # inclui Temporal se snapshot ausente
active = {d: W[d] for d in dims if d not in excluidas}
w_total = sum(active.values())                    # NÃO hardcodar 0.90
W_norm = {d: w / w_total for d, w in active.items()}
```

> O hardcode `/ 0.90` só é correto quando Temporal é a única dimensão excluída.
> Se outra dimensão também tiver `Σ w_r = 0` (ex.: todas as regras de PCASP desabilitadas),
> `w_total` seria menor que 0,90 e os pesos `W_norm` deixariam de somar 1,0.

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
| INFO-only excluídas via `is_scoring = False` | Inferir INFO-only pelo output do run | Regra que passou com zero issues não revela sua natureza INFO; única forma segura é declaração na classe — evita diluição artificial do score por regras INFO em execuções limpas |
| Renormalização dinâmica (`w_total = sum(active)`) | Divisor fixo `0.90` para Temporal ausente | `0.90` só é correto quando Temporal é a única dimensão excluída; se outra dimensão também tiver `Σ w_r = 0`, os pesos normalizados deixam de somar 1,0 e o score fica subescalado |

---

## 11. Referências

- Leiaute MSC 2026 — STN
- Portaria STN 642 — Regras Gerais MSC (`ref/2026_Anexo_I_Portaria_STN_642_Regras_Gerais_MSC.pdf`)
- MCASP — Manual de Contabilidade Aplicada ao Setor Público
- `backlog_regras_msc_completo.xlsx` — aba "Resumo por Categoria"
- `ref/regras_catalogo.md`
