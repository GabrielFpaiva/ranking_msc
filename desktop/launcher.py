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

Qualquer exceção entre a preparação da config e o arranque do servidor —
``ImportError`` de ``hiddenimport`` faltando no PyInstaller, ``ConfigError``
de template ausente no pacote — é capturada em ``main()``, registrada com
traceback completo em ``desktop.log`` e faz o processo sair com código 1, em
vez de estourar sem deixar rastro no subsistema GUI do Windows. Em modo janela
no Windows, a pessoa ainda recebe uma caixa de mensagem com o caminho do log.

Uso:
    python -m desktop.launcher
    python -m desktop.launcher --headless   # sem janela, para smoke test
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
from pathlib import Path

from app.api.paths import resolve_root

from desktop.bootstrap import data_home, preparar_config
from desktop.server import ServidorLocal, porta_livre

logger = logging.getLogger("ranking_msc")

_TITULO = "MCRA PMJP — Validação da Matriz de Saldos Contábeis"
_NOME_ARQUIVO_LOG = "desktop.log"
# Primeira abertura com antivírus corporativo varrendo ~350 MB de instalação
# passa fácil de 30 s; 120 s evita dar "falhou" para quem só precisava esperar.
_TIMEOUT_SAUDE_S = 120.0
# Loggers de terceiros que também vão para o desktop.log. "uvicorn" cobre
# "uvicorn.error" (ConfigError no arranque, exceção de rota) por propagação;
# anexar aos dois gravaria cada linha duas vezes.
_LOGGERS_EXTERNOS = ("uvicorn",)
_MB_ICONERROR = 0x10


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="MCRA PMJP — aplicativo desktop.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="sobe o servidor, confere a saúde e sai, sem abrir a janela",
    )
    return parser.parse_args(argv)


def _eh_windows() -> bool:
    """Diz se o processo roda no Windows (isolado para os testes)."""
    return sys.platform == "win32"


def _avisar_falha(log_path: Path) -> None:
    """Mostra uma caixa de erro nativa do Windows apontando para o log.

    Sem console no subsistema GUI, a caixa é o único sinal visível de que o
    aplicativo não abriu. Fora do Windows não faz nada, e nenhuma falha ao
    mostrar a caixa pode escapar daqui.
    """
    if not _eh_windows():
        return
    mensagem = (
        "O MCRA PMJP não conseguiu abrir.\n\n"
        "Envie ao suporte o arquivo de log:\n"
        f"{log_path}"
    )
    try:
        ctypes.windll.user32.MessageBoxW(None, mensagem, _TITULO, _MB_ICONERROR)
    except Exception:
        logger.warning("Não foi possível mostrar a caixa de erro.", exc_info=True)


def _configurar_logging(home: Path) -> Path:
    """Liga o logger do projeto a um arquivo em ``home`` e ao console.

    O arquivo fica em ``home / "data" / "logs" / "desktop.log"`` e é criado
    antes de qualquer outra etapa do arranque — inclusive antes de
    ``preparar_config()`` — porque uma falha nessa etapa (template ausente no
    pacote, por exemplo) é justamente um dos casos que hoje somem em silêncio
    no subsistema GUI do Windows, que não tem console anexado.

    O mesmo handler de arquivo é anexado ao logger ``uvicorn`` (pai de
    ``uvicorn.error``), para que erro de arranque do servidor e exceção de
    rota também cheguem ao ``desktop.log``.

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
    handler_arquivo = next(
        (
            h
            for h in logger.handlers
            if isinstance(h, logging.FileHandler) and h.baseFilename == log_path_absoluto
        ),
        None,
    )
    if handler_arquivo is None:
        handler_arquivo = logging.FileHandler(log_path, encoding="utf-8")
        handler_arquivo.setFormatter(formato)
        logger.addHandler(handler_arquivo)

    for nome in _LOGGERS_EXTERNOS:
        externo = logging.getLogger(nome)
        if handler_arquivo not in externo.handlers:
            externo.addHandler(handler_arquivo)

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

    Qualquer exceção entre a configuração do log e o fim desta função é
    capturada, registrada em ``desktop.log`` com o traceback completo (via
    ``logger.exception``) e faz a função devolver 1 — sem isso, uma falha no
    subsistema GUI do Windows (``console=False`` no ``mcra.spec``, sem console
    anexado) não deixaria rastro nenhum. ``KeyboardInterrupt`` e ``SystemExit``
    continuam se propagando normalmente, sem passar por aqui.

    Em modo janela (sem ``--headless``), devolver 1 também mostra a caixa de
    erro do Windows com o caminho do log (ver ``_avisar_falha``).

    Returns:
        0 em caso de sucesso, 1 se a preparação da config, o arranque do
        servidor, a checagem de saúde ou a abertura da janela falharem.
    """
    args = parse_args(argv)

    home = data_home()
    log_path = _configurar_logging(home)

    codigo = 1
    servidor: ServidorLocal | None = None
    etapa = "preparação da configuração"
    try:
        config_path = preparar_config(home, root=resolve_root())
        os.environ["RANKING_MSC_CONFIG"] = str(config_path)

        etapa = "arranque do servidor local"
        servidor = ServidorLocal(porta_livre())
        servidor.iniciar()

        if not servidor.esperar_saude(timeout=_TIMEOUT_SAUDE_S):
            logger.error("O servidor local não respondeu. Consulte o log em %s", log_path)
        elif args.headless:
            codigo = 0
        else:
            etapa = "abertura da janela"
            import webview

            webview.create_window(_TITULO, servidor.url, width=1440, height=900)
            webview.start()
            codigo = 0
    except Exception:
        logger.exception("Falha na etapa de %s. Consulte o log em %s", etapa, log_path)
        codigo = 1
    finally:
        if servidor is not None:
            servidor.parar()

    if codigo != 0 and not args.headless:
        _avisar_falha(log_path)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
