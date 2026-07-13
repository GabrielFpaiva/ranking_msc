"""Testes do primeiro acesso via navegador (GET/POST /api/auth/setup*)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"


@pytest.fixture
def fresh_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Config recém-instalada (example, zero usuários) isolada em tmp_path.

    Aponta RANKING_MSC_CONFIG para a cópia temporária e limpa o cache de
    get_settings antes e depois, para não vazar estado entre testes.
    """
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
    api_deps.get_settings.cache_clear()
    yield config_path
    api_deps.get_settings.cache_clear()


class TestSetupStatus:
    def test_sem_usuarios_precisa_de_setup(self, fresh_config: Path) -> None:
        """Config recém-instalada → needs_setup=True."""
        client = TestClient(app)
        response = client.get("/api/auth/setup-status")
        assert response.status_code == 200
        assert response.json() == {"needs_setup": True}


class TestSetup:
    def test_cria_admin_e_permite_login(self, fresh_config: Path) -> None:
        """Fluxo completo do primeiro acesso: setup → status falso → login."""
        client = TestClient(app)

        created = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )
        assert created.status_code == 201, created.text
        assert created.json() == {"username": "admin"}

        # O setup fecha a porta: status deixa de pedir setup.
        assert client.get("/api/auth/setup-status").json() == {"needs_setup": False}

        # E o login com as credenciais criadas funciona.
        token = client.post(
            "/api/auth/token",
            data={"username": "admin", "password": "senha-forte-123"},
        )
        assert token.status_code == 200, token.text
        assert token.json()["access_token"]

    def test_segundo_setup_retorna_403(self, fresh_config: Path) -> None:
        """Com qualquer usuário configurado, o endpoint tranca para sempre."""
        client = TestClient(app)
        client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )

        response = client.post(
            "/api/auth/setup",
            json={"username": "intruso", "password": "outra-senha-123"},
        )

        assert response.status_code == 403

    def test_senha_curta_retorna_422(self, fresh_config: Path) -> None:
        """Senha com menos de 8 caracteres é rejeitada na validação."""
        client = TestClient(app)
        response = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "curta"},
        )
        assert response.status_code == 422

    def test_username_invalido_retorna_422(self, fresh_config: Path) -> None:
        """Username com caracteres fora do padrão é rejeitado."""
        client = TestClient(app)
        response = client.post(
            "/api/auth/setup",
            json={"username": "ad min!", "password": "senha-forte-123"},
        )
        assert response.status_code == 422

    def test_setup_gera_secret_key_seguro(self, fresh_config: Path) -> None:
        """Após o setup, o secret_key placeholder foi substituído."""
        import yaml

        client = TestClient(app)
        client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )

        raw = yaml.safe_load(fresh_config.read_text(encoding="utf-8"))
        assert raw["security"]["secret_key"] != "change-me-in-production"
