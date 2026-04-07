"""
ranking_msc.schemas
~~~~~~~~~~~~~~~~~~~

Constantes com as colunas esperadas dos DataFrames principais.

Cada schema define o *contrato* de dados entre os módulos.
- Fact_MSC: dados brutos lidos do CSV MSC (após normalização mínima).
- Fact_Resultado_Regras: saída de cada regra (pendências encontradas).
- Fact_Execucao: log de cada execução do motor (auditoria).

Convenções de nomes (conceitos de negócio em português):
    Competencia  — mês/ano de referência (YYYY-MM)
    Severidade   — grau do problema (ERRO, ALERTA, INFO)
    Dimensao     — classificação da regra (PCASP, Temporal, Fechamento…)
    Siconfi      — código do sistema SICONFI do ente

Uso típico:
    from ranking_msc.schemas import FACT_MSC_COLUMNS
    assert set(FACT_MSC_COLUMNS).issubset(df.columns)
"""

from typing import Final

# ---------------------------------------------------------------------------
# Raw_MSC — DataFrame bruto saído de read_msc_csv() (antes de normalize_ic)
# ---------------------------------------------------------------------------
# Contém as colunas IC1-IC6/TIPO1-TIPO6 originais do CSV, valores já pivotados
# por Tipo_valor × Natureza_valor, mais metadados (competencia, siconfi).
RAW_MSC_COLUMNS: Final[list[str]] = [
    "competencia",              # YYYY-MM (extraído da linha 1 do CSV)
    "siconfi",                  # código SICONFI do ente (extraído da linha 1)
    "conta_contabil",           # conta PCASP, 9 dígitos sem pontos (ex: "111110200")
    "ic1",                      # informação complementar 1 — código
    "tipo1",                    # tipo da IC1 (ex: "PO")
    "ic2",                      # informação complementar 2
    "tipo2",                    # tipo da IC2 (ex: "FP", "FS")
    "ic3",                      # informação complementar 3
    "tipo3",                    # tipo da IC3 (ex: "FR")
    "ic4",                      # informação complementar 4
    "tipo4",                    # tipo da IC4 (ex: "CO", "NR")
    "ic5",                      # informação complementar 5
    "tipo5",                    # tipo da IC5 (ex: "ND")
    "ic6",                      # informação complementar 6
    "tipo6",                    # tipo da IC6 (ex: "AI")
    "saldo_inicial_debito",     # beginning_balance;D
    "saldo_inicial_credito",    # beginning_balance;C
    "movimento_debito",         # period_change;D
    "movimento_credito",        # period_change;C
    "saldo_final_debito",       # ending_balance;D
    "saldo_final_credito",      # ending_balance;C
    "_has_saldo_inicial",       # True se existe ≥1 linha beginning_balance no CSV original
    "_has_saldo_final",         # True se existe ≥1 linha ending_balance no CSV original
]

# ---------------------------------------------------------------------------
# Fact_MSC — DataFrame normalizado (após normalize_ic), entrada do motor
# ---------------------------------------------------------------------------
# Contém as colunas IC já mapeadas por TIPO (po, fr, co, etc.) e valores
# pivotados. É o contrato de dados que as regras esperam.
FACT_MSC_COLUMNS: Final[list[str]] = [
    "competencia",              # YYYY-MM
    "siconfi",                  # código SICONFI do ente
    "conta_contabil",           # conta PCASP, 9 dígitos sem pontos
    "po",                       # poder/órgão (IC onde TIPO=PO)
    "fp",                       # Atributo Superávit Financeiro (F=1, P=2) — IC onde TIPO=FP
    "dc",                       # Dívida Consolidada (1=não compõe DC) — IC onde TIPO=DC
    "fs",                       # Classificação Funcional / Função e Subfunção — IC onde TIPO=FS
    "fr",                       # fonte de recurso (IC onde TIPO=FR)
    "co",                       # complemento da fonte (IC onde TIPO=CO)
    "nr",                       # natureza da receita (IC onde TIPO=NR)
    "nd",                       # natureza da despesa (IC onde TIPO=ND)
    "ai",                       # ano de inscrição RP (IC onde TIPO=AI)
    "saldo_inicial_debito",     # beginning_balance;D
    "saldo_inicial_credito",    # beginning_balance;C
    "movimento_debito",         # period_change;D
    "movimento_credito",        # period_change;C
    "saldo_final_debito",       # ending_balance;D
    "saldo_final_credito",      # ending_balance;C
    "_has_saldo_inicial",       # True se existe ≥1 linha beginning_balance no CSV original
    "_has_saldo_final",         # True se existe ≥1 linha ending_balance no CSV original
]

# ---------------------------------------------------------------------------
# Fact_Resultado_Regras — saída padronizada de cada regra
# ---------------------------------------------------------------------------
# Toda regra DEVE devolver um DataFrame com *no mínimo* estas colunas.
# Regras podem adicionar colunas extras de evidência, mas nunca omitir estas.
FACT_RESULTADO_REGRAS_COLUMNS: Final[list[str]] = [
    "regra_id",         # ex: "R082", "R111"
    "regra_nome",       # nome curto legível
    "dimensao",         # "PCASP", "Fechamento", "Temporal", "Domínio"…
    "severidade",       # "ERRO", "ALERTA", "INFO"
    "conta_contabil",   # conta afetada (pode ser vazia se a regra é global)
    "descricao",        # mensagem explicando a pendência
    "valor_esperado",   # o que a regra esperava
    "valor_encontrado", # o que de fato encontrou
    "competencia",      # competência avaliada
]

# ---------------------------------------------------------------------------
# Fact_Execucao — registro de auditoria por execução do motor
# ---------------------------------------------------------------------------
FACT_EXECUCAO_COLUMNS: Final[list[str]] = [
    "execucao_id",      # UUID da execução
    "usuario",          # quem disparou (multiusuário)
    "competencia",      # competência processada
    "siconfi",          # ente processado
    "inicio",           # datetime ISO de início
    "fim",              # datetime ISO de fim
    "status",           # "OK", "ERRO", "PARCIAL"
    "total_regras",     # quantas regras rodaram
    "total_pendencias", # quantas pendências encontradas
    "erro_msg",         # mensagem se status != "OK"
]
