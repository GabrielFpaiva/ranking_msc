"""
tests/test_reports.py
~~~~~~~~~~~~~~~~~~~~~

Testes de exportação de relatórios Excel em ``ranking_msc.outputs.reports``.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook
from openpyxl.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet

from ranking_msc.exceptions import ReportError
from ranking_msc.outputs.reports import export_issues_excel


@pytest.fixture
def pendencias_sinteticas() -> pd.DataFrame:
    """Cria DataFrame sintético de pendências para teste de exportação."""
    return pd.DataFrame(
        [
            {
                "regra_id": "R082",
                "regra_nome": "Regra Fechamento",
                "dimensao": "Fechamento",
                "severidade": "ERRO",
                "conta_contabil": "111110200",
                "descricao": "Débito diferente do crédito",
                "valor_esperado": "0",
                "valor_encontrado": "10",
                "competencia": "2024-01",
            },
            {
                "regra_id": "R083",
                "regra_nome": "Regra Fechamento 2",
                "dimensao": "Fechamento",
                "severidade": "ALERTA",
                "conta_contabil": "111110300",
                "descricao": "Variação acima do limite",
                "valor_esperado": "100",
                "valor_encontrado": "130",
                "competencia": "2024-01",
            },
            {
                "regra_id": "R084",
                "regra_nome": "Regra Temporal",
                "dimensao": "Temporal",
                "severidade": "INFO",
                "conta_contabil": "211110000",
                "descricao": "Conta sem movimento no mês",
                "valor_esperado": "com movimento",
                "valor_encontrado": "sem movimento",
                "competencia": "2024-01",
            },
            {
                "regra_id": "R085",
                "regra_nome": "Regra Temporal 2",
                "dimensao": "Temporal",
                "severidade": "ERRO",
                "conta_contabil": "311110000",
                "descricao": "Saldo final inconsistente",
                "valor_esperado": "200",
                "valor_encontrado": "150",
                "competencia": "2024-01",
            },
        ],
    )


@pytest.fixture
def local_tmp_dir() -> Iterator[Path]:
    """Cria diretório temporário local para evitar uso de %TEMP% do sistema."""
    created = Path.cwd() / ".reports_test_tmp" / uuid.uuid4().hex
    created.mkdir(parents=True, exist_ok=True)
    try:
        yield created
    finally:
        shutil.rmtree(created, ignore_errors=True)


def test_export_issues_excel_gera_arquivo_com_duas_abas(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Gera Excel com abas Resumo e Pendências, abrindo sem erro."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
    )

    assert output.exists()
    assert output.suffix == ".xlsx"

    workbook = load_workbook(output)
    assert workbook.sheetnames == ["Resumo", "Pendências"]

    ws_resumo = workbook["Resumo"]
    ws_pendencias = workbook["Pendências"]

    assert ws_resumo.freeze_panes == "A2"
    assert ws_pendencias.freeze_panes == "A2"
    assert ws_resumo.auto_filter.ref is not None
    assert ws_pendencias.auto_filter.ref is not None
    assert ws_pendencias.max_row == len(pendencias_sinteticas) + 1


def test_export_issues_excel_resumo_tem_contagens_corretas(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Confere contagem por severidade x dimensão na aba Resumo."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="resumo.xlsx",
    )

    workbook = load_workbook(output)
    ws_resumo = workbook["Resumo"]

    headers = [
        ws_resumo.cell(row=1, column=col_idx).value
        for col_idx in range(2, ws_resumo.max_column + 1)
    ]
    summary_map: dict[str, dict[str, int]] = {}

    for row_idx in range(2, ws_resumo.max_row + 1):
        severity = ws_resumo.cell(row=row_idx, column=1).value
        if not isinstance(severity, str):
            continue
        row_values: dict[str, int] = {}
        for offset, header in enumerate(headers, start=2):
            if not isinstance(header, str):
                continue
            value = ws_resumo.cell(row=row_idx, column=offset).value or 0
            row_values[header] = int(value)
        summary_map[severity] = row_values

    assert summary_map["ERRO"]["Fechamento"] == 1
    assert summary_map["ERRO"]["Temporal"] == 1
    assert summary_map["ALERTA"]["Fechamento"] == 1
    assert summary_map["ALERTA"]["Temporal"] == 0
    assert summary_map["INFO"]["Fechamento"] == 0
    assert summary_map["INFO"]["Temporal"] == 1


def test_export_issues_excel_aplica_cores_por_severidade(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Aplica cores nas linhas de pendências conforme severidade."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="cores.xlsx",
    )

    workbook = load_workbook(output)
    ws_pendencias = workbook["Pendências"]
    severity_col = _find_column_index(ws_pendencias, "severidade")

    assert severity_col is not None

    expected_colors = {
        "ERRO": "F8D7DA",
        "ALERTA": "FFF3CD",
        "INFO": "E2E3E5",
    }

    for row_idx in range(2, ws_pendencias.max_row + 1):
        severity = ws_pendencias.cell(row=row_idx, column=severity_col).value
        if not isinstance(severity, str):
            continue
        rgb = _extract_rgb(ws_pendencias.cell(row=row_idx, column=1))
        assert rgb.endswith(expected_colors[severity]), (
            f"Cor incorreta para severidade {severity}: {rgb}"
        )


def test_export_issues_excel_dataframe_invalido_levanta_reporterror(
    local_tmp_dir: Path,
) -> None:
    """Levanta ReportError quando faltam colunas obrigatórias no DataFrame."""
    invalido = pd.DataFrame([{"severidade": "ERRO"}])

    with pytest.raises(ReportError, match="colunas obrigatórias"):
        export_issues_excel(invalido, competencia="2024-01", output_dir=local_tmp_dir)


def _find_column_index(ws: Worksheet, header_name: str) -> int | None:
    """Encontra o índice da coluna com nome do cabeçalho informado."""
    normalized = header_name.strip().lower()
    for col_idx in range(1, ws.max_column + 1):
        value = ws.cell(row=1, column=col_idx).value
        if isinstance(value, str) and value.strip().lower() == normalized:
            return col_idx
    return None


def _extract_rgb(cell: Cell) -> str:
    """Extrai valor RGB da cor da célula em formato string."""
    color = cell.fill.fgColor
    if color is None:
        return ""
    rgb = getattr(color, "rgb", None)
    if isinstance(rgb, str):
        return rgb.upper()
    return ""
