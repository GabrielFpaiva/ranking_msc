#!/usr/bin/env python3
"""
scripts/benchmark.py
~~~~~~~~~~~~~~~~~~~~

CLI para executar benchmark de performance do pipeline MSC.

Gera CSVs sintéticos de diferentes tamanhos, executa o pipeline
instrumentado e produz ``ref/benchmark_performance.md``.

Uso:
    python scripts/benchmark.py --rows 1000 --output ref/benchmark_performance.md
    python scripts/benchmark.py --rows 100000 500000 1000000 --keep-csv
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from ranking_msc.benchmark import generator, profiler, reporter
from ranking_msc.benchmark.profiler import BenchmarkResult
from ranking_msc.config.settings import load_settings
from ranking_msc.engine.executor import EngineContext, run_engine
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.transform.ic_normalize import normalize_ic

logger = logging.getLogger("ranking_msc")


def main(argv: list[str] | None = None) -> int:
    """Entrypoint principal do benchmark CLI.

    Args:
        argv: argumentos da linha de comando (None usa sys.argv).

    Returns:
        Código de saída (0 = sucesso).
    """
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    settings = load_settings()
    data_dir = Path("data/benchmark")
    output_path = Path(args.output)
    results: list[BenchmarkResult] = []
    interrupted = False

    logger.info(
        "Iniciando benchmark: tamanhos=%s, seed=%d, output=%s",
        args.rows, args.seed, output_path,
    )

    try:
        for n_rows in args.rows:
            logger.info("=== Benchmark com %d linhas ===", n_rows)
            csv_path = data_dir / f"msc_{n_rows}.csv"

            try:
                # Gerar CSV sintético
                generator.generate_csv(
                    n_rows=n_rows,
                    path=csv_path,
                    seed=args.seed,
                    ref_dir=settings.paths.ref_dir,
                )

                # Executar pipeline instrumentado
                result = _run_instrumented_pipeline(csv_path, n_rows, settings)
                results.append(result)

                logger.info(
                    "Benchmark %dk concluído: %.1fs, %.0f MB pico, %.1f rows/s",
                    n_rows // 1000 if n_rows >= 1000 else n_rows,
                    result.total_seconds,
                    result.peak_rss_mb,
                    result.throughput_rows_per_sec,
                )

            except MemoryError:
                logger.error("OOM ao processar n_rows=%d", n_rows)
                results.append(BenchmarkResult(
                    n_rows=n_rows,
                    total_seconds=0.0,
                    peak_rss_mb=profiler.read_peak_rss_mb(),
                    throughput_rows_per_sec=0.0,
                    failed=True,
                    failure_reason="OOM",
                ))
            except Exception as exc:  # noqa: BLE001
                logger.error("Falha no benchmark n_rows=%d", n_rows, exc_info=True)
                results.append(BenchmarkResult(
                    n_rows=n_rows,
                    total_seconds=0.0,
                    peak_rss_mb=profiler.read_peak_rss_mb(),
                    throughput_rows_per_sec=0.0,
                    failed=True,
                    failure_reason=str(exc),
                ))

    except KeyboardInterrupt:
        logger.warning("Benchmark interrompido pelo usuário")
        interrupted = True

    # Escrever relatório (mesmo parcial)
    if results:
        reporter.write_report(results, output_path, interrupted=interrupted)
        logger.info("Relatório escrito em %s", output_path)
    else:
        logger.warning("Nenhum resultado para reportar")

    # Limpar CSVs gerados (exceto se --keep-csv)
    if not args.keep_csv and data_dir.exists():
        shutil.rmtree(data_dir)
        logger.info("Diretório %s removido", data_dir)

    return 0


def _run_instrumented_pipeline(
    csv_path: Path,
    n_rows: int,
    settings: object,
) -> BenchmarkResult:
    """Executa o pipeline com instrumentação de performance.

    Args:
        csv_path: caminho do CSV sintético.
        n_rows: número de linhas no CSV.
        settings: configurações do projeto.

    Returns:
        BenchmarkResult com métricas coletadas.
    """
    context = EngineContext(
        competencia="2026-01",
        siconfi="9999999EX",
        settings=settings,  # type: ignore[arg-type]
        usuario="benchmark",
    )

    with profiler.measure("total") as total:
        with profiler.measure("read_csv") as m_read:
            raw = read_msc_csv(csv_path)
        with profiler.measure("normalize_ic") as m_norm:
            df_norm = normalize_ic(raw.df)
        with profiler.instrument_rules() as rule_metrics:
            with profiler.measure("run_engine") as m_engine:
                run_engine(df_norm, context)

    return BenchmarkResult(
        n_rows=n_rows,
        total_seconds=total.wall_seconds,
        peak_rss_mb=profiler.read_peak_rss_mb(),
        throughput_rows_per_sec=n_rows / total.wall_seconds if total.wall_seconds > 0 else 0.0,
        stages=[m_read.to_stage(), m_norm.to_stage(), m_engine.to_stage()],
        rules=rule_metrics,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Configura e faz parse dos argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Benchmark de performance do pipeline MSC",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--rows",
        nargs="+",
        type=int,
        default=[100_000, 500_000, 1_000_000],
        help="Tamanhos de dataset para benchmark (número de linhas)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed para reprodutibilidade do gerador",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ref/benchmark_performance.md",
        help="Caminho do relatório de saída",
    )
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        default=False,
        help="Preservar CSVs gerados em data/benchmark/",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Ativar logging detalhado (DEBUG)",
    )
    return parser.parse_args(argv)


def _setup_logging(verbose: bool) -> None:
    """Configura logging para o benchmark."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    sys.exit(main())
