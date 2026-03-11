"""
ranking_msc.outputs.snapshot
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gravacao atomica de snapshots em formato Parquet.

Cada competencia processada gera um snapshot (foto do resultado) salvo
em ``data/snapshots/<competencia>/``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import SnapshotError


def write_snapshot_atomic(
    df: pd.DataFrame,
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
    label: str = "resultado_regras",
) -> Path:
    """Grava snapshot Parquet de forma atomica.

    Args:
        df: DataFrame a ser salvo.
        competencia: "YYYY-MM" usado para criar o subdiretorio.
        base_dir: diretorio raiz de snapshots.
        label: nome logico do arquivo (ex: "resultado_regras", "msc_normalizado").

    Returns:
        Path do arquivo Parquet final gravado.

    Raises:
        SnapshotError: falha de I/O ou permissao.
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
        return final_path
    except OSError as exc:
        _remove_tmp_if_exists(tmp_path)
        raise SnapshotError(
            f"Falha ao gravar snapshot da competencia {competencia} em {final_path}: {exc}"
        ) from exc


def read_snapshot(
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
    label: str = "resultado_regras",
) -> pd.DataFrame:
    """Le um snapshot Parquet existente.

    Returns:
        DataFrame carregado do Parquet.

    Raises:
        SnapshotError: se o arquivo nao existir ou houver falha de leitura.
    """
    path = Path(base_dir) / competencia / f"{label}.parquet"
    if not path.exists():
        raise SnapshotError(f"Snapshot nao encontrado: {path}")

    try:
        return pd.read_parquet(path)
    except OSError as exc:
        raise SnapshotError(f"Falha ao ler snapshot da competencia {competencia}: {exc}") from exc


def _remove_tmp_if_exists(tmp_path: Path) -> None:
    """Remove arquivo temporario de snapshot quando existir."""
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        # Melhor esforco: erro original de gravacao deve prevalecer.
        pass
