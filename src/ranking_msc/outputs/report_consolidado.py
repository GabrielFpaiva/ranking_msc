"""
ranking_msc.outputs.report_consolidado
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Exportação de relatório Excel consolidado com evolução temporal de scores
multi-competência.

Formato gerado:
    - "Evolução": tabela competência × métricas (pontuação, banda, pendências,
      breakdown por dimensão) com gráfico de linha de pontuação embedded.

Nota sobre gráficos:
    O gráfico de pontuação usa ``openpyxl.chart.LineChart``, não SparklineGroup.
    O openpyxl 3.x não expõe SparklineGroup na API pública — apenas na leitura
    interna de arquivos existentes. LineChart oferece funcionalidade equivalente
    (linha de evolução temporal com título e eixos) com suporte público garantido.
    Esta é a decisão definitiva: se openpyxl adicioná-lo em versão futura, avaliar
    migração então; até lá, LineChart é correto e suficiente.
"""

from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ranking_msc.engine.compare_periods import PeriodComparison
from ranking_msc.exceptions import ReportError

logger = logging.getLogger("ranking_msc")

# ---------------------------------------------------------------------------
# Constantes visuais
# ---------------------------------------------------------------------------

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="FFDDEBF7")
_HEADER_FONT = Font(bold=True)
_MAX_COLUMN_WIDTH = 25
_MIN_COLUMN_WIDTH = 8

# Fills por banda — espelha reports.py para consistência visual
_BAND_FILLS: dict[str, PatternFill] = {
    "A": PatternFill(fill_type="solid", fgColor="FF70AD47"),  # verde
    "B": PatternFill(fill_type="solid", fgColor="FFC6EFCE"),  # verde claro
    "C": PatternFill(fill_type="solid", fgColor="FFFFEB9C"),  # amarelo
    "D": PatternFill(fill_type="solid", fgColor="FFFFCC00"),  # laranja
    "E": PatternFill(fill_type="solid", fgColor="FFFFC7CE"),  # vermelho
}

# Cabeçalhos fixos da aba Evolução
_FIXED_HEADERS = [
    "Competência",
    "Pontuação",
    "Banda",
    "Total Pendências",
    "Regras c/ ERRO",
    "Regras c/ ALERTA",
    "Delta",
]

# Dimensões de scoring em ordem canônica → rótulo de coluna
_DIMENSION_LABELS: dict[str, str] = {
    "Estrutura": "Estrutura (%)",
    "Fechamento": "Fechamento (%)",
    "IC_Dominio": "IC Domínio (%)",
    "PCASP_Completude": "PCASP Completude (%)",
    "Temporal": "Temporal (%)",
}
_DIMENSION_ORDER = list(_DIMENSION_LABELS.keys())


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------


def export_consolidado_excel(
    comparison: PeriodComparison,
    *,
    output_dir: str | Path = "data/reports",
    filename: str | None = None,
) -> Path:
    """Exporta relatório Excel consolidado com evolução temporal de scores.

    Abas geradas:
    - "Evolução": tabela competência × métricas com gráfico de linha embedded.

    Args:
        comparison: resultado de ``compare_periods()``.
        output_dir: diretório de saída do relatório.
        filename: nome do arquivo. Se ``None``, usa
            ``consolidado_{siconfi}.xlsx``.

    Returns:
        Path absoluto para o arquivo Excel gerado.

    Raises:
        ReportError: em falha de I/O ou escrita.
    """
    final_name = filename or f"consolidado_{comparison.siconfi}.xlsx"
    output_path = Path(output_dir) / final_name

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        _active = wb.active
        if not isinstance(_active, Worksheet):
            raise ReportError("Falha ao criar aba ativa no workbook.")
        ws: Worksheet = _active
        ws.title = "Evolução"

        _write_evolucao_sheet(ws, comparison)

        if len(comparison.periods) >= 2:
            _add_score_chart(ws, comparison)

        wb.save(str(output_path))

    except Exception as exc:  # noqa: BLE001
        raise ReportError(
            f"Falha ao exportar relatório consolidado para siconfi "
            f"{comparison.siconfi}: {exc}"
        ) from exc

    logger.info(
        "Relatório consolidado exportado: siconfi=%s path=%s (%d períodos)",
        comparison.siconfi,
        output_path.resolve(),
        len(comparison.periods),
        extra={"siconfi": comparison.siconfi, "modulo": "report_consolidado"},
    )
    return output_path.resolve()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _build_headers() -> list[str]:
    """Retorna lista completa de cabeçalhos (fixos + dimensões)."""
    return _FIXED_HEADERS + [_DIMENSION_LABELS[d] for d in _DIMENSION_ORDER]


def _write_evolucao_sheet(ws: Worksheet, comparison: PeriodComparison) -> None:
    """Escreve cabeçalho e linhas de dados na aba Evolução.

    Args:
        ws: worksheet ativa (já nomeada "Evolução").
        comparison: comparação calculada por compare_periods().
    """
    headers = _build_headers()

    # Linha 1 — cabeçalhos
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL

    # Linhas de dados
    for row_offset, period in enumerate(comparison.periods, start=1):
        row_idx = row_offset + 1
        delta = comparison.score_delta(row_offset - 1)

        row_values: list[str | float | int] = [
            period.competencia,
            round(period.score_result.pontuacao, 2),
            period.score_result.banda,
            period.total_pendencias,
            period.score_result.regras_falhas_erro,
            period.score_result.regras_falhas_alerta,
            delta if delta is not None else "",
        ]

        for dim in _DIMENSION_ORDER:
            dim_score = period.score_result.dimensions.get(dim)
            dim_val: str | float = (
                round(dim_score.score * 100, 2) if dim_score is not None else ""
            )
            row_values.append(dim_val)

        for col_idx, value in enumerate(row_values, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)

        # Colorir linha conforme banda do período
        band_fill = _BAND_FILLS.get(period.score_result.banda, _BAND_FILLS["E"])
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_idx).fill = band_fill

    # Freeze + auto-filtro
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    _auto_fit_columns(ws)


def _add_score_chart(ws: Worksheet, comparison: PeriodComparison) -> None:
    """Adiciona gráfico de linha de pontuação abaixo dos dados.

    O gráfico usa a coluna "Pontuação" (coluna 2) como série e a coluna
    "Competência" (coluna 1) como eixo X. É ancorado 2 linhas abaixo
    dos dados para não sobrepor a tabela.

    Args:
        ws: worksheet da aba Evolução.
        comparison: comparação com os períodos.
    """
    n_periods = len(comparison.periods)
    if n_periods < 2:
        return

    chart = LineChart()
    chart.title = f"Evolução de Pontuação — {comparison.siconfi}"
    chart.style = 10
    chart.y_axis.title = "Pontuação (0–100)"
    chart.x_axis.title = "Competência"
    chart.width = 18   # cm
    chart.height = 10  # cm

    # Dados: coluna 2 (Pontuação), linha 1 = header, linhas 2..n+1 = dados
    data_ref = Reference(ws, min_col=2, min_row=1, max_row=n_periods + 1)
    chart.add_data(data_ref, titles_from_data=True)

    # Categorias: coluna 1 (Competência), linhas 2..n+1
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=n_periods + 1)
    chart.set_categories(cats_ref)

    # Ancorar 2 linhas abaixo dos dados
    anchor_row = n_periods + 3
    anchor_col = get_column_letter(1)
    ws.add_chart(chart, f"{anchor_col}{anchor_row}")


def _auto_fit_columns(ws: Worksheet) -> None:
    """Ajusta largura das colunas ao conteúdo mais longo."""
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
