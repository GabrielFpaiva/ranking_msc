#!/usr/bin/env python3
"""CLI para comparação de scores entre competências de um ente SICONFI.

Lê snapshots existentes e exibe a evolução temporal do score, mostrando
pontuação, banda e variação entre períodos.

Uso::

    python scripts/compare_periods.py --siconfi 250400
    python scripts/compare_periods.py --siconfi 250400 --competencias 2024-01 2024-02 2024-03
    python scripts/compare_periods.py --siconfi 250400 --snapshots-dir ./data/snapshots
    python scripts/compare_periods.py --siconfi 250400 --output-dir ./data/reports

Códigos de saída:
    0 — comparação concluída com pelo menos 1 período
    2 — erro de infraestrutura (sem snapshots, config inválida)
    3 — falha inesperada
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

from _cli_helpers import _log_failure, _resolve_config_path, _resolve_project_path  # noqa: E402

from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.engine.compare_periods import PeriodComparison, compare_periods  # noqa: E402
from ranking_msc.io.store import make_store  # noqa: E402
from ranking_msc.exceptions import RankingMSCError  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402
from ranking_msc.outputs.report_consolidado import export_consolidado_excel  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando.

    Args:
        argv: lista de argumentos (sem nome do programa).

    Returns:
        Namespace com siconfi, competencias, config, snapshots_dir, output_dir.
    """
    parser = argparse.ArgumentParser(
        description="Compara scores entre competências de um ente SICONFI.",
    )
    parser.add_argument(
        "--siconfi",
        required=True,
        help="Código do ente SICONFI (ex: 250400).",
    )
    parser.add_argument(
        "--competencias",
        nargs="+",
        metavar="YYYY-MM",
        help=(
            "Competências a comparar (ex: 2024-01 2024-02). "
            "Se omitido, descobre automaticamente a partir dos snapshots."
        ),
    )
    parser.add_argument(
        "--config",
        required=False,
        help="Caminho do settings.yaml (opcional).",
    )
    parser.add_argument(
        "--snapshots-dir",
        required=False,
        help="Diretório raiz de snapshots (opcional).",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        help=(
            "Diretório de saída para o relatório Excel consolidado (opcional). "
            "Quando informado, exporta consolidado_{siconfi}.xlsx no diretório indicado."
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
    config_path = _resolve_config_path(args.config)
    logger: logging.Logger | None = None

    try:
        settings = load_settings(config_path)
        logs_dir = _resolve_project_path(settings.paths.logs_dir)
        logger = setup_logging(log_dir=logs_dir)

        snapshots_dir = _resolve_snapshots_dir(settings, args.snapshots_dir)

        result = compare_periods(
            siconfi=args.siconfi,
            store=make_store(settings, snapshots_dir),
            settings=settings,
            competencias=args.competencias,
        )

        if not result.periods:
            _log_failure(
                logger,
                f"Nenhum snapshot encontrado para siconfi={args.siconfi} em {snapshots_dir}",
            )
            return 2

        _print_comparison(result)

        if args.output_dir:
            report_path = export_consolidado_excel(
                result,
                output_dir=args.output_dir,
            )
            print(f"\nRelatório consolidado exportado: {report_path}")
            logger.info(
                "Relatório consolidado exportado: siconfi=%s path=%s",
                args.siconfi,
                report_path,
            )

        logger.info(
            "Comparação concluída: siconfi=%s períodos=%d",
            args.siconfi,
            len(result.periods),
        )
        return 0

    except RankingMSCError as exc:
        _log_failure(logger, f"Falha ao comparar competências: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        _log_failure(logger, f"Falha inesperada: {exc}")
        return 3


def _print_comparison(result: PeriodComparison) -> None:
    """Imprime tabela de evolução de scores no stdout.

    Args:
        result: comparação calculada pelo compare_periods.
    """
    header = f"Evolução de scores — siconfi {result.siconfi}"
    print(header)
    print("─" * 62)
    print(f"{'Competência':<13} {'Score':>6}  {'Banda':>5}  {'Δ Score':>8}  {'Pendências':>10}")
    print("─" * 62)

    for i, period in enumerate(result.periods):
        delta = result.score_delta(i)
        delta_str = f"{delta:+.2f}" if delta is not None else "—"
        print(
            f"{period.competencia:<13} "
            f"{period.score_result.pontuacao:>6.2f}  "
            f"{period.score_result.banda:>5}  "
            f"{delta_str:>8}  "
            f"{period.total_pendencias:>10}"
        )

    print("─" * 62)


def _resolve_snapshots_dir(settings: object, snapshots_dir_arg: str | None) -> Path:
    """Resolve o diretório de snapshots a partir do argumento ou das settings.

    Args:
        settings: configurações do projeto.
        snapshots_dir_arg: argumento --snapshots-dir (pode ser None).

    Returns:
        Path absoluto do diretório de snapshots.
    """
    if snapshots_dir_arg:
        p = Path(snapshots_dir_arg).expanduser()
        return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()

    from ranking_msc.config.settings import Settings  # noqa: PLC0415
    assert isinstance(settings, Settings)
    return _resolve_project_path(settings.paths.snapshots_dir)


def main() -> None:
    """Ponto de entrada do script CLI."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
