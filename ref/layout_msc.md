# Layout do CSV MSC

> Documentação do formato dos arquivos CSV da Matriz de Saldos Contábeis (MSC)
> exportados pelo sistema SICONFI.

---

## Metadados do arquivo

| Propriedade         | Valor                                      |
|---------------------|--------------------------------------------|
| Encoding            | ASCII (compatível UTF-8)                   |
| Separador           | `;` (ponto-e-vírgula)                      |
| Separador decimal   | `.` (ponto)                                |
| Line terminator     | `\r` (CR only — estilo Mac clássico)       |
| Cabeçalho           | 2 linhas (ver abaixo)                      |
| Aspas               | Nenhuma (valores sem quoting)              |

### Estrutura das primeiras linhas

```
Linha 1:  <SICONFI>;<competencia>        → ex: 2507507EX;2025-11
Linha 2:  CONTA;IC1;TIPO1;...;Valor;Tipo_valor;Natureza_valor   (header das colunas)
Linha 3+: dados
```

A **linha 1** é metadata (não é header CSV padrão). O reader deve tratá-la à parte
para extrair o código SICONFI e a competência, e usar a linha 2 como header real.

---

## Amostras disponíveis

| Arquivo              | Competência | Linhas (dados) | SICONFI    |
|----------------------|-------------|----------------|------------|
| `msc_2025-11.csv`   | 2025-11     | ~25.311        | 2507507EX  |
| `msc_2025-12.csv`   | 2025-12     | ~28.891        | 2507507EX  |

---

## Colunas

| #  | Nome             | Tipo     | Obrigatória | Exemplo           | Descrição                                      |
|----|------------------|----------|-------------|-------------------|-------------------------------------------------|
| 1  | CONTA            | str(9)   | Sim         | `111110200`       | Conta contábil PCASP, 9 dígitos sem pontos      |
| 2  | IC1              | str      | Sim         | `10131`           | Informação Complementar 1 — código              |
| 3  | TIPO1            | str(2)   | Sim         | `PO`              | Tipo da IC1 — sempre `PO` (Poder/Órgão)         |
| 4  | IC2              | str      | Não         | `01031`           | Informação Complementar 2 — código              |
| 5  | TIPO2            | str(2)   | Não         | `FP`              | Tipo da IC2 — ex: `FP` (Superávit F/P), `FS` (Funcional) |
| 6  | IC3              | str      | Não         | `1500`            | Informação Complementar 3 — código              |
| 7  | TIPO3            | str(2)   | Não         | `FR`              | Tipo da IC3 — sempre `FR` (Fonte de Recurso)    |
| 8  | IC4              | str      | Não         | `1001`            | Informação Complementar 4 — código              |
| 9  | TIPO4            | str(2)   | Não         | `CO`              | Tipo da IC4 — `CO` (Complemento) ou `NR`        |
| 10 | IC5              | str      | Não         | `33903099`        | Informação Complementar 5 — código              |
| 11 | TIPO5            | str(2)   | Não         | `ND`              | Tipo da IC5 — sempre `ND` (Natureza da Despesa) |
| 12 | IC6              | str      | Não         | `2024`            | Informação Complementar 6 — código              |
| 13 | TIPO6            | str(2)   | Não         | `AI`              | Tipo da IC6 — sempre `AI` (Ano Inscrição)       |
| 14 | Valor            | float    | Sim         | `8508556.46`      | Valor monetário (sempre positivo ou zero)        |
| 15 | Tipo_valor       | str      | Sim         | `beginning_balance` | Tipo do saldo (ver domínio abaixo)            |
| 16 | Natureza_valor   | str(1)   | Sim         | `D`               | Natureza: `D` (Débito) ou `C` (Crédito)         |

> Apenas IC1/TIPO1 são obrigatórios em todas as linhas. IC2-IC6 dependem do tipo
> de conta contábil.

---

## Domínios

### Tipo_valor

