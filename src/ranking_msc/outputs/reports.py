"""
ranking_msc.outputs.reports
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Exportação de relatórios Excel com pendências e evidências.

O relatório é o produto final para o analista: uma planilha com abas
detalhando as pendências encontradas, agrupadas por dimensão e severidade.

Formato planejado (uma aba por seção):
    - "Resumo": totalizadores por dimensão/severidade.
    - "Pendências": listagem completa com todas as colunas de evidência.
    - "Por Regra": uma aba por regra (R082, R083…) com detalhamento.

TODO: usar openpyxl ou xlsxwriter para formatação condicional,
      cores por severidade, cabeçalhos fixos, etc.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import ReportError


def export_issues_excel(
    df_pendencias: pd.DataFrame,
    competencia: str,
    *,
    output_dir: str | Path = "data/reports",
    filename: str | None = None,
) -> Path:
    """Exporta pendências para planilha Excel.

    Args:
        df_pendencias: DataFrame com colunas de FACT_RESULTADO_REGRAS_COLUMNS.
        competencia: "YYYY-MM" para identificar o relatório.
        output_dir: diretório de saída.
        filename: nome do arquivo. Se None, gera automaticamente
                  "pendencias_<competencia>.xlsx".

    Returns:
        Path do arquivo Excel gerado.

    Raises:
        ReportError: falha de I/O ou DataFrame vazio inesperado.
        NotImplementedError: stub — lógica ainda não implementada.

    TODO (implementar):
        1. Criar ExcelWriter com openpyxl.
        2. Aba "Resumo": pivot table severidade × dimensao → contagem.
        3. Aba "Pendências": df_pendencias completo.
        4. Para cada regra_id distinta: aba "R<NNN>" com filtro.
        5. Aplicar formatação condicional:
           - ERRO → fundo vermelho claro
           - ALERTA → fundo amarelo
           - INFO → sem cor
        6. Salvar e retornar Path.
    """
    raise NotImplementedError(
        "export_issues_excel() ainda não implementado. "
        "Consulte os comentários para o fluxo de geração do Excel."
    )
