"""
ranking_msc.outputs.reports
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Exportação de relatórios Excel com pendências e evidências.

Formato gerado:
    - "Resumo": totalizadores por severidade x dimensão, com linha Total e cores.
    - "Pendências": listagem completa das pendências, ordenada e com cabeçalhos PT.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from ranking_msc.exceptions import ReportError
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

logger = logging.getLogger("ranking_msc")

_SEVERITY_ORDER = ["ERRO", "ALERTA", "INFO"]
_SEVERITY_COLORS: dict[str, str] = {
    "ERRO": "FFF8D7DA",
    "ALERTA": "FFFFF3CD",
    "INFO": "FFE2E3E5",
}

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="FFDDEBF7")
_HEADER_FONT = Font(bold=True)

_COLUMN_LABELS: dict[str, str] = {
    "regra_id": "Regra",
    "regra_nome": "Nome da Regra",
    "dimensao": "Dimensão",
    "severidade": "Severidade",
    "conta_contabil": "Conta Contábil",
    "descricao": "Descrição",
    "valor_esperado": "Valor Esperado",
    "valor_encontrado": "Valor Encontrado",
    "competencia": "Competência",
}

_MAX_COLUMN_WIDTH = 60
_MIN_COLUMN_WIDTH = 10


def export_issues_excel(
    df_pendencias: pd.DataFrame,
    competencia: str,
    *,
    output_dir: str | Path = "data/reports",
    filename: str | None = None,
) -> Path:
    """Exporta pendências para arquivo Excel formatado.

    Args:
        df_pendencias: DataFrame com colunas de FACT_RESULTADO_REGRAS_COLUMNS.
        competencia: competência no formato "YYYY-MM".
        output_dir: diretório de saída do relatório.
        filename: nome do arquivo. Se ``None``, usa
            ``pendencias_<competencia>.xlsx``.

    Returns:
        Path absoluto para o arquivo Excel gerado.

    Raises:
        ReportError: se o DataFrame for inválido ou ocorrer falha na escrita.
    """
    _validate_issues_dataframe(df_pendencias)

    output_path = _build_output_path(
        competencia=competencia,
        output_dir=output_dir,
        filename=filename,
    )
    resumo_df = _build_summary_dataframe(df_pendencias)
    pendencias_sorted = _sort_pendencias(df_pendencias)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            resumo_df.to_excel(writer, sheet_name="Resumo", index_label="severidade")
            pendencias_sorted.to_excel(writer, sheet_name="Pendências", index=False)

            ws_resumo = writer.sheets["Resumo"]
            ws_pendencias = writer.sheets["Pendências"]

            _format_header(ws_resumo)
            _format_header(ws_pendencias)
            _freeze_and_filter(ws_resumo)
            _freeze_and_filter(ws_pendencias)
            _apply_severity_colors(ws_pendencias)
            _apply_severity_colors_resumo(ws_resumo)
            _auto_fit_columns(ws_resumo)
            _auto_fit_columns(ws_pendencias)
            _rename_headers(ws_pendencias)
    except Exception as exc:  # noqa: BLE001
        raise ReportError(
            f"Falha ao exportar relatório Excel para competência {competencia}: {exc}"
        ) from exc

    logger.info(
        "Relatório Excel exportado: competência=%s path=%s (%d pendências)",
        competencia, output_path.resolve(), len(df_pendencias),
        extra={"competencia": competencia, "modulo": "reports"},
    )
    return output_path.resolve()


def _validate_issues_dataframe(df_pendencias: pd.DataFrame) -> None:
    """Valida se o DataFrame possui as colunas obrigatórias de pendências."""
    missing_columns = sorted(set(FACT_RESULTADO_REGRAS_COLUMNS) - set(df_pendencias.columns))
    if missing_columns:
        raise ReportError(
            "DataFrame de pendências sem colunas obrigatórias para exportação: "
            f"{missing_columns}"
        )


def _build_output_path(
    *,
    competencia: str,
    output_dir: str | Path,
    filename: str | None,
) -> Path:
    """Monta o caminho de saída do arquivo Excel."""
    final_name = filename or f"pendencias_{competencia}.xlsx"
    return Path(output_dir) / final_name


def _build_summary_dataframe(df_pendencias: pd.DataFrame) -> pd.DataFrame:
    """Monta tabela de resumo com contagem por severidade x dimensão e linha Total."""
    summary_base = df_pendencias.copy()
    summary_base["severidade"] = summary_base["severidade"].fillna("SEM_SEVERIDADE").astype(str)
    summary_base["dimensao"] = summary_base["dimensao"].fillna("SEM_DIMENSAO").astype(str)

    summary = (
        summary_base.groupby(["severidade", "dimensao"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    summary.columns = summary.columns.astype(str)
    summary = summary.reindex(columns=sorted(summary.columns))

    ordered_index = [severity for severity in _SEVERITY_ORDER if severity in summary.index]
    remaining = sorted(severity for severity in summary.index if severity not in ordered_index)
    summary = summary.reindex(ordered_index + remaining)

    summary.loc["Total"] = summary.sum()
    return summary


def _sort_pendencias(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena pendências: ERRO primeiro, depois ALERTA, INFO; depois regra_id e conta."""
    order = {s: i for i, s in enumerate(_SEVERITY_ORDER)}
    df = df.copy()
    df["_sev_order"] = df["severidade"].map(order).fillna(len(_SEVERITY_ORDER))
    df = df.sort_values(["_sev_order", "regra_id", "conta_contabil"]).drop(
        columns=["_sev_order"]
    )
    return df.reset_index(drop=True)