| Valor               | Significado              |
|----------------------|--------------------------|
| `beginning_balance`  | Saldo inicial do período |
| `period_change`      | Movimentação do período  |
| `ending_balance`     | Saldo final do período   |

### Natureza_valor

| Valor | Significado |
|-------|-------------|
| `D`   | Débito      |
| `C`   | Crédito     |

### TIPO (mapeamento IC → TIPO)

| TIPO | Significado                | Posição usual |
|------|----------------------------|---------------|
| `PO` | Poder/Órgão                | IC1           |
| `FP` | Atributo Superávit Financeiro (F=1, P=2) | IC2 |
| `DC` | Dívida Consolidada         | IC2 ou IC3    |
| `FS` | Classificação Funcional (Função e Subfunção) | IC2 |
| `FR` | Fonte de Recurso           | IC3           |
| `CO` | Complemento da Fonte       | IC4           |
| `NR` | Natureza da Receita        | IC4           |
| `ND` | Natureza da Despesa        | IC5           |
| `AI` | Ano de Inscrição (RP)      | IC6           |

> Todas as 14 combinações únicas de TIPO1–TIPO6 observadas nos CSVs reais estão
> documentadas em [`ref/mapeamento_ic_tipo.csv`](mapeamento_ic_tipo.csv), incluindo
> quais colunas complementares (po, fp, fs, fr, co, nr, nd, ai) se aplicam a cada uma.

---

## Padrões observados nos dados

### Preenchimento das ICs (amostra nov/2025, ~25.311 linhas)

| Coluna | Linhas preenchidas | Observação                            |
|--------|--------------------|---------------------------------------|
| IC1    | Todas              | Sempre presente (PO)                  |
| IC2    | ~24.175 (96%)      | FP ou FS — ausente em algumas contas  |
| IC3    | ~21.104 (83%)      | FR — ausente em algumas contas        |
| IC4    | ~3.628 (14%)       | CO ou NR, quando aplicável            |
| IC5    | ~18.375 (73%)      | ND — natureza da despesa              |
| IC6    | ~2.589 (10%)       | AI — apenas para Restos a Pagar       |

### IC1 (Poder/Órgão) — valores únicos: 3

- `10131`, `10132`, `20231`

### CONTA

- 376 contas distintas (amostra nov/2025)
- Formato: 9 dígitos sem pontuação (ex: `111110200`, `531100000`)
- Sem valores negativos no campo Valor
- 30 registros com Valor = 0

### Agrupamento lógico

Cada combinação `CONTA + IC1..IC6` tem até 4 linhas:
- `beginning_balance;D`, `beginning_balance;C`
- `period_change;D`, `period_change;C`
- `ending_balance;D`, `ending_balance;C`

Na prática, a maioria das combinações tem 3-4 linhas (saldo inicial, movimentos D/C,
saldo final), e a regra de fechamento é:

```
saldo_final = saldo_inicial + period_change_D - period_change_C
```

---

## Peculiaridades e cuidados para o reader

1. **Line terminator `\r`**: `pd.read_csv()` com `lineterminator='\r'` direto no
   path pode falhar. Solução recomendada: ler o arquivo em modo binário (`rb`),
   decodificar, substituir `\r` por `\n`, e passar via `io.StringIO`.
2. **Linha 1 é metadata**: pular com `skiprows=1` e extrair SICONFI/competência
   separadamente.
3. **ICs opcionais vazias**: campos IC4-IC6 e TIPO4-TIPO6 podem ser strings vazias.
   Ler como `dtype=str` e tratar vazio como `""` (não NaN).
4. **CONTA sem pontuação**: o CSV traz `111110200`, não `1.1.1.1.1.02.00`. A
   conversão para formato PCASP com pontos deve ser feita no transform se necessário.
5. **Todos os campos devem ser lidos como `str`** exceto `Valor` (float). Códigos
   contábeis e ICs começam com zeros significativos.
6. **Valores sempre positivos**: a direção (débito/crédito) é indicada por
   `Natureza_valor`, não pelo sinal do valor.
