"""Helpers compartilhados entre os scripts CLI do Ranking MSC.

Centraliza lógica duplicada de resolução de caminhos, diretórios de saída
e tratamento de falhas presente em run_pipeline.py, run_batch.py e
compare_periods.py.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.config.settings import Settings  # noqa: E402


@dataclass(frozen=True)
class OutputPaths:
    """Diretórios de saída usados pelas execuções CLI."""

    snapshots_dir: Path
    reports_dir: Path
    logs_dir: Path


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


def _log_failure(logger: logging.Logger | None, message: str) -> None:
    """Registra falha de execução com fallback de logging para stderr.

    Inclui traceback apenas quando há uma exceção ativa — evita ruído
    ``NoneType: None`` em caminhos de falha sem exceção real.
    """
    exc_info = sys.exc_info()[0] is not None
    if logger is not None:
        logger.error(message, exc_info=exc_info)
        return

    logging.basicConfig(
        level=logging.ERROR,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    logging.getLogger("ranking_msc").error(message, exc_info=exc_info)
