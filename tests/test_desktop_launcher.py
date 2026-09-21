"""Testes de desktop/launcher.py — arranque headless."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from desktop.launcher import main

from ranking_msc.outputs.logs import setup_logging


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


def test_headless_depois_setup_logging_ainda_anexa_handler_jsonl(
    tmp_path: Path, monkeypatch
) -> None:
    """Sequência real do app: depois de main(), setup_logging() ainda cria o JSONL.

    ``desktop.launcher.main()`` anexa seus próprios handlers ao logger
    ``"ranking_msc"`` antes de o servidor subir. Se ``setup_logging()`` (chamado sob
    demanda por ``app.api.deps.get_logger()`` na primeira requisição) tratasse "logger
    já tem handler" como "não faço nada", o arquivo ``ranking_msc.jsonl`` de auditoria
    nunca seria criado no aplicativo empacotado. Este teste reproduz exatamente essa
    sequência.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("RANKING_MSC_CONFIG", raising=False)

    assert main(["--headless"]) == 0

    logger = logging.getLogger("ranking_msc")
    handlers_antes = list(logger.handlers)

    logs_dir = tmp_path / "MCRA" / "data" / "logs"
    resultado = setup_logging(log_dir=logs_dir)
    resultado.info("linha de teste após arranque headless")

    jsonl_path = logs_dir / "ranking_msc.jsonl"
    try:
        assert jsonl_path.is_file()
        assert jsonl_path.stat().st_size > 0
    finally:
        # Não deixa o handler do JSONL grudado no logger compartilhado para o
        # resto da sessão de testes.
        for h in list(logger.handlers):
            if h not in handlers_antes:
                logger.removeHandler(h)
                h.close()
