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
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ranking_msc.engine.score_engine import ScoreResult
from ranking_msc.exceptions import ReportError
from ranking_msc.outputs import brand
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

logger = logging.getLogger("ranking_msc")

# Tintas pálidas para fundo de linha por severidade (legíveis com texto escuro);
# as cores saturadas da marca ficam só nos chips/barras, não em linhas inteiras.
_SEVERITY_ORDER = ["ERRO", "ALERTA", "INFO"]
_SEVERITY_COLORS: dict[str, str] = {
    "ERRO": "FFF8D7DA",
    "ALERTA": "FFFFF3CD",
    "INFO": "FFE2E3E5",
}

_HEADER_FILL = brand.HEADER_FILL
_HEADER_FONT = brand.HEADER_FONT

_THIN_SIDE = Side(style="thin", color="FFD9D9D9")
_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)

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

# Ordem canônica das dimensões nas abas; valores desconhecidos vão ao fim, ordenados.
_DIMENSION_ORDER = [
    "Estrutura",
    "Fechamento",
    "PCASP",
    "Completude",
    "IC",
    "Domínio",
    "Orçamentária",
    "Temporal",
]

# Abas fixas — reservadas para não colidir com abas de dimensão.
_RESERVED_SHEET_NAMES = ("Resumo", "Pendências", "Saldo Devedor", "Score")

# Limites do Excel para nomes de aba.
_MAX_SHEET_NAME_LEN = 31
_EXCEL_FORBIDDEN_CHARS = set("[]:*?/\\")

# Cores para aba Score — por banda A-E (paleta MCRA compartilhada)
_BAND_FILLS: dict[str, PatternFill] = {b: brand.fill(brand.band_hex(b)) for b in "ABCDE"}

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
            ws_resumo = writer.sheets["Resumo"]
            _format_header(ws_resumo)
            _freeze_and_filter(ws_resumo)
            _apply_severity_colors_resumo(ws_resumo)
            _auto_fit_columns(ws_resumo)

            _write_pendencias_sheet(writer, pendencias_sorted, "Pendências")
            _add_dimension_sheets(writer, pendencias_sorted)

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

    # Sem pendências: não há colunas de dimensão para somar; devolve resumo vazio
    # (a aba ainda é criada com o cabeçalho, mês limpo não quebra a exportação).
    if summary.empty:
        return summary

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


def _write_pendencias_sheet(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    sheet_name: str,
) -> Worksheet:
    """Escreve uma aba de pendências (listagem + formatação padrão).

    Args:
        writer: ExcelWriter aberto (contexto ``with pd.ExcelWriter``).
        df: DataFrame de pendências já ordenado.
        sheet_name: nome da aba, já saneado para o Excel.

    Returns:
        Worksheet criada e formatada.
    """
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    ws: Worksheet = writer.sheets[sheet_name]
    _format_header(ws)
    _freeze_and_filter(ws)
    _apply_severity_colors(ws)
    _auto_fit_columns(ws)
    _rename_headers(ws)
    _apply_borders(ws)
    return ws


def _add_dimension_sheets(
    writer: pd.ExcelWriter,
    pendencias_sorted: pd.DataFrame,
) -> None:
    """Adiciona uma aba por dimensão presente nas pendências.

    Cria a aba somente para dimensões com ao menos uma pendência, preservando
    a ordem das linhas (ERRO primeiro) já aplicada em ``pendencias_sorted``. As
    dimensões seguem ``_DIMENSION_ORDER``; valores desconhecidos vão ao fim em
    ordem alfabética.

    Args:
        writer: ExcelWriter aberto.
        pendencias_sorted: pendências já ordenadas por severidade.
    """
    if pendencias_sorted.empty:
        return

    df = pendencias_sorted.copy()
    df["dimensao"] = df["dimensao"].fillna("SEM_DIMENSAO").astype(str)

    present = list(dict.fromkeys(df["dimensao"]))
    ordered = [dim for dim in _DIMENSION_ORDER if dim in present]
    remaining = sorted(dim for dim in present if dim not in ordered)

    used_names: set[str] = set(_RESERVED_SHEET_NAMES)
    for dimensao in ordered + remaining:
        sub = df[df["dimensao"] == dimensao]
        if sub.empty:
            continue
        sheet_name = _safe_dimension_sheet_name(dimensao, used_names)
        used_names.add(sheet_name)
        _write_pendencias_sheet(writer, sub.reset_index(drop=True), sheet_name)


def _safe_dimension_sheet_name(dimensao: str, used: set[str]) -> str:
    """Gera um nome de aba válido para o Excel a partir do nome da dimensão.

    Remove caracteres proibidos (``[ ] : * ? / \\``), limita a 31 caracteres e
    desambigua nomes repetidos com sufixo numérico.

    Args:
        dimensao: nome da dimensão.
        used: nomes de aba já utilizados (inclui as abas fixas reservadas).

    Returns:
        Nome de aba único e aceito pelo Excel.
    """
    cleaned = "".join(
        " " if ch in _EXCEL_FORBIDDEN_CHARS else ch for ch in dimensao
    ).strip()
    name = (cleaned or "SEM_DIMENSAO")[:_MAX_SHEET_NAME_LEN]

    base = name
    counter = 2
    while name in used:
        suffix = f" ({counter})"
        name = f"{base[:_MAX_SHEET_NAME_LEN - len(suffix)]}{suffix}"
        counter += 1
    return name


def _format_header(ws: Worksheet) -> None:
    """Aplica estilo de cabeçalho na primeira linha da planilha."""
    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL


def _apply_borders(ws: Worksheet) -> None:
    """Aplica borda fina cinza em toda a faixa preenchida da planilha."""
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.border = _BORDER


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
        raise ReportError("Coluna 'severidade' não encontrada na aba de pendências.")

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
    _apply_borders(ws)


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
        _apply_borders(ws)
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

    _apply_borders(ws)
