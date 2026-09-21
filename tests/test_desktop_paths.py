"""Testes de app/api/paths.py — raiz de recursos em modo normal e congelado."""

from __future__ import annotations

import sys
from pathlib import Path

from app.api.paths import is_frozen, resolve_root


def test_root_sem_bundle_aponta_para_a_raiz_do_repo() -> None:
    """Fora do PyInstaller, a raiz é a pasta que contém pyproject.toml."""
    assert (resolve_root() / "pyproject.toml").is_file()
    assert is_frozen() is False


def test_root_congelado_usa_meipass(tmp_path: Path, monkeypatch) -> None:
    """Com sys.frozen e sys._MEIPASS, a raiz é o diretório de extração."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resolve_root() == tmp_path
    assert is_frozen() is True
