"""
ranking_msc.outputs.snapshot
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gravação atômica de snapshots em formato Parquet.

Cada competência processada gera um snapshot (foto do resultado) salvo
em ``data/snapshots/<competencia>/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import SnapshotError, SnapshotNotFoundError

logger = logging.getLogger("ranking_msc")


def write_snapshot_atomic(
    df: pd.DataFrame,
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
    label: str = "resultado_regras",
) -> Path:
    """Grava snapshot Parquet de forma atômica.

    Args:
        df: DataFrame a ser salvo.
        competencia: "YYYY-MM" usado para criar o subdiretório.
        base_dir: diretório raiz de snapshots.
        label: nome lógico do arquivo (ex: "resultado_regras", "msc_normalizado").

    Returns:
        Path do arquivo Parquet final gravado.

    Raises:
        SnapshotError: falha de I/O ou permissão.
    """
    dest_dir = Path(base_dir) / competencia
    tmp_path = dest_dir / f"{label}.parquet.tmp"
    final_path = dest_dir / f"{label}.parquet"

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if tmp_path.exists():
            tmp_path.unlink()
        df.to_parquet(tmp_path, index=False)
        # replace no mesmo filesystem preserva atomicidade no rename final.
        tmp_path.replace(final_path)
    except OSError as exc:
        _remove_tmp_if_exists(tmp_path)
        raise SnapshotError(
            f"Falha ao gravar snapshot da competência {competencia} em {final_path}: {exc}"
        ) from exc

    logger.info(
        "Snapshot gravado: competência=%s label=%s path=%s (%d linhas)",
        competencia, label, final_path, len(df),
        extra={"competencia": competencia, "modulo": "snapshot"},
    )
    return final_path


def read_snapshot(
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
    label: str = "resultado_regras",
) -> pd.DataFrame:
    """Lê um snapshot Parquet existente.

    Returns:
        DataFrame carregado do Parquet.

    Raises:
        SnapshotNotFoundError: se o arquivo não existir em disco.
        SnapshotError: se houver falha de leitura (I/O, permissão, Parquet corrompido).
    """
    path = Path(base_dir) / competencia / f"{label}.parquet"
    if not path.exists():
        raise SnapshotNotFoundError(f"Snapshot não encontrado: {path}")

    try:
        df = pd.read_parquet(path)
    except OSError as exc:
        raise SnapshotError(
            f"Falha ao ler snapshot da competência {competencia}: {exc}"
        ) from exc

    logger.info(
        "Snapshot lido: competência=%s path=%s (%d linhas)",
        competencia, path, len(df),
        extra={"competencia": competencia, "modulo": "snapshot"},
    )
    return df


def _remove_tmp_if_exists(tmp_path: Path) -> None:
    """Remove arquivo temporário de snapshot quando existir."""
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        # Melhor esforço: erro original de gravação deve prevalecer.
        pass
