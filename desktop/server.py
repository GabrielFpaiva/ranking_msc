"""
desktop.server
~~~~~~~~~~~~~~

Sobe a API FastAPI num servidor uvicorn local, dentro de uma thread, para que a
janela do aplicativo possa apontar para ela.

O bind é sempre ``127.0.0.1``: evita o alerta de firewall do Windows e mantém o
aplicativo inacessível pela rede. A porta é sorteada pelo sistema operacional em
vez de fixa, porque a máquina do usuário pode já ter algo na 8000.
"""

from __future__ import annotations

import logging
import socket
import threading
import time

import httpx
import uvicorn

logger = logging.getLogger("ranking_msc")

_HOST = "127.0.0.1"


def porta_livre() -> int:
    """Pede ao sistema operacional uma porta TCP livre em loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((_HOST, 0))
        return int(sock.getsockname()[1])


class ServidorLocal:
    """Servidor uvicorn em thread, com arranque e parada explícitos."""

    def __init__(self, porta: int) -> None:
        """Prepara o servidor sem iniciá-lo.

        Args:
            porta: porta TCP em loopback. Use ``porta_livre()``.
        """
        self.porta: int = porta
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None

    @property
    def url(self) -> str:
        """URL base do servidor."""
        return f"http://{_HOST}:{self.porta}"

    def iniciar(self) -> None:
        """Sobe o servidor numa thread daemon.

        A aplicação é importada aqui, e não no topo do módulo, para que
        ``RANKING_MSC_CONFIG`` já esteja no ambiente quando o loader de
        configuração rodar.

        Raises:
            RuntimeError: se o servidor já foi iniciado.
        """
        if self._server is not None or self._thread is not None:
            raise RuntimeError("O servidor já foi iniciado. Crie uma nova instância.")

        from app.api.main import app

        # log_config=None: o dictConfig padrão do uvicorn chama sys.stdout.isatty(), e no
        # exe GUI do Windows (console=False) sys.stdout é None — o Config estouraria com
        # "Unable to configure formatter 'default'". Os handlers vêm do launcher.
        config = uvicorn.Config(
            app, host=_HOST, port=self.porta, log_level="warning", log_config=None
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        logger.info("Servidor local iniciado em %s", self.url)

    def esperar_saude(self, timeout: float = 30.0) -> bool:
        """Aguarda ``/api/health`` responder.

        Desiste na hora se a thread do servidor já morreu (porta ocupada, falha
        no startup da aplicação): com o timeout longo do launcher, esperar o
        prazo inteiro só atrasaria o aviso de erro.

        Args:
            timeout: segundos de espera antes de desistir.

        Returns:
            True se respondeu 200 dentro do prazo.
        """
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            if self._thread is not None and not self._thread.is_alive():
                return False
            try:
                resposta = httpx.get(f"{self.url}/api/health", timeout=2.0)
                if resposta.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        return False

    def parar(self) -> None:
        """Pede o encerramento do uvicorn e aguarda a thread terminar."""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            if self._thread.is_alive():
                logger.warning(
                    "Thread do servidor em %s não encerrou no timeout de 10s.",
                    self.url,
                )
                return
        logger.info("Servidor local encerrado.")
