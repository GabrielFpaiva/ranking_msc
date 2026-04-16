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
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ranking_msc.engine.score_engine import ScoreResult
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

_SALDO_DEVEDOR_FILL = PatternFill(fill_type="solid", fgColor="FFFFC7CE")
_SALDO_DEVEDOR_COLUMNS: dict[str, str] = {
    "conta_contabil": "Conta Contábil",
    "valor_esperado": "Natureza Esperada",
    "valor_encontrado": "Saldo Encontrado",
    "descricao": "Descrição",
}

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

# Cores para aba Score — por banda A-E
_BAND_FILLS: dict[str, PatternFill] = {
    "A": PatternFill(fill_type="solid", fgColor="FF70AD47"),  # verde
    "B": PatternFill(fill_type="solid", fgColor="FFC6EFCE"),  # verde claro
    "C": PatternFill(fill_type="solid", fgColor="FFFFEB9C"),  # amarelo
    "D": PatternFill(fill_type="solid", fgColor="FFFFCC00"),  # laranja
    "E": PatternFill(fill_type="solid", fgColor="FFFFC7CE"),  # vermelho
}

# Thresholds de banda para tabela de benchmarks — doc/modelo_pontuacao.md §6
_BAND_THRESHOLDS: list[tuple[str, str]] = [
    ("A", "≥ 95"),
    ("B", "≥ 85"),
    ("C", "≥ 75"),
    ("D", "≥ 65"),
    ("E", "< 65"),
]

# Thresholds numéricos para colorir linhas de dimensão na aba Score
# Espelha _BANDS de score_engine.py para consistência visual com a legenda
_DIM_FILL_THRESHOLDS: list[tuple[float, str]] = [
    (95.0, "A"),
    (85.0, "B"),
    (75.0, "C"),
    (65.0, "D"),
    (0.0, "E"),
]


