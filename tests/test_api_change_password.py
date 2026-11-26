"""Testes de POST /api/auth/change-password (troca de senha pelo próprio usuário).

Cada teste usa um ``settings.yaml`` em ``tmp_path`` (``RANKING_MSC_CONFIG``) com uma conta
real, e confere pelo login de verdade (``/api/auth/token``) que a senha nova entra e a antiga
não. Nenhum teste toca a config versionada.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api.deps import get_current_user
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.services.users import provision_user

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"
USUARIO = "Fulano@Exemplo.com"
SENHA_ATUAL = "senha-atual-123"
SENHA_NOVA = "senha-nova-456"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Config com uma conta; as rotas com login enxergam essa conta (em minúsculas)."""
    config_path = tmp_path / "settings.yaml"
    provision_user(config_path, USUARIO, SENHA_ATUAL, example_path=_EXAMPLE)
    monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
    app.dependency_overrides[get_current_user] = lambda: USUARIO.lower()
    yield TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: "test-user"


def _trocar(client: TestClient, atual: str, nova: str):  # noqa: ANN202
    return client.post(
        "/api/auth/change-password",
        json={"current_password": atual, "new_password": nova},
    )


def _login(client: TestClient, senha: str) -> int:
    resposta = client.post("/api/auth/token", data={"username": USUARIO, "password": senha})
    return resposta.status_code


def test_troca_e_a_nova_senha_entra_e_a_antiga_nao(client: TestClient) -> None:
    resposta = _trocar(client, SENHA_ATUAL, SENHA_NOVA)
    assert resposta.status_code == 204
    assert _login(client, SENHA_NOVA) == 200
    assert _login(client, SENHA_ATUAL) == 401


def test_nao_duplica_a_conta_gravada_com_outra_caixa(
    client: TestClient, tmp_path: Path
) -> None:
    """O username gravado é 'Fulano@Exemplo.com'; o token traz minúsculas. Sem conta nova."""
    import yaml

    _trocar(client, SENHA_ATUAL, SENHA_NOVA)
    raw = yaml.safe_load((tmp_path / "settings.yaml").read_text(encoding="utf-8"))
    nomes = [u["username"] for u in raw["security"]["users"]]
    assert nomes.count(USUARIO) == 1
    assert len([n for n in nomes if n.casefold() == USUARIO.casefold()]) == 1


def test_senha_atual_errada_retorna_400_e_nao_troca(client: TestClient) -> None:
    """400 e não 401: o frontend desloga em todo 401."""
    resposta = _trocar(client, "errada-errada-1", SENHA_NOVA)
    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Senha atual incorreta."
    assert _login(client, SENHA_ATUAL) == 200


@pytest.mark.parametrize("nova", ["curta", "á" * 40])
def test_senha_nova_fora_do_limite_retorna_422(client: TestClient, nova: str) -> None:
    resposta = _trocar(client, SENHA_ATUAL, nova)
    assert resposta.status_code == 422
    assert "mínimo 8 caracteres" in resposta.json()["detail"]
    assert _login(client, SENHA_ATUAL) == 200


def test_senha_nova_igual_a_atual_retorna_422(client: TestClient) -> None:
    resposta = _trocar(client, SENHA_ATUAL, SENHA_ATUAL)
    assert resposta.status_code == 422
    assert "diferente da atual" in resposta.json()["detail"]


def test_sem_login_retorna_401(client: TestClient) -> None:
    app.dependency_overrides.pop(get_current_user, None)
    assert _trocar(client, SENHA_ATUAL, SENHA_NOVA).status_code == 401


def test_nenhuma_senha_vai_para_o_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
        _trocar(client, "errada-errada-1", SENHA_NOVA)
        _trocar(client, SENHA_ATUAL, SENHA_NOVA)
    for segredo in (SENHA_ATUAL, SENHA_NOVA, "errada-errada-1"):
        assert segredo not in caplog.text
