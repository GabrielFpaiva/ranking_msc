"""
tests/test_report_consolidado.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do módulo outputs/report_consolidado.py.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest
from openpyxl.chart import LineChart

from ranking_msc.engine.compare_periods import PeriodComparison, PeriodScore
from ranking_msc.engine.score_engine import DimensionScore, ScoreResult
from ranking_msc.exceptions import ReportError
from ranking_msc.outputs.report_consolidado import (
    _add_score_chart,
    _build_headers,
    export_consolidado_excel,
)

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _make_score_result(
    pontuacao: float = 85.0,
    banda: str = "B",
    regras_executadas: int = 5,
    erros: int = 0,
    alertas: int = 1,
    with_dimensions: bool = False,
) -> ScoreResult:
    """Cria ScoreResult mínimo para testes."""
    dimensions: dict[str, DimensionScore] = {}
    if with_dimensions:
        dimensions = {
            "Estrutura": DimensionScore(
                dimension="Estrutura",
                score=0.9,
                weight_normalized=0.2,
                rules_total=2,
                rules_passed=2,
                rules_failed_alerta=0,
                rules_failed_erro=0,
            ),
            "Fechamento": DimensionScore(
                dimension="Fechamento",
                score=0.8,
                weight_normalized=0.25,
                rules_total=3,
                rules_passed=2,
                rules_failed_alerta=1,
                rules_failed_erro=0,
            ),
        }
    return ScoreResult(
        pontuacao=pontuacao,
        banda=banda,
        dimensions=dimensions,
        regras_executadas=regras_executadas,
        regras_falhas_erro=erros,
        regras_falhas_alerta=alertas,
    )


def _make_period(
    competencia: str,
    pontuacao: float = 85.0,
    banda: str = "B",
    total_pendencias: int = 3,
    with_dimensions: bool = False,
) -> PeriodScore:
    """Cria PeriodScore mínimo para testes."""
    return PeriodScore(
        competencia=competencia,
        score_result=_make_score_result(
            pontuacao=pontuacao,
            banda=banda,
            with_dimensions=with_dimensions,
        ),
        total_pendencias=total_pendencias,
    )


def _make_comparison(
    siconfi: str = "250400",
    periods: list[PeriodScore] | None = None,
) -> PeriodComparison:
    """Cria PeriodComparison para testes."""
    return PeriodComparison(
        siconfi=siconfi,
        periods=periods or [],
    )


# ---------------------------------------------------------------------------
# Testes de export_consolidado_excel
# ---------------------------------------------------------------------------


class TestExportConsolidadoExcel:
    def test_cria_arquivo_excel(self, tmp_path: Path) -> None:
        """Arquivo Excel é criado no diretório de saída."""
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_nome_default_inclui_siconfi(self, tmp_path: Path) -> None:
        """Sem filename, usa consolidado_{siconfi}.xlsx."""
        comparison = _make_comparison(siconfi="123456")
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        assert path.name == "consolidado_123456.xlsx"

    def test_filename_custom_respeitado(self, tmp_path: Path) -> None:
        """Filename explícito substitui o padrão."""
        comparison = _make_comparison()
        path = export_consolidado_excel(
            comparison,
            output_dir=tmp_path,
            filename="relatorio_custom.xlsx",
        )

        assert path.name == "relatorio_custom.xlsx"

    def test_aba_evolucao_existe(self, tmp_path: Path) -> None:
        """Workbook contém aba chamada 'Evolução'."""
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        assert "Evolução" in wb.sheetnames

    def test_colunas_fixas_presentes(self, tmp_path: Path) -> None:
        """Cabeçalhos fixos estão na linha 1 da aba Evolução."""
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

        assert "Competência" in headers
        assert "Pontuação" in headers
        assert "Banda" in headers
        assert "Total Pendências" in headers
        assert "Regras c/ ERRO" in headers
        assert "Regras c/ ALERTA" in headers
        assert "Delta" in headers

    def test_sem_periodos_nao_levanta_excecao(self, tmp_path: Path) -> None:
        """Comparação vazia gera Excel sem levantar exceção."""
        comparison = _make_comparison(periods=[])
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        assert path.exists()

    def test_dados_de_periodo_escritos(self, tmp_path: Path) -> None:
        """Dados de períodos aparecem nas linhas 2+ da aba."""
        periods = [
            _make_period("2024-01", pontuacao=80.0, banda="C", total_pendencias=5),
            _make_period("2024-02", pontuacao=85.0, banda="B", total_pendencias=3),
        ]
        comparison = _make_comparison(periods=periods)
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]

        # Linha 2 = 2024-01
        assert ws.cell(row=2, column=1).value == "2024-01"
        assert ws.cell(row=2, column=2).value == pytest.approx(80.0)
        assert ws.cell(row=2, column=3).value == "C"
        assert ws.cell(row=2, column=4).value == 5

        # Linha 3 = 2024-02
        assert ws.cell(row=3, column=1).value == "2024-02"
        assert ws.cell(row=3, column=2).value == pytest.approx(85.0)

    def test_delta_calculado_na_coluna_7(self, tmp_path: Path) -> None:
        """Coluna Delta (índice 7) contém variação entre períodos."""
        periods = [
            _make_period("2024-01", pontuacao=80.0),
            _make_period("2024-02", pontuacao=85.0),
        ]
        comparison = _make_comparison(periods=periods)
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]

        # Primeiro período → Delta vazio (sem predecessor) — openpyxl lê "" como None
        delta_col = 7
        assert ws.cell(row=2, column=delta_col).value in (None, "")

        # Segundo período → Delta = +5.0
        assert ws.cell(row=3, column=delta_col).value == pytest.approx(5.0)

    def test_dimensoes_presentes_nos_cabecalhos(self, tmp_path: Path) -> None:
        """Colunas de dimensão aparecem no cabeçalho."""
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

        assert "Estrutura (%)" in headers
        assert "Fechamento (%)" in headers
        assert "IC Domínio (%)" in headers
        assert "PCASP Completude (%)" in headers
        assert "Temporal (%)" in headers

    def test_dimensao_score_escrito_quando_presente(self, tmp_path: Path) -> None:
        """Score de dimensão ativa escrito na coluna correta."""
        periods = [_make_period("2024-01", with_dimensions=True)]
        comparison = _make_comparison(periods=periods)
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]

        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        estrutura_col = headers.index("Estrutura (%)") + 1
        fechamento_col = headers.index("Fechamento (%)") + 1

        # Estrutura: 0.9 * 100 = 90.0
        assert ws.cell(row=2, column=estrutura_col).value == pytest.approx(90.0)
        # Fechamento: 0.8 * 100 = 80.0
        assert ws.cell(row=2, column=fechamento_col).value == pytest.approx(80.0)

    def test_dimensao_ausente_escrita_como_vazio(self, tmp_path: Path) -> None:
        """Dimensão sem score (inativa no período) → célula vazia."""
        periods = [_make_period("2024-01", with_dimensions=False)]
        comparison = _make_comparison(periods=periods)
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Evolução"]

        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        estrutura_col = headers.index("Estrutura (%)") + 1

        assert ws.cell(row=2, column=estrutura_col).value in (None, "")

    def test_output_dir_criado_se_ausente(self, tmp_path: Path) -> None:
        """Diretório de saída é criado automaticamente se não existir."""
        nested = tmp_path / "deep" / "nested"
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=nested)

        assert path.exists()

    def test_retorna_path_absoluto(self, tmp_path: Path) -> None:
        """Retorno é sempre Path absoluto."""
        comparison = _make_comparison()
        path = export_consolidado_excel(comparison, output_dir=tmp_path)

        assert path.is_absolute()

    def test_io_error_levanta_report_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falha de I/O levanta ReportError."""
        comparison = _make_comparison()

        def _broken_save(path: str) -> None:
            raise OSError("disco cheio")

        monkeypatch.setattr("openpyxl.Workbook.save", _broken_save)

        with pytest.raises(ReportError, match="Falha ao exportar relatório consolidado"):
            export_consolidado_excel(comparison, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Testes de _build_headers
# ---------------------------------------------------------------------------


class TestBuildHeaders:
    def test_retorna_todos_os_cabecalhos(self) -> None:
        """Retorna cabeçalhos fixos + 5 dimensões = 12 colunas."""
        headers = _build_headers()
        assert len(headers) == 12  # 7 fixos + 5 dimensões

    def test_dimensoes_em_ordem_canonica(self) -> None:
        """Dimensões seguem a ordem canônica definida."""
        headers = _build_headers()
        dim_headers = headers[7:]
        assert dim_headers == [
            "Estrutura (%)",
            "Fechamento (%)",
            "IC Domínio (%)",
            "PCASP Completude (%)",
            "Temporal (%)",
        ]


# ---------------------------------------------------------------------------
# Regressão — Finding 5: decisão LineChart vs SparklineGroup
# ---------------------------------------------------------------------------


class TestLineChartDecision:
    """Finding 5: gráfico usa LineChart (não SparklineGroup — não disponível em openpyxl 3.x)."""

    def test_grafico_usa_linechart(self, tmp_path: Path) -> None:
        """_add_score_chart insere um LineChart na worksheet, não SparklineGroup."""
        from openpyxl import Workbook

        periods = [
            _make_period("2024-01", pontuacao=80.0),
            _make_period("2024-02", pontuacao=85.0),
        ]
        comparison = _make_comparison(periods=periods)

        wb = Workbook()
        ws = wb.active
        assert ws is not None

        # Escreve alguns dados para que a referência tenha linhas válidas
        ws.cell(row=1, column=1, value="Competência")
        ws.cell(row=1, column=2, value="Pontuação")
        ws.cell(row=2, column=1, value="2024-01")
        ws.cell(row=2, column=2, value=80.0)
        ws.cell(row=3, column=1, value="2024-02")
        ws.cell(row=3, column=2, value=85.0)

        _add_score_chart(ws, comparison)

        assert len(ws._charts) == 1, "Esperado exatamente 1 gráfico na worksheet"
        chart = ws._charts[0]
        assert isinstance(chart, LineChart), (
            f"Esperado LineChart, obteve {type(chart).__name__}. "
            "SparklineGroup não está disponível na API pública do openpyxl 3.x."
        )

    def test_grafico_ausente_para_periodo_unico(self) -> None:
        """Sem 2+ períodos, nenhum gráfico é adicionado (evita gráfico vazio)."""
        from openpyxl import Workbook

        periods = [_make_period("2024-01", pontuacao=80.0)]
        comparison = _make_comparison(periods=periods)

        wb = Workbook()
        ws = wb.active
        assert ws is not None

        _add_score_chart(ws, comparison)

        assert len(ws._charts) == 0, "Não deve criar gráfico com menos de 2 períodos"
