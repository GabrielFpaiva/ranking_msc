"""Testes de desktop/launcher.py — arranque headless."""

from __future__ import annotations

import os
from pathlib import Path

from desktop.launcher import main


def test_headless_sobe_e_encerra_com_zero(tmp_path: Path, monkeypatch) -> None:
    """Em modo headless o launcher prepara tudo, confere a saúde e sai."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0

    assert (tmp_path / "MCRA" / "config" / "settings.yaml").is_file()
    assert os.environ["RANKING_MSC_CONFIG"] == str(
        tmp_path / "MCRA" / "config" / "settings.yaml"
    )
