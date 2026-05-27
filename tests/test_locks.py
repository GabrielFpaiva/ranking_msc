from __future__ import annotations

from pathlib import Path

import pytest

from ranking_msc.engine.locks import (
    ExecutionLockExistsError,
    acquire_execution_lock,
    release_execution_lock,
)


def test_acquire_execution_lock_cria_arquivo(tmp_path: Path) -> None:
    lock = acquire_execution_lock(
        tmp_path,
        siconfi="2507507EX",
        competencia="2025-11",
        usuario="alice",
    )

    assert lock.path.exists()
    assert lock.token


def test_acquire_execution_lock_rejeita_mesmo_namespace(tmp_path: Path) -> None:
    lock = acquire_execution_lock(
        tmp_path,
        siconfi="2507507EX",
        competencia="2025-11",
        usuario="alice",
    )

    with pytest.raises(ExecutionLockExistsError):
        acquire_execution_lock(
            tmp_path,
            siconfi="2507507EX",
            competencia="2025-11",
            usuario="bob",
        )

    release_execution_lock(lock)


def test_release_execution_lock_remove_arquivo(tmp_path: Path) -> None:
    lock = acquire_execution_lock(
        tmp_path,
        siconfi="2507507EX",
        competencia="2025-11",
        usuario="alice",
    )

    release_execution_lock(lock)

    assert not lock.path.exists()
