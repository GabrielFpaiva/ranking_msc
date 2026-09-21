#!/usr/bin/env python3
"""
desktop.launcher
~~~~~~~~~~~~~~~~

Ponto de entrada do aplicativo desktop.

A ordem importa: a pasta de dados e a config vêm primeiro, ``RANKING_MSC_CONFIG``
entra no ambiente antes de qualquer import da aplicação, e só então o servidor
sobe. O loader de configuração lê a variável no momento da carga; exportá-la
depois não tem efeito.

Uso:
    python -m desktop.launcher
    python -m desktop.launcher --headless   # sem janela, para smoke test
"""

from __future__ import annotations

import argparse
import logging
import os

from app.api.paths import resolve_root

from desktop.bootstrap import data_home, preparar_config
from desktop.server import ServidorLocal, porta_livre

logger = logging.getLogger("ranking_msc")

_TITULO = "MCRA PMJP — Validação da Matriz de Saldos Contábeis"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="MCRA PMJP — aplicativo desktop.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="sobe o servidor, confere a saúde e sai, sem abrir a janela",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Prepara o ambiente, sobe o servidor e abre a janela.

    Returns:
        0 em caso de sucesso, 1 se o servidor não respondeu a tempo.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    config_path = preparar_config(data_home(), root=resolve_root())
    os.environ["RANKING_MSC_CONFIG"] = str(config_path)

    servidor = ServidorLocal(porta_livre())
    servidor.iniciar()
    try:
        if not servidor.esperar_saude():
            logger.error("O servidor local não respondeu. Consulte o log da aplicação.")
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