def _format_header(ws: Worksheet) -> None:
    """Aplica estilo de cabeçalho na primeira linha da planilha."""
    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL


def _freeze_and_filter(ws: Worksheet) -> None:
    """Congela cabeçalho e ativa auto-filtro na planilha."""
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _auto_fit_columns(ws: Worksheet) -> None:
    """Ajusta largura de cada coluna ao conteúdo mais longo."""
    for col in ws.columns:
        max_len = max(
            (len(str(cell.value)) for cell in col if cell.value is not None),
            default=_MIN_COLUMN_WIDTH,
        )
        first_cell = col[0]
        if not hasattr(first_cell, "column_letter"):
            continue
        ws.column_dimensions[first_cell.column_letter].width = min(
            max_len + 4, _MAX_COLUMN_WIDTH
        )


def _rename_headers(ws: Worksheet) -> None:
    """Substitui cabeçalhos técnicos pelos rótulos em português na aba Pendências."""
    for cell in ws[1]:
        if isinstance(cell.value, str):
            cell.value = _COLUMN_LABELS.get(cell.value, cell.value)


def _apply_severity_colors(ws: Worksheet) -> None:
    """Aplica cores por severidade na aba de pendências."""
    severity_column = _find_column_index(ws, "severidade")
    if severity_column is None:
        raise ReportError("Coluna 'severidade' não encontrada na aba 'Pendências'.")

    for row_idx in range(2, ws.max_row + 1):
        severity_value = ws.cell(row=row_idx, column=severity_column).value
        if severity_value is None:
            continue

        fill_color = _SEVERITY_COLORS.get(str(severity_value).upper())
        if fill_color is None:
            continue

        fill = PatternFill(fill_type="solid", fgColor=fill_color)
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).fill = fill


def _apply_severity_colors_resumo(ws: Worksheet) -> None:
    """Aplica cores por severidade na aba Resumo (coluna 1 = severidade)."""
    for row_idx in range(2, ws.max_row + 1):
        severity_value = ws.cell(row=row_idx, column=1).value
        if not isinstance(severity_value, str):
            continue

        fill_color = _SEVERITY_COLORS.get(severity_value.upper())
        if fill_color is None:
            continue

        fill = PatternFill(fill_type="solid", fgColor=fill_color)
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).fill = fill


def _find_column_index(ws: Worksheet, header_name: str) -> int | None:
    """Encontra o índice da coluna pelo valor do cabeçalho na linha 1."""
    normalized_header = header_name.strip().lower()
    for col_idx in range(1, ws.max_column + 1):
        value = ws.cell(row=1, column=col_idx).value
        if isinstance(value, str) and value.strip().lower() == normalized_header:
            return col_idx
    return None
