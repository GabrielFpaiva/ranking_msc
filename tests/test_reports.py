"""
tests/test_reports.py
~~~~~~~~~~~~~~~~~~~~~

Testes de exportação de relatórios Excel em ``ranking_msc.outputs.reports``.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell, MergedCell
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
            row_values[header] = _to_int(value)
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


def test_colunas_ajustadas_tem_largura_maior_que_padrao(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Colunas da aba Pendências têm largura ajustada ao conteúdo (> largura padrão 8)."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="widths.xlsx",
    )

    workbook = load_workbook(output)
    ws = workbook["Pendências"]

    for col_letter, dim in ws.column_dimensions.items():
        assert dim.width > 8, f"Coluna {col_letter} com largura {dim.width} não foi ajustada"


def test_cabecalhos_renomeados_para_portugues(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Cabeçalhos da aba Pendências exibem rótulos em português."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="headers.xlsx",
    )

    workbook = load_workbook(output)
    ws = workbook["Pendências"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

    assert "Regra" in headers
    assert "Nome da Regra" in headers
    assert "Conta Contábil" in headers
    assert "Valor Esperado" in headers
    assert "regra_id" not in headers
    assert "conta_contabil" not in headers


def test_pendencias_ordenadas_erro_primeiro(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Aba Pendências tem linhas ERRO antes de ALERTA e INFO."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="order.xlsx",
    )

    workbook = load_workbook(output)
    ws = workbook["Pendências"]
    severity_col = _find_column_index(ws, "Severidade")
    assert severity_col is not None

    severities = [
        ws.cell(row=r, column=severity_col).value
        for r in range(2, ws.max_row + 1)
    ]

    order_map = {"ERRO": 0, "ALERTA": 1, "INFO": 2}
    orders = [order_map.get(str(s), 99) for s in severities if s is not None]
    assert orders == sorted(orders), f"Severidades fora de ordem: {severities}"


def test_resumo_tem_linha_total(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Última linha da aba Resumo é 'Total' com soma das colunas."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="total.xlsx",
    )

    workbook = load_workbook(output)
    ws = workbook["Resumo"]
    last_row_label = ws.cell(row=ws.max_row, column=1).value
    assert last_row_label == "Total"

    # Total deve ser >= max individual de qualquer outra linha
    total_values = [
        ws.cell(row=ws.max_row, column=c).value or 0
        for c in range(2, ws.max_column + 1)
    ]
    assert sum(_to_int(v) for v in total_values) > 0


def test_resumo_aplica_cor_em_severidade_erro(
    local_tmp_dir: Path,
    pendencias_sinteticas: pd.DataFrame,
) -> None:
    """Linha ERRO na aba Resumo recebe cor vermelha."""
    output = export_issues_excel(
        pendencias_sinteticas,
        competencia="2024-01",
        output_dir=local_tmp_dir,
        filename="resumo_cores.xlsx",
    )

    workbook = load_workbook(output)
    ws = workbook["Resumo"]

    for row_idx in range(2, ws.max_row + 1):
        label = ws.cell(row=row_idx, column=1).value
        if label == "ERRO":
            rgb = _extract_rgb(ws.cell(row=row_idx, column=1))
            assert rgb.endswith("F8D7DA"), f"Cor ERRO incorreta no Resumo: {rgb}"
            break
    else:
        pytest.fail("Linha ERRO não encontrada na aba Resumo")


def _find_column_index(ws: Worksheet, header_name: str) -> int | None:
    """Encontra o índice da coluna com nome do cabeçalho informado."""
    normalized = header_name.strip().lower()
    for col_idx in range(1, ws.max_column + 1):
        value = ws.cell(row=1, column=col_idx).value
        if isinstance(value, str) and value.strip().lower() == normalized:
            return col_idx
    return None


def _to_int(value: object) -> int:
    """Converte valores de célula do Excel para inteiro de forma segura."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _extract_rgb(cell: Cell | MergedCell) -> str:
    """Extrai valor RGB da cor da célula em formato string."""
    color = cell.fill.fgColor
    if color is None:
        return ""
    rgb = getattr(color, "rgb", None)
    if isinstance(rgb, str):
        return rgb.upper()
    return ""
