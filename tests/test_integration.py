"""
tests/test_integration.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Testes de integração ponta a ponta do pipeline ranking_msc.

Fluxo testado:
    CSV → read_msc_csv() → normalize_ic() → run_engine()
    → write_snapshot_atomic() + export_issues_excel()

Dados de entrada:
    - Arquivos reais de produção em ref/amostras/ (376-393 contas, 25-28k linhas)
    - CSVs sintéticos via build_msc_csv() para cenários negativos controlados

Sem monkeypatch: load_pcasp() e load_tabela_po() usam os arquivos reais
de ref/, que ficam acessíveis porque o pytest roda da raiz do projeto.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import openpyxl

from ranking_msc.config.settings import RulesSettings, Settings
from ranking_msc.engine.executor import EngineContext, run_engine
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.outputs.snapshot import read_snapshot, write_snapshot_atomic
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS
from ranking_msc.transform.ic_normalize import normalize_ic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AMOSTRAS = Path("ref/amostras")

_REGRAS_PILOTO: list[str] = ["R003", "R004", "R010", "R021", "R030"]


def _settings_com_regras() -> Settings:
    """Settings com todas as regras piloto habilitadas."""
    return dataclasses.replace(Settings(), rules=RulesSettings(enabled=_REGRAS_PILOTO))


def _run_pipeline(
    csv_path: Path,
    tmp_path: Path,
) -> object:
    """Executa o pipeline completo e retorna EngineResult.

    Args:
        csv_path: caminho do arquivo CSV MSC de entrada.
        tmp_path: diretório base temporário para outputs isolados.

    Returns:
        EngineResult com status, pendencias e total_pendencias.
    """
    raw = read_msc_csv(csv_path)
    df = normalize_ic(raw.df)

    context = EngineContext(
        competencia=raw.competencia,
        siconfi=raw.siconfi,
        settings=_settings_com_regras(),
        usuario="integration_test",
        pre_pivot_issues=raw.pre_pivot_issues,
    )

    result = run_engine(df, context)

    write_snapshot_atomic(
        result.pendencias,
        raw.competencia,
        base_dir=tmp_path / "snapshots",
    )
    export_issues_excel(
        result.pendencias,
        raw.competencia,
        output_dir=tmp_path / "reports",
    )

    return result, raw.competencia


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestPipelineComDadosReais:
    def test_pipeline_csv_real_novembro_sem_crash(self, tmp_path: Path) -> None:
        """Pipeline com msc_2025-11.csv (376 contas, 25k linhas) não crasha e gera outputs."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        result, competencia = _run_pipeline(csv_path, tmp_path)

        assert result.status in {"OK", "PARCIAL", "ERRO"}
        assert isinstance(result.total_pendencias, int)
        assert (tmp_path / "snapshots" / competencia / "resultado_regras.parquet").exists()
        assert any((tmp_path / "reports").glob("*.xlsx"))
        assert set(FACT_RESULTADO_REGRAS_COLUMNS).issubset(result.pendencias.columns)

    def test_pipeline_csv_real_dezembro_sem_crash(self, tmp_path: Path) -> None:
        """Pipeline com msc_2025-12.csv (393 contas, 28k linhas) não crasha e gera outputs."""
        csv_path = _AMOSTRAS / "msc_2025-12.csv"
        result, competencia = _run_pipeline(csv_path, tmp_path)

        assert result.status in {"OK", "PARCIAL", "ERRO"}
        assert (tmp_path / "snapshots" / competencia / "resultado_regras.parquet").exists()
        assert any((tmp_path / "reports").glob("*.xlsx"))


