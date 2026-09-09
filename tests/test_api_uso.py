"""
Testes das rotas de tempo de uso (app/api/routes/uso.py).

A fixture de sessão _bypass_auth_for_api_tests (tests/conftest.py) substitui
get_current_user por "test-user" — por isso nenhum teste aqui monta um JWT.
"""

from __future__ import annotations

import pytest
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _estado_limpo() -> None:
    """Zera acumulador, cache e arquivos entre testes.

    O acumulador e o cache são globais ao processo, e o diretório de uso é
    compartilhado pela fixture de sessão _hermetic_settings. Sem esta limpeza,
    o que um teste grava vaza para o próximo e as asserções de total viram
    dependentes da ordem de execução.
    """
    from app.api.deps import absolute_uso_dir
    from app.api.uso_store import ACUMULADOR, limpar_cache

    ACUMULADOR.drenar()
    limpar_cache()

    uso_dir = absolute_uso_dir()
    if uso_dir.is_dir():
        for arquivo in uso_dir.iterdir():
            if arquivo.is_file():
                arquivo.unlink()


class TestHeartbeat:
    def test_heartbeat_valido_retorna_204(self) -> None:
        """Batida bem formada é aceita sem corpo de resposta."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/pendencias", "aberto_s": 60, "ativo_s": 45},
        )
        assert resposta.status_code == 204

    def test_heartbeat_alimenta_o_acumulador(self) -> None:
        """O que entra pela rota aparece no buffer, atrelado ao usuário do token."""
        from app.api.uso_store import ACUMULADOR

        client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 60, "ativo_s": 60},
        )
        buffer = ACUMULADOR.espiar()
        assert len(buffer) == 1
        chave = next(iter(buffer))
        assert chave.usuario == "test-user"
        assert chave.rota == "/caixa"

    def test_rota_desconhecida_e_rejeitada(self) -> None:
        """Allowlist: o cliente não escreve rota arbitrária no JSONL."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/../../etc/passwd", "aberto_s": 60, "ativo_s": 60},
        )
        assert resposta.status_code == 422

    def test_segundos_acima_do_teto_sao_rejeitados(self) -> None:
        """Ninguém se dá 40 horas de uso com um curl."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": 144000, "ativo_s": 144000},
        )
        assert resposta.status_code == 422

    def test_segundos_negativos_sao_rejeitados(self) -> None:
        """Delta negativo faria o contador andar para trás."""
        resposta = client.post(
            "/api/uso/heartbeat",
            json={"rota": "/caixa", "aberto_s": -60, "ativo_s": -60},
        )
        assert resposta.status_code == 422
