"""
ranking_msc.outputs.snapshot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gravação atômica de snapshots em formato Parquet.

Cada competência processada gera um snapshot (foto do resultado) salvo
em ``data/snapshots/<competencia>/``. Isso permite:
    - Consultar resultados anteriores sem reprocessar.
    - Comparar evolução entre competências.
    - Alimentar dashboards de tendência.

Escrita atômica:
    Para evitar que um crash no meio da gravação deixe um snapshot
    corrompido, o fluxo deve ser:
        1. Gravar em arquivo temporário (mesmo diretório, extensão .tmp).
        2. Após gravação completa, renomear (atomic rename) para o nome final.
    No Linux, rename dentro do mesmo filesystem é atômico.

Concorrência:
    Se dois usuários processarem a mesma competência ao mesmo tempo,
    podemos ter conflito de escrita. Estratégias planejadas:
        - Opção A: lock por arquivo (.lock) — simples, bom para poucos usuários.
        - Opção B: semáforo no executor (ver SecuritySettings.max_concurrent_jobs).
    TODO: escolher e implementar a estratégia.
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
    """Grava snapshot Parquet de forma atômica.

    Args:
        df: DataFrame a ser salvo.
        competencia: "YYYY-MM" — usado para criar o subdiretório.
        base_dir: diretório raiz de snapshots.
        label: nome lógico do arquivo (ex: "resultado_regras", "msc_normalizado").

    Returns:
        Path do arquivo Parquet final gravado.

    Raises:
        SnapshotError: falha de I/O ou permissão.
        NotImplementedError: stub — lógica ainda não implementada.

    TODO (implementar):
        1. dest_dir = base_dir / competencia
        2. dest_dir.mkdir(parents=True, exist_ok=True)
        3. tmp_path = dest_dir / f"{label}.parquet.tmp"
        4. final_path = dest_dir / f"{label}.parquet"
        5. df.to_parquet(tmp_path, index=False)
        6. tmp_path.rename(final_path)  # atomic rename
        7. Retornar final_path
        — Em caso de erro: remover tmp_path e levantar SnapshotError.
    """
    raise NotImplementedError(
        "write_snapshot_atomic() ainda não implementado. "
        "Consulte os comentários para o fluxo de escrita atômica."
    )


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
        SnapshotError: se o arquivo não existir.
    """
    path = Path(base_dir) / competencia / f"{label}.parquet"
    if not path.exists():
        raise SnapshotError(f"Snapshot não encontrado: {path}")
    return pd.read_parquet(path)