class TestCriterioDeAceite:
    """Testes que mapeiam diretamente o critério de aceite da F2-18:
    'Pipeline completo sem crash e outputs válidos.'
    """

    def test_pipeline_completo_sem_crash(self, tmp_path: Path) -> None:
        """Pipeline executa do início ao fim sem levantar nenhuma exceção."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        # Qualquer exceção aqui representa falha direta do critério
        result, _ = _run_pipeline(csv_path, tmp_path)
        assert result is not None

    def test_output_parquet_e_valido_e_legivel(self, tmp_path: Path) -> None:
        """Snapshot Parquet gerado é legível e contém as colunas do schema."""
        import pandas as pd
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        result, competencia = _run_pipeline(csv_path, tmp_path)

        parquet_path = tmp_path / "snapshots" / competencia / "resultado_regras.parquet"
        assert parquet_path.exists(), "Parquet não foi criado"

        df = pd.read_parquet(parquet_path)
        assert list(df.columns) == FACT_RESULTADO_REGRAS_COLUMNS, (
            f"Schema do Parquet incorreto: {list(df.columns)}"
        )
        assert len(df) == result.total_pendencias, (
            "Parquet tem número de linhas diferente do engine result"
        )

    def test_output_excel_e_valido_com_abas_e_conteudo(self, tmp_path: Path) -> None:
        """Excel gerado tem as duas abas esperadas e a aba Pendências contém as colunas certas."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        _, competencia = _run_pipeline(csv_path, tmp_path)

        excel_files = list((tmp_path / "reports").glob("*.xlsx"))
        assert len(excel_files) == 1, "Nenhum ou mais de um Excel gerado"

        wb = openpyxl.load_workbook(excel_files[0])
        assert "Resumo" in wb.sheetnames, "Aba 'Resumo' ausente no Excel"
        assert "Pendências" in wb.sheetnames, "Aba 'Pendências' ausente no Excel"

        # Aba Pendências: cabeçalho usa rótulos em português (F2-21)
        ws = wb["Pendências"]
        header = [cell.value for cell in ws[1]]
        expected_pt_headers = [
            "Regra", "Nome da Regra", "Dimensão", "Severidade",
            "Conta Contábil", "Descrição", "Valor Esperado", "Valor Encontrado", "Competência",
        ]
        for col in expected_pt_headers:
            assert col in header, f"Coluna '{col}' ausente no cabeçalho do Excel"

    def test_competencia_e_siconfi_propagados_corretamente(
        self,
        tmp_path: Path,
        build_msc_csv: object,
    ) -> None:
        """Metadados do CSV (competencia e siconfi) chegam corretos até o snapshot."""
        import pandas as pd

        csv_bytes: bytes = build_msc_csv(siconfi="9999999EX", competencia="2025-06")
        csv_path = tmp_path / "MSC_9999999EX_2025-06.csv"
        csv_path.write_bytes(csv_bytes)

        result, competencia = _run_pipeline(csv_path, tmp_path)

        assert competencia == "2025-06"

        parquet_path = tmp_path / "snapshots" / "2025-06" / "resultado_regras.parquet"
        assert parquet_path.exists()

        df = pd.read_parquet(parquet_path)
        if not df.empty:
            assert (df["competencia"] == "2025-06").all(), (
                "Competência incorreta no snapshot"
            )

    def test_regras_executam_sem_crash_e_pendencias_com_erro_geradas(
        self,
        tmp_path: Path,
        build_msc_csv: object,
    ) -> None:
        """Engine status 'OK' = regras rodaram sem crash; pendências ERRO = violações detectadas.

        status 'OK' significa que nenhuma regra travou durante a execução.
        status 'PARCIAL'/'ERRO' significa que a regra em si teve uma falha de código.
        Severidade 'ERRO' nas pendências indica uma violação de negócio encontrada.
        """
        rows = [
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "500.00", "beginning_balance", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "500.00", "beginning_balance", "C"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "100.00", "period_change", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "100.00", "period_change", "C"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "600.00", "ending_balance", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "600.00", "ending_balance", "C"],
        ]
        csv_bytes: bytes = build_msc_csv(rows=rows)
        csv_path = tmp_path / "MSC_2507507EX_2025-05.csv"
        csv_path.write_bytes(csv_bytes)

        result, _ = _run_pipeline(csv_path, tmp_path)

        # Engine rodou sem crash (nenhuma regra lançou exceção)
        assert result.status == "OK", (
            f"Engine status inesperado '{result.status}': alguma regra crashou"
        )
        # Violações de negócio foram detectadas pelas regras (R010: conta inválida)
        assert result.total_pendencias >= 1
        assert (result.pendencias["severidade"] == "ERRO").any(), (
            "Nenhuma pendência com severidade ERRO foi gerada"
        )


