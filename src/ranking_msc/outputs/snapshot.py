"""
ranking_msc.outputs.snapshot
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gravação atômica de snapshots em formato Parquet.

Cada competência processada gera um snapshot (foto do resultado) salvo
em ``data/snapshots/<competencia>/``.
"""

from __future__ import annotations

import json
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


def write_scoring_metadata(
    rule_ids: list[str],
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
) -> Path:
    """Persiste a lista de regras executadas junto ao snapshot de resultado_regras.

    Garante estabilidade histórica do score: ao recalcular períodos anteriores
    em compare_periods(), usa as regras que *foram* executadas naquele período,
    não as atualmente habilitadas em settings.rules.enabled.

    Args:
        rule_ids: lista de rule_id executadas no pipeline para esta competência.
        competencia: "YYYY-MM" — subdiretório de destino.
        base_dir: diretório raiz de snapshots (mesmo usado por write_snapshot_atomic).

    Returns:
        Path do arquivo JSON gravado.

    Raises:
        SnapshotError: falha de I/O ou permissão.
    """
    dest_dir = Path(base_dir) / competencia
    tmp_path = dest_dir / "scoring_metadata.json.tmp"
    final_path = dest_dir / "scoring_metadata.json"

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps({"executed_rule_ids": sorted(rule_ids)}, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(final_path)
    except OSError as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise SnapshotError(
            f"Falha ao gravar metadados de scoring para competência {competencia}: {exc}"
        ) from exc

    logger.info(
        "Metadados de scoring gravados: competência=%s regras=%d path=%s",
        competencia,
        len(rule_ids),
        final_path,
        extra={"competencia": competencia, "modulo": "snapshot"},
    )
    return final_path


def read_scoring_metadata(
    competencia: str,
    *,
    base_dir: str | Path = "data/snapshots",
) -> list[str] | None:
    """Lê a lista de regras executadas do metadado persistido para uma competência.

    Args:
        competencia: "YYYY-MM" — subdiretório do snapshot.
        base_dir: diretório raiz de snapshots.

    Returns:
        Lista de rule_id persistidos, ou ``None`` se o arquivo não existir ou
        estiver corrompido (sem levantar exceção — o chamador decide o fallback).
    """
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


def _remove_tmp_if_exists(tmp_path: Path) -> None:
    """Remove arquivo temporário de snapshot quando existir."""
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        # Melhor esforço: erro original de gravação deve prevalecer.
        pass
