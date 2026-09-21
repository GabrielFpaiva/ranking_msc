#!/usr/bin/env python3
"""
desktop.launcher
~~~~~~~~~~~~~~~~

Ponto de entrada do aplicativo desktop.

A ordem importa: o logging vem primeiro — antes de qualquer coisa que possa
falhar, inclusive ``preparar_config()`` — porque no subsistema GUI do Windows
(``console=False`` no ``mcra.spec``) não existe console anexado, e sem um
arquivo de log uma falha no arranque não deixa rastro nenhum. Depois vem a
pasta de dados e a config, ``RANKING_MSC_CONFIG`` entra no ambiente antes de
qualquer import da aplicação, e só então o servidor sobe. O loader de
configuração lê a variável no momento da carga; exportá-la depois não tem
efeito.

Uso:
    python -m desktop.launcher
    python -m desktop.launcher --headless   # sem janela, para smoke test
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from app.api.paths import resolve_root

from desktop.bootstrap import data_home, preparar_config
from desktop.server import ServidorLocal, porta_livre

logger = logging.getLogger("ranking_msc")

_TITULO = "MCRA PMJP — Validação da Matriz de Saldos Contábeis"
_NOME_ARQUIVO_LOG = "desktop.log"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="MCRA PMJP — aplicativo desktop.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="sobe o servidor, confere a saúde e sai, sem abrir a janela",
    )
    return parser.parse_args(argv)


def _configurar_logging(home: Path) -> Path:
    """Liga o logger do projeto a um arquivo em ``home`` e ao console.

    O arquivo fica em ``home / "data" / "logs" / "desktop.log"`` e é criado
    antes de qualquer outra etapa do arranque — inclusive antes de
    ``preparar_config()`` — porque uma falha nessa etapa (template ausente no
    pacote, por exemplo) é justamente um dos casos que hoje somem em silêncio
    no subsistema GUI do Windows, que não tem console anexado.

    Idempotente: chamar de novo no mesmo processo, com o mesmo ``home``, não
    duplica handlers nem duplica linhas escritas no arquivo.

    Args:
        home: pasta de dados do usuário (ver ``data_home()``).

    Returns:
        Caminho do arquivo de log.
    """
    log_dir = home / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _NOME_ARQUIVO_LOG

    logger.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    log_path_absoluto = os.path.abspath(str(log_path))
    tem_handler_arquivo = any(
        isinstance(h, logging.FileHandler) and h.baseFilename == log_path_absoluto
        for h in logger.handlers
    )
    if not tem_handler_arquivo:
        handler_arquivo = logging.FileHandler(log_path, encoding="utf-8")
        handler_arquivo.setFormatter(formato)
        logger.addHandler(handler_arquivo)

    tem_handler_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not tem_handler_console:
        handler_console = logging.StreamHandler()
        handler_console.setFormatter(formato)
        logger.addHandler(handler_console)

    return log_path


def main(argv: list[str] | None = None) -> int:
    """Prepara o ambiente, sobe o servidor e abre a janela.

    Returns:
        0 em caso de sucesso, 1 se o servidor não respondeu a tempo.
    """
    args = parse_args(argv)

    home = data_home()
    log_path = _configurar_logging(home)

    config_path = preparar_config(home, root=resolve_root())
    os.environ["RANKING_MSC_CONFIG"] = str(config_path)

    servidor = ServidorLocal(porta_livre())
    servidor.iniciar()
    try:
        if not servidor.esperar_saude():
            logger.error("O servidor local não respondeu. Consulte o log em %s", log_path)
            return 1
        if args.headless:
            return 0

        import webview

        webview.create_window(_TITULO, servidor.url, width=1440, height=900)
        webview.start()
        return 0
    finally:
        servidor.parar()


if __name__ == "__main__":
    raise SystemExit(main())