class TestPipelineComDadosSinteticos:
    def test_pipeline_conta_invalida_gera_pendencia_r010(
        self,
        tmp_path: Path,
        build_msc_csv: object,
    ) -> None:
        """Conta ausente no PCASP real gera pendência R010 sem abortar o pipeline."""
        rows = [
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "1000.00", "beginning_balance", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "1000.00", "beginning_balance", "C"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "200.00", "period_change", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "200.00", "period_change", "C"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "1200.00", "ending_balance", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "1200.00", "ending_balance", "C"],
        ]
        csv_bytes: bytes = build_msc_csv(rows=rows)
        csv_path = tmp_path / "MSC_2507507EX_2025-03.csv"
        csv_path.write_bytes(csv_bytes)

        result, competencia = _run_pipeline(csv_path, tmp_path)

        assert result.total_pendencias >= 1
        pendencias_r010 = result.pendencias[result.pendencias["regra_id"] == "R010"]
        assert len(pendencias_r010) >= 1
        assert (pendencias_r010["severidade"] == "ERRO").all()
        assert (tmp_path / "snapshots" / competencia / "resultado_regras.parquet").exists()
        assert any((tmp_path / "reports").glob("*.xlsx"))

    def test_pipeline_outputs_schema_correto(
        self,
        tmp_path: Path,
        msc_csv_path: Path,
    ) -> None:
        """Outputs do pipeline respeitam o schema FACT_RESULTADO_REGRAS_COLUMNS."""
        result, competencia = _run_pipeline(msc_csv_path, tmp_path)

        # Schema exato do DataFrame de pendências
        assert list(result.pendencias.columns) == FACT_RESULTADO_REGRAS_COLUMNS

        # Snapshot relido bate com o resultado original
        snapshot_df = read_snapshot(competencia, base_dir=tmp_path / "snapshots")
        assert list(snapshot_df.columns) == FACT_RESULTADO_REGRAS_COLUMNS
        assert len(snapshot_df) == len(result.pendencias)

        # Excel com as duas abas esperadas
        excel_files = list((tmp_path / "reports").glob("*.xlsx"))
        assert len(excel_files) == 1
        wb = openpyxl.load_workbook(excel_files[0])
        assert "Resumo" in wb.sheetnames
        assert "Pendências" in wb.sheetnames

    def test_pipeline_dois_meses_geram_snapshots_separados(
        self,
        tmp_path: Path,
        build_msc_csv: object,
    ) -> None:
        """Dois CSVs de competências diferentes produzem snapshots isolados."""
        for mes in ("2025-10", "2025-11"):
            csv_bytes: bytes = build_msc_csv(competencia=mes)
            csv_path = tmp_path / f"MSC_2507507EX_{mes}.csv"
            csv_path.write_bytes(csv_bytes)
            _run_pipeline(csv_path, tmp_path)

        assert (tmp_path / "snapshots" / "2025-10" / "resultado_regras.parquet").exists()
        assert (tmp_path / "snapshots" / "2025-11" / "resultado_regras.parquet").exists()

        df_10 = read_snapshot("2025-10", base_dir=tmp_path / "snapshots")
        df_11 = read_snapshot("2025-11", base_dir=tmp_path / "snapshots")
        assert (df_10["competencia"] == "2025-10").all() or df_10.empty
        assert (df_11["competencia"] == "2025-11").all() or df_11.empty
