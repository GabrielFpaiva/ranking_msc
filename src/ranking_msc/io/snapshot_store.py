"""Leitura de snapshots históricos persistidos em disco."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from pyarrow.lib import ArrowException, ArrowIOError

from ranking_msc.exceptions import SnapshotCorruptError, SnapshotError, SnapshotNotFoundError

logger = logging.getLogger("ranking_msc")


def read_snapshot(
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
    label: str = "resultado_regras",
) -> pd.DataFrame:
    """Lê um snapshot Parquet existente."""
    path = Path(base_dir) / competencia / f"{label}.parquet"
    if not path.exists():
        raise SnapshotNotFoundError(f"Snapshot não encontrado: {path}")

    try:
        df = pd.read_parquet(path)
    except (ArrowException, ArrowIOError) as exc:
        raise SnapshotCorruptError(
            f"Snapshot corrompido para competência {competencia}: {exc}"
        ) from exc
    except Exception as exc:
        raise SnapshotError(
            f"Falha ao ler snapshot da competência {competencia}: {exc}"
        ) from exc

    logger.info(
        "Snapshot lido: competência=%s path=%s (%d linhas)",
        competencia, path, len(df),
        extra={"competencia": competencia, "modulo": "snapshot"},
    )
    return df


def read_scoring_metadata(
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
) -> list[str] | None:
    """Lê a lista de regras executadas do metadado persistido para uma competência."""
    path = Path(base_dir) / competencia / "scoring_metadata.json"
    if not path.exists():
        return None

    def _warn_corrupt(reason: str) -> None:
        logger.warning(
            "Metadados de scoring inválidos para competência %s em %s — %s. "
            "Tratando como ausentes.",
            competencia,
            path,
            reason,
            extra={"competencia": competencia, "modulo": "snapshot"},
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _warn_corrupt("arquivo corrompido ou ilegível")
        return None

    if not isinstance(data, dict):
        _warn_corrupt("payload não é um objeto JSON")
        return None

    ids = data.get("executed_rule_ids")
    if not isinstance(ids, list):
        _warn_corrupt("'executed_rule_ids' ausente ou não é uma lista")
        return None

    if not all(isinstance(item, str) for item in ids):
        _warn_corrupt("'executed_rule_ids' contém itens não-string")
        return None

    return ids
