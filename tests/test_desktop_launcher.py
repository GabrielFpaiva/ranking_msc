"""Testes de desktop/launcher.py — arranque headless."""

from __future__ import annotations

import logging
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

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    assert log_path.is_file()
    assert log_path.stat().st_size > 0


def test_headless_duas_vezes_nao_duplica_handlers_nem_linhas(
    tmp_path: Path, monkeypatch
) -> None:
    """Chamar main() duas vezes no mesmo processo não duplica handlers nem linhas do log."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0
    assert main(["--headless"]) == 0

    log_path = tmp_path / "MCRA" / "data" / "logs" / "desktop.log"
    log_path_absoluto = os.path.abspath(str(log_path))
    conteudo = log_path.read_text(encoding="utf-8")

    # Duas execuções bem-sucedidas devem gerar exatamente duas ocorrências de
    # cada marco de arranque/parada — se um handler tivesse sido duplicado,
    # cada chamada teria escrito a mensagem duas vezes no arquivo.
    assert conteudo.count("Servidor local iniciado em") == 2
    assert conteudo.count("Servidor local encerrado.") == 2

    logger = logging.getLogger("ranking_msc")
    handlers_deste_arquivo = [
        h
        for h in logger.handlers
        if isinstance(h, logging.FileHandler) and h.baseFilename == log_path_absoluto
    ]
    assert len(handlers_deste_arquivo) == 1
