"""
tests/test_snapshot.py
~~~~~~~~~~~~~~~~~~~~~

Testes de snapshots Parquet em ``ranking_msc.outputs.snapshot``.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ranking_msc.exceptions import SnapshotError
from ranking_msc.outputs.snapshot import read_snapshot, write_snapshot_atomic


@pytest.fixture
def snapshot_df() -> pd.DataFrame:
    """Cria DataFrame sintetico para round-trip de snapshot."""
    return pd.DataFrame(
        [
            {
                "regra_id": "R082",
                "severidade": "ERRO",
                "descricao": "Debito diferente de credito",
                "valor_encontrado": "10",
            },
            {
                "regra_id": "R083",
                "severidade": "ALERTA",
                "descricao": "Variacao acima do limite",
                "valor_encontrado": "130",
            },
        ]
    )


@pytest.fixture
def local_snapshot_dir() -> Iterator[Path]:
    """Cria diretorio temporario local para snapshots de teste."""
    created = Path.cwd() / ".snapshot_test_tmp" / uuid.uuid4().hex
    created.mkdir(parents=True, exist_ok=True)
    try:
        yield created
    finally:
        shutil.rmtree(created, ignore_errors=True)


def test_write_snapshot_atomic_grava_parquet_sem_tmp_residual(
    local_snapshot_dir: Path,
    snapshot_df: pd.DataFrame,
) -> None:
    """Grava snapshot em parquet e nao deixa arquivo temporario residual."""
    output = write_snapshot_atomic(
        snapshot_df,
        competencia="2024-01",
        base_dir=local_snapshot_dir,
        label="resultado_regras",
    )

    expected_dir = local_snapshot_dir / "2024-01"
    expected_tmp = expected_dir / "resultado_regras.parquet.tmp"

    assert output == expected_dir / "resultado_regras.parquet"
    assert output.exists()
    assert not expected_tmp.exists()


def test_read_snapshot_retorna_dataframe_igual_ao_gravado(
    local_snapshot_dir: Path,
    snapshot_df: pd.DataFrame,
) -> None:
    """Le snapshot gravado e retorna DataFrame equivalente ao original."""
    write_snapshot_atomic(
        snapshot_df,
        competencia="2024-01",
        base_dir=local_snapshot_dir,
        label="resultado_regras",
    )

    loaded = read_snapshot(
        competencia="2024-01",
        base_dir=local_snapshot_dir,
        label="resultado_regras",
    )

    pd.testing.assert_frame_equal(loaded, snapshot_df)


def test_write_snapshot_atomic_sem_permissao_levanta_snapshoterror(
    local_snapshot_dir: Path,
    snapshot_df: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Converte erro de permissao em SnapshotError."""

    def _forbidden_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("Sem permissao para criar diretorio")

    monkeypatch.setattr(Path, "mkdir", _forbidden_mkdir)

    with pytest.raises(SnapshotError, match="Falha ao gravar snapshot"):
        write_snapshot_atomic(
            snapshot_df,
            competencia="2024-01",
            base_dir=local_snapshot_dir,
            label="resultado_regras",
        )


def test_write_snapshot_atomic_remove_tmp_quando_gravacao_falha(
    local_snapshot_dir: Path,
    snapshot_df: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove arquivo .tmp caso haja falha durante escrita do parquet."""

    def _broken_to_parquet(self: pd.DataFrame, path: str | Path, index: bool = False) -> None:
        del index
        tmp_path = Path(path)
        tmp_path.write_text("parcial", encoding="utf-8")
        raise OSError("falha de I/O durante to_parquet")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _broken_to_parquet)

    with pytest.raises(SnapshotError, match="Falha ao gravar snapshot"):
        write_snapshot_atomic(
            snapshot_df,
            competencia="2024-01",
            base_dir=local_snapshot_dir,
            label="resultado_regras",
        )

    assert not (local_snapshot_dir / "2024-01" / "resultado_regras.parquet.tmp").exists()


def test_read_snapshot_ausente_levanta_snapshoterror(local_snapshot_dir: Path) -> None:
    """Levanta SnapshotError quando arquivo parquet nao existe."""
    with pytest.raises(SnapshotError, match="Snapshot não encontrado"):
        read_snapshot(
            competencia="2024-01",
            base_dir=local_snapshot_dir,
            label="resultado_regras",
        )


def test_read_snapshot_corrompido_levanta_snapshoterror(local_snapshot_dir: Path) -> None:
    """Converte parquet invalido em SnapshotError no boundary de leitura."""
    target_dir = local_snapshot_dir / "2024-01"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "resultado_regras.parquet").write_text("nao-e-parquet", encoding="utf-8")

    with pytest.raises(SnapshotError, match="Falha ao ler snapshot da competência 2024-01"):
        read_snapshot(
            competencia="2024-01",
            base_dir=local_snapshot_dir,
            label="resultado_regras",
        )
