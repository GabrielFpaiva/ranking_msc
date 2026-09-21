"""Testes de desktop/server.py — servidor uvicorn em thread."""

from __future__ import annotations

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
