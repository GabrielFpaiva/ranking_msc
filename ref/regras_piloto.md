# Regras piloto (F2-10)

## Escopo e padrao de documentacao

Este arquivo e a fonte de verdade das 5 regras piloto da Fase 2.

- Local oficial: `ref/regras_piloto.md`
- Status atual: `PSEUDO_V0` (catalogo oficial R082-R111 ainda nao implementado no codigo)
- Objetivo: documentar logica verificavel agora e substituir depois sem trocar IDs
- Contrato de saida futuro: `FACT_RESULTADO_REGRAS_COLUMNS`

Alinhamento com backlog futuro:

- F2-12: `R082` (Fechamento)
- F2-13: `R089` (PCASP)
- F2-14: `R093` (Dominio)
- F2-15: `R085` (Orcamentaria) e `R102` (Temporal)

Amostras usadas para referencia:

- `ref/amostras/msc_2025-11.csv`
- `ref/amostras/msc_2025-12.csv`

---

## R082 - Fechamento contabil por chave

- **ID:** `R082`
- **Nome:** Fechamento contabil por chave
- **Dimensao:** `Fechamento`
- **Severidade padrao:** `ERRO`
- **Dependencias:** nenhuma dependencia externa
- **Status:** `PSEUDO_V0`

### Colunas de entrada
`conta_contabil`, `po`, `fp`, `fs`, `fr`, `co`, `nr`, `nd`, `ai`,
`saldo_inicial_debito`, `saldo_inicial_credito`, `movimento_debito`,
`movimento_credito`, `saldo_final_debito`, `saldo_final_credito`.

### Condicao logica (pseudocodigo)
```text
para cada linha do FACT_MSC:
    saldo_inicial = saldo_inicial_debito - saldo_inicial_credito
    movimento = movimento_debito - movimento_credito
    saldo_final = saldo_final_debito - saldo_final_credito

    se round(saldo_final - (saldo_inicial + movimento), 2) != 0:
        gerar pendencia ERRO
```

### Criterio de pendencia
Gera pendencia quando a equacao de fechamento contabil nao fecha na chave da linha.

### Caso OK
`100 + 10 = 110` (debito-liquido), sem pendencia.

### Caso com pendencia
`100 + 10 != 105`, gera pendencia ERRO.

### Contrato de saida esperado
`regra_id`, `regra_nome`, `dimensao`, `severidade`, `conta_contabil`,
`descricao`, `valor_esperado`, `valor_encontrado`, `competencia`.

---

## R089 - Conta contabil deve existir no PCASP

- **ID:** `R089`
- **Nome:** Conta contabil valida no PCASP
- **Dimensao:** `PCASP`
- **Severidade padrao:** `ERRO`
- **Dependencias:** `io/ref_loader.py` -> `load_pcasp()` (F2-11)
- **Status:** `PSEUDO_V0`

### Colunas de entrada
`conta_contabil` + tabela de referencia `pcasp`.

### Condicao logica (pseudocodigo)
```text
pcasp_df = load_pcasp()
contas_validas = set(pcasp_df["conta_contabil"])

para cada linha do FACT_MSC:
    se conta_contabil nao estiver em contas_validas:
        gerar pendencia ERRO
```

### Criterio de pendencia
Conta do MSC nao encontrada na base PCASP vigente.

### Caso OK
`conta_contabil=111110200` presente na tabela PCASP.

### Caso com pendencia
`conta_contabil=999999999` ausente na tabela PCASP.

### Contrato de saida esperado
`regra_id`, `regra_nome`, `dimensao`, `severidade`, `conta_contabil`,
`descricao`, `valor_esperado`, `valor_encontrado`, `competencia`.

---

## R093 - Validacao de dominio (FR e ND)

- **ID:** `R093`
- **Nome:** Dominio de FR e ND
- **Dimensao:** `Dominio`
- **Severidade padrao:** `ERRO`
- **Dependencias:** `load_dominios_fr()` (F2-11, quando disponivel)
- **Status:** `PSEUDO_V0`

