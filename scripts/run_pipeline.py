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
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
for _p in (str(_SRC_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _cli_helpers import (  # noqa: E402, F401
    OutputPaths,
    _log_failure,
    _resolve_config_path,
    _resolve_output_paths,
    _resolve_project_path,
)

from ranking_msc.config.settings import Settings, load_settings  # noqa: E402
from ranking_msc.exceptions import InputFormatError, RankingMSCError  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.io.store import make_store  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402
from ranking_msc.services.pipeline import run_full_pipeline  # noqa: E402


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

    run = run_full_pipeline(
        raw_msc,
        settings=settings,
        store=make_store(settings, output_paths.snapshots_dir),
        reports_dir=output_paths.reports_dir,
        logger=logger,
        usuario="cli",
        log_message="Execução CLI concluída",
    )

    logger.info(
        "Pipeline concluído: status=%s pendencias=%d matriz=%s report=%s",
        run.engine_result.status,
        run.engine_result.total_pendencias,
        run.ref,
        run.report_path,
        extra={
            "execucao_id": run.context.execucao_id,
            "competencia": run.context.competencia,
            "siconfi": run.context.siconfi,
            "usuario": run.context.usuario,
        },
    )

    return run.engine_result.status


def main() -> None:
    """Ponto de entrada do script CLI."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