def export_issues_excel(
    df_pendencias: pd.DataFrame,
    competencia: str,
    *,
    output_dir: str | Path = "data/reports",
    filename: str | None = None,
    score_result: ScoreResult | None = None,
) -> Path:
    """Exporta pendências para arquivo Excel formatado.

    Args:
        df_pendencias: DataFrame com colunas de FACT_RESULTADO_REGRAS_COLUMNS.
        competencia: competência no formato "YYYY-MM".
        output_dir: diretório de saída do relatório.
        filename: nome do arquivo. Se ``None``, usa
            ``pendencias_<competencia>.xlsx``.
        score_result: resultado de ``calculate_score()``. Se fornecido,
            adiciona aba "Score" com nota geral, breakdown por dimensão
            e tabela de benchmarks.

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

            _add_saldo_devedor_sheet(writer, df_pendencias)
            if score_result is not None:
                _add_score_sheet(writer, score_result)
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
    for col_idx in range(1, ws.max_column + 1):
        max_len = max(
            (
                len(str(ws.cell(row=row_idx, column=col_idx).value))
                for row_idx in range(1, ws.max_row + 1)
                if ws.cell(row=row_idx, column=col_idx).value is not None
            ),
            default=_MIN_COLUMN_WIDTH,
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
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


def _dim_band_fill(nota: float) -> PatternFill:
    """Retorna fill correspondente à banda A-E de uma nota de dimensão (0-100)."""
    for threshold, band in _DIM_FILL_THRESHOLDS:
        if nota >= threshold:
            return _BAND_FILLS[band]
    return _BAND_FILLS["E"]


def _add_score_sheet(
    writer: pd.ExcelWriter,
    score_result: ScoreResult,
) -> None:
    """Adiciona aba 'Score' com nota geral, breakdown por dimensão e benchmarks.

    Layout:
        Seção 1 (linha 1-2): cabeçalho + linha com nota final, banda e totais.
        Seção 2 (a partir da linha 5): tabela de desempenho por dimensão.
        Seção 3 (após dimensões + 2 linhas): tabela de benchmarks A-E.

    Args:
        writer: ExcelWriter aberto (contexto ``with pd.ExcelWriter``).
        score_result: resultado de ``calculate_score()``.
    """
    sheet_name = "Score"

    # -- Seção 1: Nota Geral --------------------------------------------------
    summary_headers = ["Nota Final", "Banda", "Regras Executadas", "Com Erro", "Com Alerta"]
    summary_values = [
        round(score_result.pontuacao, 2),
        score_result.banda,
        score_result.regras_executadas,
        score_result.regras_falhas_erro,
        score_result.regras_falhas_alerta,
    ]

    # -- Seção 2: Desempenho por Dimensão -------------------------------------
    dim_headers = ["Dimensão", "Nota (%)", "Peso (%)", "Regras", "Passou", "Alerta", "Erro"]
    dim_rows: list[list[object]] = []
    for dim_score in score_result.dimensions.values():
        dim_rows.append([
            dim_score.dimension,
            round(dim_score.score * 100, 2),
            round(dim_score.weight_normalized * 100, 2),
            dim_score.rules_total,
            dim_score.rules_passed,
            dim_score.rules_failed_alerta,
            dim_score.rules_failed_erro,
        ])

    # -- Seção 3: Benchmarks --------------------------------------------------
    bench_headers = ["Banda", "Faixa"]

    # Montar um DataFrame com tudo para usar to_excel (sem índice)
    # Usamos startrow para espaçar as seções manualmente
    wb = writer.book
    ws = wb.create_sheet(sheet_name)

    # Seção 1 — cabeçalho na linha 1, valores na linha 2
    for col_idx, header in enumerate(summary_headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL

    for col_idx, value in enumerate(summary_values, start=1):
        ws.cell(row=2, column=col_idx, value=value)

    # Colorir nota e banda conforme a banda obtida
    banda_fill = _BAND_FILLS.get(score_result.banda, _BAND_FILLS["E"])
    for col_idx in range(1, len(summary_headers) + 1):
        ws.cell(row=2, column=col_idx).fill = banda_fill

    # Seção 2 — começa na linha 5 (linha 3 vazia, linha 4 = cabeçalho)
    section2_start = 4
    for col_idx, header in enumerate(dim_headers, start=1):
        cell = ws.cell(row=section2_start, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL

    for row_offset, row_data in enumerate(dim_rows, start=1):
        row_idx = section2_start + row_offset
        for col_idx, value in enumerate(row_data, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)
        # Colorir linha conforme nota da dimensão (coluna 2 = nota %)
        dim_fill = _dim_band_fill(float(row_data[1]))  # type: ignore[arg-type]
        for col_idx in range(1, len(dim_headers) + 1):
            ws.cell(row=row_idx, column=col_idx).fill = dim_fill

    # Seção 3 — benchmarks, após dimensões + 2 linhas de espaço
    bench_start = section2_start + len(dim_rows) + 3
    for col_idx, header in enumerate(bench_headers, start=1):
        cell = ws.cell(row=bench_start, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL

    for row_offset, (banda, faixa) in enumerate(_BAND_THRESHOLDS, start=1):
        row_idx = bench_start + row_offset
        ws.cell(row=row_idx, column=1, value=banda)
        ws.cell(row=row_idx, column=2, value=faixa)
        bench_fill = _BAND_FILLS[banda]
        ws.cell(row=row_idx, column=1).fill = bench_fill
        ws.cell(row=row_idx, column=2).fill = bench_fill

    _auto_fit_columns(ws)


def _add_saldo_devedor_sheet(
    writer: pd.ExcelWriter,
    df_pendencias: pd.DataFrame,
) -> None:
    """Adiciona aba 'Saldo Devedor' com contas de natureza incompatível (R032).

    Filtra pendências da regra R032 e exibe numa aba dedicada com linhas
    destacadas em vermelho — entrega tangível acordada para a Fase 3.

    Args:
        writer: ExcelWriter aberto (contexto ``with pd.ExcelWriter``).
        df_pendencias: DataFrame consolidado de todas as pendências do engine.
    """
    r032 = (
        df_pendencias[df_pendencias["regra_id"] == "R032"]
        if not df_pendencias.empty
        else df_pendencias
    )

    sheet_name = "Saldo Devedor"

    if r032.empty:
        msg_df = pd.DataFrame(
            [{"Conta Contábil": "Sem incompatibilidades de natureza de saldo"}]
        )
        msg_df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        _format_header(ws)
        _auto_fit_columns(ws)
        return

    cols = list(_SALDO_DEVEDOR_COLUMNS.keys())
    view = r032[cols].copy()
    view.to_excel(writer, sheet_name=sheet_name, index=False)

    ws = writer.sheets[sheet_name]

    # Renomear cabeçalhos para rótulos legíveis
    for cell in ws[1]:
        if isinstance(cell.value, str):
            cell.value = _SALDO_DEVEDOR_COLUMNS.get(cell.value, cell.value)

    _format_header(ws)
    _freeze_and_filter(ws)
    _auto_fit_columns(ws)

    # Destacar todas as linhas de dados em vermelho
    for row_idx in range(2, ws.max_row + 1):
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).fill = _SALDO_DEVEDOR_FILL
