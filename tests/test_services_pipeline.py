"""Testes de ``ranking_msc.services.pipeline`` — orquestração compartilhada CLI×API."""

from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import load_workbook

import ranking_msc.rules  # noqa: F401  -- popular RULE_REGISTRY
from ranking_msc.config.settings import PathsSettings, RulesSettings, Settings
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.io.store import ParquetStore
from ranking_msc.services.pipeline import run_full_pipeline


def _settings_com_r082() -> Settings:
    """Settings mínimo com uma regra real habilitada."""
    return Settings(rules=RulesSettings(enabled=["R082"]))


def test_pipeline_normaliza_usando_o_ref_dir_configurado(
    monkeypatch,
    msc_csv_path: Path,
    tmp_path: Path,
) -> None:
    """O caminho do mapeamento IC/TIPO sai de settings.paths.ref_dir.

    Congelado pelo PyInstaller, o default derivado de __file__ aponta para fora
    do bundle — o pipeline não pode depender dele.
    """
    capturado: dict[str, object] = {}

    def _spy(df, *, mapping_path=None):
        capturado["mapping_path"] = mapping_path
        return df

    monkeypatch.setattr("ranking_msc.services.pipeline.normalize_ic", _spy)

    raw = read_msc_csv(msc_csv_path)
    settings = Settings(
        paths=PathsSettings(ref_dir=str(tmp_path / "ref_instalado")),
        rules=RulesSettings(enabled=[]),
    )

    run_full_pipeline(
        raw,
        settings=settings,
        store=ParquetStore(tmp_path / "snapshots"),
        reports_dir=tmp_path / "reports",
        logger=logging.getLogger("ranking_msc_test_service"),
        usuario="teste",
    )

    assert capturado["mapping_path"] == Path(settings.paths.ref_dir) / "mapeamento_ic_tipo.csv"


class TestRunFullPipeline:
    def test_pipeline_completo_persiste_artefatos(
        self,
        msc_csv_path: Path,
        tmp_path: Path,
    ) -> None:
        """Sequência completa gera snapshots, metadata e Excel."""
        raw = read_msc_csv(msc_csv_path)
        snapshots_dir = tmp_path / "snapshots"
        reports_dir = tmp_path / "reports"

        run = run_full_pipeline(
            raw,
            settings=_settings_com_r082(),
            store=ParquetStore(snapshots_dir),
            reports_dir=reports_dir,
            logger=logging.getLogger("ranking_msc_test_service"),
            usuario="teste",
        )

        assert run.engine_result.status in {"OK", "PARCIAL", "ERRO"}
        assert (snapshots_dir / raw.siconfi / raw.competencia / "resultado_regras.parquet").exists()
        assert run.report_path.exists()
        normalizado = (
            snapshots_dir / raw.siconfi / raw.competencia / "msc_normalizado.parquet"
        )
        assert normalizado.exists()

    def test_excel_gerado_contem_aba_score(
        self,
        msc_csv_path: Path,
        tmp_path: Path,
    ) -> None:
        """Regressão: o Excel do pipeline SEMPRE inclui a aba Score.

        O bug original nasceu da duplicação CLI×API — a cópia da API não
        passava score_result ao export e o Excel saía sem a aba Score.
        """
        raw = read_msc_csv(msc_csv_path)

        run = run_full_pipeline(
            raw,
            settings=_settings_com_r082(),
            store=ParquetStore(tmp_path / "snapshots"),
            reports_dir=tmp_path / "reports",
            logger=logging.getLogger("ranking_msc_test_service"),
            usuario="teste",
        )

        workbook = load_workbook(run.report_path, read_only=True)
        assert "Score" in workbook.sheetnames
