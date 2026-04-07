#!/usr/bin/env python3
"""CLI para execução ponta a ponta do pipeline Ranking MSC.

Fluxo executado:
    CSV MSC -> read_msc_csv() -> normalize_ic() -> run_engine()
    -> snapshot Parquet + relatório Excel + log JSON Lines.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.config.settings import Settings, load_settings  # noqa: E402
from ranking_msc.engine.executor import EngineContext, run_engine  # noqa: E402
from ranking_msc.exceptions import InputFormatError, RankingMSCError  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.outputs.logs import log_execucao, setup_logging  # noqa: E402
from ranking_msc.outputs.reports import export_issues_excel  # noqa: E402
from ranking_msc.outputs.snapshot import write_snapshot_atomic  # noqa: E402
from ranking_msc.transform.ic_normalize import normalize_ic  # noqa: E402


@dataclass(frozen=True)
class OutputPaths:
    """Diretórios de saída usados pela execução CLI."""

    snapshots_dir: Path
    reports_dir: Path
    logs_dir: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando.

    Args:
        argv: lista de argumentos (sem nome do programa). Se ``None``,
            usa ``sys.argv``.

    Returns:
        Namespace com ``csv``, ``config`` e ``output_dir``.
    """
    parser = argparse.ArgumentParser(
        description="Executa o pipeline completo do Ranking MSC via CLI.",
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Caminho do arquivo CSV MSC de entrada.",
    )
    parser.add_argument(
        "--config",
        required=False,
        help="Caminho do settings.yaml (opcional).",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        help=(
            "Diretório base de saída (opcional). "
            "Quando informado, usa <output-dir>/snapshots, /reports e /logs."
        ),
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Executa a CLI com tratamento padronizado de erros.

    Args:
        argv: lista de argumentos (sem nome do programa).

    Returns:
        Código de saída Unix.
    """
    args = parse_args(argv)
    csv_path = Path(args.csv).expanduser().resolve()
    config_path = _resolve_config_path(args.config)

    logger: logging.Logger | None = None

    try:
        settings = load_settings(config_path)
        output_paths = _resolve_output_paths(settings, args.output_dir)
        logger = setup_logging(log_dir=output_paths.logs_dir)

        status = _execute_pipeline(
            csv_path=csv_path,
            settings=settings,
            output_paths=output_paths,
            logger=logger,
        )
        return 1 if status == "ERRO" else 0
    except RankingMSCError as exc:
        _log_failure(logger, f"Falha ao executar pipeline: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        _log_failure(logger, f"Falha inesperada ao executar pipeline: {exc}")
        return 3


def _resolve_config_path(config_arg: str | None) -> Path:
    """Resolve o caminho do arquivo de configuração da execução.

    Args:
        config_arg: valor recebido em ``--config``.

    Returns:
        Path absoluto do settings.yaml.
    """
    if not config_arg:
        return (_PROJECT_ROOT / "config" / "settings.yaml").resolve()

    config_path = Path(config_arg).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    return config_path.resolve()


def _resolve_output_paths(settings: Settings, output_dir_arg: str | None) -> OutputPaths:
    """Resolve diretórios de snapshots, relatórios e logs.

    Args:
        settings: configurações carregadas do projeto.
        output_dir_arg: argumento de ``--output-dir``.

    Returns:
        Dataclass ``OutputPaths`` com diretórios absolutos.
    """
    if output_dir_arg:
        base_dir = Path(output_dir_arg).expanduser()
        if not base_dir.is_absolute():
            base_dir = Path.cwd() / base_dir
        base_dir = base_dir.resolve()
        return OutputPaths(
            snapshots_dir=base_dir / "snapshots",
            reports_dir=base_dir / "reports",
            logs_dir=base_dir / "logs",
        )

    return OutputPaths(
        snapshots_dir=_resolve_project_path(settings.paths.snapshots_dir),
        reports_dir=_resolve_project_path(settings.paths.reports_dir),
        logs_dir=_resolve_project_path(settings.paths.logs_dir),
    )


def _resolve_project_path(path_value: str) -> Path:
    """Resolve caminho de settings relativo à raiz do projeto."""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (_PROJECT_ROOT / path).resolve()


def _execute_pipeline(
    *,
    csv_path: Path,
    settings: Settings,
    output_paths: OutputPaths,
    logger: logging.Logger,
) -> str:
    """Executa o pipeline e persiste artefatos de saída.

    Args:
        csv_path: caminho do CSV MSC.
        settings: configurações do projeto.
        output_paths: diretórios de saída resolvidos.
        logger: logger configurado do projeto.

    Returns:
        Status final retornado pelo engine (``OK``, ``PARCIAL`` ou ``ERRO``).

    Raises:
        InputFormatError: se o CSV de entrada não existir.
        RankingMSCError: em erros dos módulos do projeto.
    """
    if not csv_path.exists():
        raise InputFormatError(f"Arquivo CSV não encontrado: {csv_path}")

    logger.info("Iniciando pipeline CLI para arquivo: %s", csv_path)

    raw_msc = read_msc_csv(csv_path)
    normalized_df = normalize_ic(raw_msc.df)

    # Grava snapshot do DataFrame normalizado ANTES de executar as regras.
    # Namespaceado por siconfi para evitar colisão entre entes no mesmo diretório.
    # R054 e regras temporais futuras leem este snapshot para comparar com o mês anterior.
    write_snapshot_atomic(
        normalized_df,
        raw_msc.competencia,
        base_dir=output_paths.snapshots_dir / raw_msc.siconfi,
        label="msc_normalizado",
    )

    context = EngineContext(
        competencia=raw_msc.competencia,
        siconfi=raw_msc.siconfi,
        settings=settings,
        snapshots_dir=output_paths.snapshots_dir,
        usuario="cli",
        pre_pivot_issues=raw_msc.pre_pivot_issues,
    )
    logger.info(
        "Executando motor de regras para competencia=%s siconfi=%s",
        context.competencia,
        context.siconfi,
        extra={
            "execucao_id": context.execucao_id,
            "competencia": context.competencia,
            "siconfi": context.siconfi,
            "usuario": context.usuario,
        },
    )

    engine_result = run_engine(normalized_df, context)

    snapshot_path = write_snapshot_atomic(
        engine_result.pendencias,
        raw_msc.competencia,
        base_dir=output_paths.snapshots_dir / raw_msc.siconfi,
        label="resultado_regras",
    )
    report_path = export_issues_excel(
        engine_result.pendencias,
        raw_msc.competencia,
        output_dir=output_paths.reports_dir,
    )

    log_execucao(
        logger,
        execucao_id=context.execucao_id,
        competencia=context.competencia,
        status=engine_result.status,
        message="Execução CLI concluída",
        siconfi=context.siconfi,
        usuario=context.usuario,
    )

    logger.info(
        "Pipeline concluído: status=%s pendencias=%d snapshot=%s report=%s",
        engine_result.status,
        engine_result.total_pendencias,
        snapshot_path,
        report_path,
        extra={
            "execucao_id": context.execucao_id,
            "competencia": context.competencia,
            "siconfi": context.siconfi,
            "usuario": context.usuario,
        },
    )

    return engine_result.status


def _log_failure(logger: logging.Logger | None, message: str) -> None:
    """Registra falha de execução com fallback de logging para stderr."""
    if logger is not None:
        logger.error(message, exc_info=True)
        return

    logging.basicConfig(
        level=logging.ERROR,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    logging.getLogger("ranking_msc").error(message, exc_info=True)


def main() -> None:
    """Ponto de entrada do script CLI."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
