"""
ranking_msc.engine.locks
~~~~~~~~~~~~~~~~~~~~~~~~

File-based execution locks for concurrent API runs.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class ExecutionLockError(RuntimeError):
    """Base error for execution lock failures."""


class ExecutionLockExistsError(ExecutionLockError):
    """Raised when a lock already exists for the same execution namespace."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Execution lock already exists: {path}")


@dataclass(frozen=True)
class ExecutionLock:
    """Handle for a lock acquired by one execution."""

    path: Path
    token: str
    siconfi: str
    competencia: str
    usuario: str


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def acquire_execution_lock(
    locks_dir: str | Path,
    *,
    siconfi: str,
    competencia: str,
    usuario: str,
) -> ExecutionLock:
    """Acquire an exclusive lock for one ``siconfi`` + ``competencia`` pair.

    The lock is intentionally scoped to the persisted snapshot namespace. It
    prevents concurrent writes to deterministic files such as
    ``resultado_regras.parquet`` and ``pendencias_<siconfi>_<competencia>.xlsx``.
    """

    root = Path(locks_dir)
    root.mkdir(parents=True, exist_ok=True)

    token = str(uuid.uuid4())
    path = root / f"{_safe_part(siconfi)}__{_safe_part(competencia)}.lock"
    payload = {
        "token": token,
        "siconfi": siconfi,
        "competencia": competencia,
        "usuario": usuario,
        "created_at": datetime.now(UTC).isoformat(),
    }

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(path, flags)
    except FileExistsError as exc:
        raise ExecutionLockExistsError(path) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True, indent=2)
    except Exception:
        try:
            path.unlink()
        finally:
            raise

    return ExecutionLock(
        path=path,
        token=token,
        siconfi=siconfi,
        competencia=competencia,
        usuario=usuario,
    )


def release_execution_lock(lock: ExecutionLock) -> None:
    """Release ``lock`` if it still belongs to the current execution."""

    try:
        data = json.loads(lock.path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return

    if isinstance(data, dict) and data.get("token") == lock.token:
        try:
            lock.path.unlink()
        except FileNotFoundError:
            return


def _safe_part(value: str) -> str:
    cleaned = _SAFE_CHARS.sub("_", value.strip())
    return cleaned or "unknown"
