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
