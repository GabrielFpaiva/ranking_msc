"""
tests/test_siconfi_client.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes do cliente da API do Siconfi.

Rodam sem rede: usam ``httpx.MockTransport`` alimentado por uma resposta REAL
capturada do Tesouro (``tests/fixtures/siconfi_extrato_jp_2025.json``), para
exercitar o formato verdadeiro em vez de um JSON inventado.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ranking_msc.siconfi.client import SiconfiIndisponivelError, buscar_extrato

FIXTURE = Path(__file__).parent / "fixtures" / "siconfi_extrato_jp_2025.json"


def test_busca_devolve_itens_da_api() -> None:
    """Resposta única (sem paginação) devolve todos os itens."""
    payload = json.loads(FIXTURE.read_text())
    payload["hasMore"] = False

    def handler(request: httpx.Request) -> httpx.Response:
        assert "extrato_entregas" in str(request.url)
        assert request.url.params["id_ente"] == "2507507"
        assert request.url.params["an_referencia"] == "2025"
        return httpx.Response(200, json=payload)

    itens = buscar_extrato(2507507, 2025, transport=httpx.MockTransport(handler))

    assert len(itens) == len(payload["items"])
    assert itens[0]["cod_ibge"] == 2507507


def test_segue_paginacao_ate_o_fim() -> None:
    """hasMore=True faz o cliente pedir a próxima página somando o limit."""
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", 0))
        chamadas.append(offset)
        if offset == 0:
            return httpx.Response(
                200, json={"items": [{"a": 1}], "hasMore": True, "limit": 25}
            )
        return httpx.Response(
            200, json={"items": [{"a": 2}], "hasMore": False, "limit": 25}
        )

    itens = buscar_extrato(2507507, 2025, transport=httpx.MockTransport(handler))

    assert chamadas == [0, 25]
    assert itens == [{"a": 1}, {"a": 2}]


def test_erro_http_vira_excecao_do_dominio() -> None:
    """500 do Tesouro não vaza httpx para as camadas de cima."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="erro interno")

    with pytest.raises(SiconfiIndisponivelError):
        buscar_extrato(2507507, 2025, transport=httpx.MockTransport(handler))


def test_falha_de_rede_vira_excecao_do_dominio() -> None:
    """Timeout/DNS/firewall também viram a exceção do domínio."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host")

    with pytest.raises(SiconfiIndisponivelError):
        buscar_extrato(2507507, 2025, transport=httpx.MockTransport(handler))


def test_resposta_sem_items_nao_quebra() -> None:
    """Payload inesperado devolve lista vazia em vez de KeyError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hasMore": False})

    assert buscar_extrato(2507507, 2025, transport=httpx.MockTransport(handler)) == []
