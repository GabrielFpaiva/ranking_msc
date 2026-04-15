#!/usr/bin/env python3
"""CLI para processamento em lote de múltiplos CSVs MSC.

Processa todos os arquivos ``*.csv`` de um diretório, gerando snapshot
Parquet e relatório Excel para cada competência. Erros em arquivos
individuais são registrados e o batch continua nos demais.

Uso::

    python scripts/run_batch.py --dir ./csvs
    python scripts/run_batch.py --dir ./csvs --config config/settings.yaml
    python scripts/run_batch.py --dir ./csvs --output-dir ./saida

Códigos de saída:
    0 — todos os CSVs processados com sucesso (OK)
    1 — pelo menos um CSV falhou ou ficou parcial
    2 — erro de infraestrutura (configuração inválida, diretório vazio/inexistente)
    3 — falha inesperada
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.config.settings import Settings, load_settings  # noqa: E402
from ranking_msc.engine.executor import EngineContext, run_engine  # noqa: E402
from ranking_msc.exceptions import RankingMSCError  # noqa: E402
from ranking_msc.io.reader_msc import read_msc_csv  # noqa: E402
from ranking_msc.outputs.logs import log_execucao, setup_logging  # noqa: E402
from ranking_msc.outputs.reports import export_issues_excel  # noqa: E402
from ranking_msc.outputs.snapshot import write_snapshot_atomic  # noqa: E402
from ranking_msc.transform.ic_normalize import normalize_ic  # noqa: E402


@dataclass(frozen=True)
class OutputPaths:
    """Diretórios de saída usados pelo batch."""

    snapshots_dir: Path
    reports_dir: Path
    logs_dir: Path


@dataclass
class CsvResult:
    """Resultado do processamento de um CSV individual dentro do batch."""

    csv_path: Path
    status: str                 # "OK", "PARCIAL", "ERRO", "EXCECAO"
    competencia: str = ""
    siconfi: str = ""
    pendencias: int = 0
    error_message: str = ""

    @property
    def succeeded(self) -> bool:
        """Retorna True se o processamento foi bem-sucedido (OK ou PARCIAL)."""
        return self.status in ("OK", "PARCIAL")


@dataclass
class BatchSummary:
    """Resumo consolidado do processamento em lote."""

    results: list[CsvResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Número total de CSVs encontrados."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Número de CSVs com status OK."""
        return sum(1 for r in self.results if r.status == "OK")

    @property
    def partial(self) -> int:
        """Número de CSVs com status PARCIAL (regras com erro mas pipeline concluído)."""
        return sum(1 for r in self.results if r.status == "PARCIAL")

    @property
    def failed(self) -> int:
        """Número de CSVs com status ERRO ou EXCECAO."""
        return sum(1 for r in self.results if r.status in ("ERRO", "EXCECAO"))

    @property
    def exit_code(self) -> int:
        """Código de saída Unix derivado do resultado do batch.

        Returns:
            0 se todos OK, 1 se houve falhas parciais ou totais.
        """
        if self.failed > 0 or self.partial > 0:
            return 1
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando.

    Args:
        argv: lista de argumentos (sem nome do programa). Se ``None``,
            usa ``sys.argv``.

    Returns:
        Namespace com ``dir``, ``config`` e ``output_dir``.
    """
    parser = argparse.ArgumentParser(
        description="Processa em lote todos os CSVs MSC de um diretório.",
    )
    parser.add_argument(
        "--dir",
        required=True,
        dest="input_dir",
        help="Diretório contendo os arquivos CSV MSC a processar.",
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
    """Executa a CLI de batch com tratamento padronizado de erros.

    Args:
        argv: lista de argumentos (sem nome do programa).

    Returns:
        Código de saída Unix.
    """
    args = parse_args(argv)
    input_dir = Path(args.input_dir).expanduser().resolve()
    config_path = _resolve_config_path(args.config)

    logger: logging.Logger | None = None

    try:
        settings = load_settings(config_path)
        output_paths = _resolve_output_paths(settings, args.output_dir)
        logger = setup_logging(log_dir=output_paths.logs_dir)

        csv_files = _find_csv_files(input_dir)

        if not csv_files:
            _log_failure(logger, f"Nenhum arquivo CSV encontrado em: {input_dir}")
            return 2

        logger.info(
            "Iniciando batch: %d arquivo(s) CSV encontrado(s) em %s",
            len(csv_files),
            input_dir,
        )

        summary = _process_batch(
            csv_files=csv_files,
            settings=settings,
            output_paths=output_paths,
            logger=logger,
        )

        _log_batch_summary(summary, logger)
        return summary.exit_code

    except RankingMSCError as exc:
        _log_failure(logger, f"Falha ao executar batch: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        _log_failure(logger, f"Falha inesperada ao executar batch: {exc}")
        return 3


def _find_csv_files(directory: Path) -> list[Path]:
    """Retorna todos os arquivos *.csv no diretório (não recursivo), ordenados.

    Args:
        directory: diretório a ser varrido.

    Returns:
        Lista de Paths de arquivos *.csv, ordenada por nome.
    """
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.csv"))


def _process_batch(
    *,
    csv_files: list[Path],
    settings: Settings,
    output_paths: OutputPaths,
    logger: logging.Logger,
) -> BatchSummary:
    """Itera sobre todos os CSVs e executa o pipeline para cada um.

    Args:
        csv_files: lista de CSVs a processar.
        settings: configurações do projeto.
        output_paths: diretórios de saída resolvidos.
        logger: logger configurado.

    Returns:
        BatchSummary com resultados de todos os CSVs.
    """
    summary = BatchSummary()

    for idx, csv_path in enumerate(csv_files, start=1):
        logger.info(
            "Processando arquivo %d/%d: %s",
            idx,
            len(csv_files),
            csv_path.name,
        )
        result = _execute_single_csv(
            csv_path=csv_path,
            settings=settings,
            output_paths=output_paths,
            logger=logger,
        )
        summary.results.append(result)

    return summary


def _execute_single_csv(
    *,
    csv_path: Path,
    settings: Settings,
    output_paths: OutputPaths,
    logger: logging.Logger,
) -> CsvResult:
    """Executa o pipeline completo para um único CSV.

    Captura exceções para que erros num arquivo não interrompam o batch.

    Args:
        csv_path: caminho do CSV a processar.
        settings: configurações do projeto.
        output_paths: diretórios de saída resolvidos.
        logger: logger configurado.

    Returns:
        CsvResult com status final e métricas do processamento.
    """
    result = CsvResult(csv_path=csv_path, status="EXCECAO")

    try:
        raw_msc = read_msc_csv(csv_path)
        result.competencia = raw_msc.competencia
        result.siconfi = raw_msc.siconfi

        normalized_df = normalize_ic(raw_msc.df)

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
            usuario="batch",
            pre_pivot_issues=raw_msc.pre_pivot_issues,
        )

        engine_result = run_engine(normalized_df, context)

        write_snapshot_atomic(
            engine_result.pendencias,
            raw_msc.competencia,
            base_dir=output_paths.snapshots_dir / raw_msc.siconfi,
            label="resultado_regras",
        )
        export_issues_excel(
            engine_result.pendencias,
            raw_msc.competencia,
            output_dir=output_paths.reports_dir,
        )

        log_execucao(
            logger,
            execucao_id=context.execucao_id,
            competencia=context.competencia,
            status=engine_result.status,
            message="Batch: CSV processado",
            siconfi=context.siconfi,
            usuario=context.usuario,
        )

        result.status = engine_result.status
        result.pendencias = engine_result.total_pendencias
        return result

    except RankingMSCError as exc:
        result.error_message = str(exc)
        logger.error(
            "Erro ao processar %s: %s",
            csv_path.name,
            exc,
            extra={"csv_path": str(csv_path)},
        )
        return result
    except Exception as exc:  # noqa: BLE001
        result.error_message = f"Erro inesperado: {exc}"
        logger.error(
            "Erro inesperado ao processar %s: %s",
            csv_path.name,
            exc,
            exc_info=True,
            extra={"csv_path": str(csv_path)},
        )
        return result


def _resolve_config_path(config_arg: str | None) -> Path:
    """Resolve o caminho do arquivo de configuração.

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


def _log_batch_summary(summary: BatchSummary, logger: logging.Logger) -> None:
    """Registra resumo do batch ao final da execução.

    Args:
        summary: resultado consolidado do batch.
        logger: logger configurado.
    """
    logger.info(
        "Batch concluído — total=%d ok=%d parcial=%d falha=%d",
        summary.total,
        summary.succeeded,
        summary.partial,
        summary.failed,
    )
    for result in summary.results:
        if result.status in ("ERRO", "EXCECAO"):
            logger.warning(
                "  FALHOU: %s — %s",
                result.csv_path.name,
                result.error_message,
            )
        else:
            logger.info(
                "  %s: %s (competencia=%s siconfi=%s pendencias=%d)",
                result.status,
                result.csv_path.name,
                result.competencia,
                result.siconfi,
                result.pendencias,
            )


def _log_failure(logger: logging.Logger | None, message: str) -> None:
    """Registra falha de execução com fallback para stderr."""
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