### Colunas de entrada
`fr`, `nd`, `conta_contabil` + dominio de FR.

### Condicao logica (pseudocodigo)
```text
dominio_fr = load_dominios_fr()  # quando tabela existir

para cada linha do FACT_MSC:
    se fr != "" e fr nao estiver no dominio_fr:
        gerar pendencia ERRO

    se nd != "" e nd nao casar com ^[0-9]{8}$:
        gerar pendencia ERRO
```

### Criterio de pendencia
- Fonte de recurso fora do dominio permitido.
- Natureza da despesa malformada (quando preenchida).

### Caso OK
`fr=1500` dentro do dominio e `nd=33903000` com 8 digitos numericos.

### Caso com pendencia
`fr=ZZZZ` fora do dominio ou `nd=33A0300` invalida.

### Contrato de saida esperado
`regra_id`, `regra_nome`, `dimensao`, `severidade`, `conta_contabil`,
`descricao`, `valor_esperado`, `valor_encontrado`, `competencia`.

---

## R085 - Coerencia orcamentaria (FS exige ND)

- **ID:** `R085`
- **Nome:** Exigir ND quando FS estiver informado
- **Dimensao:** `Orcamentaria`
- **Severidade padrao:** `ERRO`
- **Dependencias:** nenhuma dependencia externa
- **Status:** `PSEUDO_V0`

### Colunas de entrada
`fs`, `nd`, `conta_contabil`.

### Condicao logica (pseudocodigo)
```text
para cada linha do FACT_MSC:
    se fs != "" e nd == "":
        gerar pendencia ERRO
```

### Criterio de pendencia
Linha orcamentaria com fonte/subfonte informada sem natureza da despesa.

### Caso OK
`fs=1001` e `nd=33903000`.

### Caso com pendencia
`fs=1001` e `nd=""`.

### Contrato de saida esperado
`regra_id`, `regra_nome`, `dimensao`, `severidade`, `conta_contabil`,
`descricao`, `valor_esperado`, `valor_encontrado`, `competencia`.

---

## R102 - Continuidade temporal entre competencias

- **ID:** `R102`
- **Nome:** Continuidade de saldos entre meses
- **Dimensao:** `Temporal`
- **Severidade padrao:** `ERRO`
- **Dependencias:** disponibilidade de competencia anterior
- **Status:** `PSEUDO_V0`

### Colunas de entrada
`conta_contabil`, `po`, `fp`, `fs`, `fr`, `co`, `nr`, `nd`, `ai`,
`saldo_final_debito`, `saldo_final_credito` (mes anterior),
`saldo_inicial_debito`, `saldo_inicial_credito` (mes atual).

### Condicao logica (pseudocodigo)
```text
chave = (conta_contabil, po, fp, fs, fr, co, nr, nd, ai)

juntar df_mes_anterior e df_mes_atual por chave

para cada chave em comum:
    se round(saldo_final_debito_anterior, 2) != round(saldo_inicial_debito_atual, 2):
        gerar pendencia ERRO

    se round(saldo_final_credito_anterior, 2) != round(saldo_inicial_credito_atual, 2):
        gerar pendencia ERRO
```

### Criterio de pendencia
Quebra de continuidade entre fechamento do mes anterior e abertura do mes atual.

### Caso OK
Mes anterior fecha com `1500.00` e mes atual abre com `1500.00` para a mesma chave.

### Caso com pendencia
Mes anterior fecha com `1500.00` e mes atual abre com `1490.00` para a mesma chave.

### Contrato de saida esperado
`regra_id`, `regra_nome`, `dimensao`, `severidade`, `conta_contabil`,
`descricao`, `valor_esperado`, `valor_encontrado`, `competencia`.

---

## Nota de substituicao futura

Ao migrar de `PSEUDO_V0` para regra oficial:

1. Manter os IDs (`R082`, `R089`, `R093`, `R085`, `R102`).
2. Ajustar apenas a logica.
3. Preservar o contrato de saida do motor (`FACT_RESULTADO_REGRAS_COLUMNS`).
