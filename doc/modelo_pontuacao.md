# Modelo de Pontuação — Ranking MSC

> **Versão:** 1.0 (draft para revisão)
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

As 18 categorias do catálogo são agrupadas em 5 dimensões:

| Dimensão | Categorias incluídas | Qtd regras | ERRO | ALERTA | INFO |
|---|---|:---:|:---:|:---:|:---:|
| **Estrutura** | Estrutura, Formato, Duplicidade | 14 | 14 | 0 | 0 |
| **Fechamento** | Fechamento, Interconta | 10 | 6 | 4 | 0 |
| **IC/Domínio** | IC, PO, NR, ND, FR, CO, FS, DC | 23 | 13 | 9 | 1 |
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

```
w_r = { 2  se severidade == "ERRO"
      { 1  se severidade == "ALERTA"
      { 0  se severidade == "INFO"
```

### 5.2 Resultado de uma regra

```
ok_r = { 1  se a regra não gerou nenhum issue
       { 0  se a regra gerou ≥ 1 issue
```

### 5.3 Pontuação de uma dimensão

```
P_d = Σ_{r ∈ d} (w_r × ok_r)  /  Σ_{r ∈ d} w_r

onde d = conjunto de regras da dimensão d (excluindo regras INFO, pois w_r = 0)
```

Se `Σ w_r = 0` para a dimensão (ex.: dimensão composta só por regras INFO), `P_d = 1,0` (dimensão não penaliza).

### 5.4 Pontuação final

```
Pontuação = 100 × Σ_d (W_d × P_d)
```

### 5.5 Resumo em notação compacta

```
Pontuação = 100 × Σ_d [ W_d × ( Σ_{r∈d} w_r·ok_r / Σ_{r∈d} w_r ) ]
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

| Dimensão | Regras | Regras ERRO (w=2) | Regras ALERTA (w=1) | ok_r = 1 (passou) | ok_r = 0 (falhou) |
|---|:---:|:---:|:---:|:---:|:---:|
| Estrutura | 14 | 14 | 0 | 14 / 14 ERRO passaram | 0 |
| Fechamento | 10 | 6 | 4 | 5 ERRO + 3 ALERTA | 1 ERRO + 1 ALERTA |
| IC/Domínio | 23 | 13 | 9 | 11 ERRO + 7 ALERTA | 2 ERRO + 2 ALERTA |
| PCASP/Completude | 14 | 2 | 11 | 2 ERRO + 9 ALERTA | 0 + 2 ALERTA |
| Temporal | 6 | 0 | 3 | 3 ALERTA | 0 |

### Cálculo de P_d

**Estrutura**
```
Σ w_r·ok_r = 14×2 = 28
Σ w_r      = 14×2 = 28
P_Estrutura = 28/28 = 1,000  (100%)
```

**Fechamento**
```
Passou: 5 ERRO + 3 ALERTA → 5×2 + 3×1 = 13
Total:  6 ERRO + 4 ALERTA → 6×2 + 4×1 = 16
P_Fechamento = 13/16 = 0,813  (81,3%)
```

**IC/Domínio**
```
Passou: 11 ERRO + 7 ALERTA → 22 + 7 = 29
Total:  13 ERRO + 9 ALERTA → 26 + 9 = 35
P_IC_Domínio = 29/35 = 0,829  (82,9%)
```

**PCASP/Completude**
```
Passou: 2 ERRO + 9 ALERTA → 4 + 9 = 13
Total:  2 ERRO + 11 ALERTA → 4 + 11 = 15
P_PCASP = 13/15 = 0,867  (86,7%)
```

**Temporal**
```
Passou: 3 ALERTA → 3
Total:  3 ALERTA → 3
P_Temporal = 3/3 = 1,000  (100%)
```

### Pontuação final

```
Pontuação = 100 × (0,20×1,000 + 0,25×0,813 + 0,30×0,829 + 0,15×0,867 + 0,10×1,000)
          = 100 × (0,200 + 0,203 + 0,249 + 0,130 + 0,100)
          = 100 × 0,882
          = 88,2
```

**Banda: B (Bom)**

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

---

## 11. Referências

- Leiaute MSC 2026 — STN
- Portaria STN 642 — Regras Gerais MSC (`ref/2026_Anexo_I_Portaria_STN_642_Regras_Gerais_MSC.pdf`)
- MCASP — Manual de Contabilidade Aplicada ao Setor Público
- `backlog_regras_msc_completo.xlsx` — aba "Resumo por Categoria"
- `ref/regras_catalogo.md`
