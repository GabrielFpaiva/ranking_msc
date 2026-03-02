"""
ranking_msc.transform.ic_normalize
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normalização do Indicador Contábil (IC) e Tipo de Valor da MSC.

O CSV MSC original contém colunas IC e TIPO que codificam informações
sobre como interpretar cada linha (Patrimonial, Orçamentário, Controle, etc.).
A normalização separa essas informações em colunas individuais:

    IC/TIPO originais  →  PO, FR, CO, NR, ND, FS

Onde:
    PO = Poder/Órgão
    FR = Fonte de Recurso
    CO = Complemento do Órgão
    NR = Natureza da Receita
    ND = Natureza da Despesa
    FS = Função/Subfunção

Este módulo é chamado logo após ``read_msc_csv()`` e antes do motor
de regras, garantindo que o DataFrame esteja no formato padronizado.
"""

from __future__ import annotations

import pandas as pd


def normalize_ic(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza colunas IC/TIPO em colunas individuais (PO, FR, CO, NR, ND, FS).

    Args:
        df: DataFrame bruto da MSC (saída de ``read_msc_csv``).

    Returns:
        DataFrame com colunas IC expandidas. As colunas originais IC/TIPO
        são mantidas para auditoria e as novas colunas são adicionadas.

    Raises:
        NotImplementedError: stub — lógica ainda não implementada.

    TODO (implementar):
        - Mapear cada combinação IC × TIPO para as colunas de informação.
        - Preencher PO, FR, CO, NR, ND, FS com os valores extraídos.
        - Tratar valores nulos/zerados (informação complementar vazia = "000…").
        - Manter colunas originais IC e TIPO para rastreabilidade.
        - Validar que todas as combinações IC×TIPO são conhecidas; logar
          combinações inesperadas como WARNING.
    """
    # --- STUB ---
    raise NotImplementedError(
        "normalize_ic() ainda não implementado. "
        "Consulte os comentários para o fluxo esperado."
    )
