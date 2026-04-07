"""Testes da CLI de execução ponta a ponta em ``scripts/run_pipeline.py``."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import scripts.run_pipeline as cli

from ranking_msc.config.settings import PathsSettings, Settings
from ranking_msc.exceptions import ConfigError
from ranking_msc.io.reader_msc import RawMSC


def test_resolve_output_paths_sem_output_dir_usa_settings() -> None:
    """Resolve diretórios a partir de settings quando --output-dir não é informado."""
    settings = Settings(
        paths=PathsSettings(
            data_dir="./data",
            snapshots_dir="./data/snapshots",
            reports_dir="./data/reports",
            logs_dir="./data/logs",
            ref_dir="./ref",
        )
    )

    resolved = cli._resolve_output_paths(settings, None)

    assert resolved.snapshots_dir == (cli._PROJECT_ROOT / "data/snapshots").resolve()
    assert resolved.reports_dir == (cli._PROJECT_ROOT / "data/reports").resolve()
    assert resolved.logs_dir == (cli._PROJECT_ROOT / "data/logs").resolve()


def test_resolve_output_paths_com_output_dir_sobrescreve_settings(tmp_path: Path) -> None:
    """Quando --output-dir é informado, a CLI deriva snapshots/reports/logs nele."""
    settings = Settings()
    base_dir = tmp_path / "saida"

    resolved = cli._resolve_output_paths(settings, str(base_dir))

    assert resolved.snapshots_dir == (base_dir / "snapshots").resolve()
    assert resolved.reports_dir == (base_dir / "reports").resolve()
    assert resolved.logs_dir == (base_dir / "logs").resolve()


def test_run_cli_fluxo_feliz_orquestra_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executa fluxo completo da CLI chamando os módulos na ordem esperada."""
    csv_path = tmp_path / "entrada.csv"
    csv_path.write_text("conteudo", encoding="utf-8")

    config_path = tmp_path / "settings.yaml"
    config_path.write_text("app: {}\n", encoding="utf-8")

    output_base = tmp_path / "output"
    settings = Settings()
    logger = logging.getLogger("ranking_msc_test_cli")

    raw_df = pd.DataFrame(
        [
            {
                "competencia": "2025-11",
                "siconfi": "2507507EX",
                "conta_contabil": "111110200",
                "ic1": "10131",
                "tipo1": "PO",
                "ic2": "",
                "tipo2": "",
                "ic3": "",
                "tipo3": "",
                "ic4": "",
                "tipo4": "",
                "ic5": "",
                "tipo5": "",
                "ic6": "",
                "tipo6": "",
                "saldo_inicial_debito": 1.0,
                "saldo_inicial_credito": 0.0,
                "movimento_debito": 0.0,
                "movimento_credito": 0.0,
                "saldo_final_debito": 1.0,
                "saldo_final_credito": 0.0,
            },
        ]
    )
    normalized_df = raw_df.copy()
    pendencias_df = pd.DataFrame(
        columns=[
            "regra_id",
            "regra_nome",
            "dimensao",
            "severidade",
            "conta_contabil",
            "descricao",
            "valor_esperado",
            "valor_encontrado",
            "competencia",
        ]
    )

    captured: dict[str, object] = {}

    def fake_load_settings(path: Path) -> Settings:
        captured["config_path"] = path
        return settings

    def fake_setup_logging(*, log_dir: str | Path, **_: object) -> logging.Logger:
        captured["log_dir"] = Path(log_dir)
        return logger

    def fake_read_msc_csv(path: Path) -> RawMSC:
        captured["csv_path"] = path
        return RawMSC(
            competencia="2025-11",
            siconfi="2507507EX",
            df=raw_df,
            source=str(path),
        )

    def fake_normalize_ic(df: pd.DataFrame) -> pd.DataFrame:
        captured["normalize_input_cols"] = list(df.columns)
        return normalized_df

    def fake_run_engine(df: pd.DataFrame, context: object) -> SimpleNamespace:
        captured["engine_rows"] = len(df)
        captured["engine_context_usuario"] = getattr(context, "usuario", "")
        captured["engine_context_competencia"] = getattr(context, "competencia", "")
        return SimpleNamespace(
            status="OK",
            pendencias=pendencias_df,
            total_pendencias=0,
        )

    def fake_write_snapshot_atomic(
        df: pd.DataFrame,
        competencia: str,
        *,
        base_dir: str | Path,
        label: str,
    ) -> Path:
        captured["snapshot_rows"] = len(df)
        captured["snapshot_competencia"] = competencia
        captured["snapshot_base"] = Path(base_dir)
        captured["snapshot_label"] = label
        return Path(base_dir) / competencia / f"{label}.parquet"

    def fake_export_issues_excel(
        df_pendencias: pd.DataFrame,
        competencia: str,
        *,
        output_dir: str | Path,
        filename: str | None = None,
    ) -> Path:
        del filename
        captured["report_rows"] = len(df_pendencias)
        captured["report_competencia"] = competencia
        captured["report_dir"] = Path(output_dir)
        return Path(output_dir) / f"pendencias_{competencia}.xlsx"

    def fake_log_execucao(logger_obj: logging.Logger, **kwargs: object) -> None:
        captured["log_execucao_logger"] = logger_obj.name
        captured["log_execucao_status"] = kwargs.get("status")
        captured["log_execucao_competencia"] = kwargs.get("competencia")

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "setup_logging", fake_setup_logging)
    monkeypatch.setattr(cli, "read_msc_csv", fake_read_msc_csv)
    monkeypatch.setattr(cli, "normalize_ic", fake_normalize_ic)
    monkeypatch.setattr(cli, "run_engine", fake_run_engine)
    monkeypatch.setattr(cli, "write_snapshot_atomic", fake_write_snapshot_atomic)
    monkeypatch.setattr(cli, "export_issues_excel", fake_export_issues_excel)
    monkeypatch.setattr(cli, "log_execucao", fake_log_execucao)

    exit_code = cli.run_cli(
        [
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_base),
        ]
    )

    assert exit_code == 0
    assert captured["config_path"] == config_path.resolve()
    assert captured["csv_path"] == csv_path.resolve()
    assert captured["log_dir"] == (output_base / "logs").resolve()
    assert captured["engine_rows"] == 1
    assert captured["engine_context_usuario"] == "cli"
    assert captured["engine_context_competencia"] == "2025-11"
    assert captured["snapshot_rows"] == 0
    assert captured["snapshot_competencia"] == "2025-11"
    assert captured["snapshot_base"] == (output_base / "snapshots" / "2507507EX").resolve()
    assert captured["snapshot_label"] == "resultado_regras"
    assert captured["report_rows"] == 0
    assert captured["report_competencia"] == "2025-11"
    assert captured["report_dir"] == (output_base / "reports").resolve()
    assert captured["log_execucao_logger"] == "ranking_msc_test_cli"
    assert captured["log_execucao_status"] == "OK"
    assert captured["log_execucao_competencia"] == "2025-11"


def test_run_cli_status_erro_retorna_codigo_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Status ERRO no engine resulta em código de saída 1 na CLI."""
    logger = logging.getLogger("ranking_msc_test_cli_erro")

    monkeypatch.setattr(cli, "load_settings", lambda path: Settings())
    monkeypatch.setattr(
        cli,
        "_resolve_output_paths",
        lambda settings, output_dir: cli.OutputPaths(
            snapshots_dir=Path("/tmp/snapshots"),
            reports_dir=Path("/tmp/reports"),
            logs_dir=Path("/tmp/logs"),
        ),
    )
    monkeypatch.setattr(cli, "setup_logging", lambda *, log_dir, **kwargs: logger)
    monkeypatch.setattr(cli, "_execute_pipeline", lambda **kwargs: "ERRO")

    exit_code = cli.run_cli(["--csv", "arquivo.csv"])

    assert exit_code == 1


def test_run_cli_erro_de_config_retorna_codigo_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha prevista de configuração retorna código de saída 2."""
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda path: (_ for _ in ()).throw(ConfigError("config inválido")),
    )

    exit_code = cli.run_cli(["--csv", "arquivo.csv"])

    assert exit_code == 2
