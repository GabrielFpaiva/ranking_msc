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
# Fact_MSC — DataFrame resultante da leitura do CSV MSC
# ---------------------------------------------------------------------------
# TODO: expandir conforme o layout real do CSV MSC for definido.
FACT_MSC_COLUMNS: Final[list[str]] = [
    "competencia",      # YYYY-MM
    "siconfi",          # código SICONFI do ente
    "conta_contabil",   # conta PCASP (ex: "1.1.1.1.1.01.00")
    "tipo_ic",          # indicador contábil original (IC)
    "po",               # poder/órgão
    "fr",               # fonte de recurso
    "co",               # complemento do órgão
    "nr",               # natureza da receita
    "nd",               # natureza da despesa
    "fs",               # função/subfunção
    "saldo_inicial",
    "debito",
    "credito",
    "saldo_final",
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
