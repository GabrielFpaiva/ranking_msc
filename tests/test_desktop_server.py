"""Testes de desktop/server.py — servidor uvicorn em thread."""

from __future__ import annotations

import logging
import socket

from desktop.server import ServidorLocal, porta_livre


def test_porta_livre_pode_ser_aberta() -> None:
    """A porta sorteada está realmente livre no momento da chamada."""
    porta = porta_livre()
    assert 1024 < porta < 65536
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", porta))


def test_servidor_sobe_responde_health_e_para() -> None:
    """Ciclo completo: iniciar, /api/health responder ok, parar."""
    import httpx

    servidor = ServidorLocal(porta_livre())
    servidor.iniciar()
    try:
        assert servidor.esperar_saude(timeout=30.0) is True
        resposta = httpx.get(f"{servidor.url}/api/health", timeout=5.0)
        assert resposta.status_code == 200
        assert resposta.json()["status"] == "ok"
    finally:
        servidor.parar()

    assert servidor.esperar_saude(timeout=2.0) is False


def test_iniciar_chamado_duas_vezes_levanta_erro() -> None:
    """Segunda chamada a iniciar() deve falhar com mensagem clara."""
    servidor = ServidorLocal(porta_livre())
    servidor.iniciar()
    try:
        with __import__("pytest").raises(RuntimeError, match="já foi iniciado"):
            servidor.iniciar()
    finally:
        servidor.parar()


def test_parar_com_thread_viva_loga_warning(caplog) -> None:  # type: ignore[no-untyped-def]
    """Se thread não morre no timeout, parar() loga warning."""
    import unittest.mock as mock

    servidor = ServidorLocal(porta_livre())
    servidor.iniciar()
    try:
        # Mock thread.join() para simular timeout (thread continua viva)
        with mock.patch.object(
            servidor._thread, "join", wraps=servidor._thread.join
        ):
            with mock.patch.object(
                servidor._thread, "is_alive", return_value=True
            ):
                with caplog.at_level(logging.WARNING):
                    servidor.parar()

        # Verificar que um warning foi gerado
        assert any(
            "não encerrou" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
    finally:
        # Cleanup: parar de verdade
        if servidor._server is not None:
            servidor._server.should_exit = True


def test_servidor_sobe_sem_stdout_nem_stderr(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No exe GUI do Windows (console=False) stdout e stderr são None; o servidor sobe igual."""
    import sys

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    servidor = ServidorLocal(porta_livre())
    try:
        servidor.iniciar()
        assert servidor.esperar_saude(timeout=30.0) is True
    finally:
        servidor.parar()
