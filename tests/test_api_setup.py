"""Testes do primeiro acesso via navegador (GET/POST /api/auth/setup*).

O cache de settings da API é keyed por (caminho, mtime) — ver
``app.api.deps.get_settings`` — então mudanças no arquivo de config (setup,
scripts/create_user.py) valem na requisição seguinte, sem restart nem
invalidação manual de cache nos testes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.services.users import provision_user

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"


@pytest.fixture
def fresh_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Config recém-instalada (example, zero usuários) isolada em tmp_path."""
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
    yield config_path


class TestSetupStatus:
    def test_sem_usuarios_precisa_de_setup(self, fresh_config: Path) -> None:
        """Config recém-instalada → needs_setup=True."""
        client = TestClient(app)
        response = client.get("/api/auth/setup-status")
        assert response.status_code == 200
        assert response.json() == {"needs_setup": True}

    def test_config_ausente_precisa_de_setup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sem settings.yaml algum, o onboarding continua funcionando.

        load_settings() levantaria ConfigError aqui — o endpoint não pode
        depender dele, senão responde 500 e o primeiro acesso nunca aparece.
        """
        monkeypatch.setenv("RANKING_MSC_CONFIG", str(tmp_path / "nao-existe.yaml"))
        client = TestClient(app)

        response = client.get("/api/auth/setup-status")

        assert response.status_code == 200
        assert response.json() == {"needs_setup": True}

    def test_secret_configurado_sem_usuarios_precisa_de_setup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Operador gerou secret_key mas não criou usuários → ainda é setup.

        Essa combinação faz load_settings() levantar ConfigError (lockout);
        o fluxo de primeiro acesso é justamente a saída desse estado.
        """
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            'security:\n  secret_key: "chave-forte-configurada-pelo-operador"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
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

    def test_usuario_criado_externamente_loga_sem_restart(
        self,
        fresh_config: Path,
    ) -> None:
        """Usuário criado por scripts/create_user.py com a API no ar já loga.

        Cenário do review: o 403 do setup manda usar create_user.py, mas o
        script roda em outro processo. O cache por mtime garante que a API
        recarregue o settings.yaml na requisição seguinte — sem restart.
        """
        client = TestClient(app)
        client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )
        # get_settings() já cacheado com o estado pós-setup:
        assert client.get("/api/auth/setup-status").json() == {"needs_setup": False}

        # Operador roda create_user.py em outro processo, API continua no ar.
        provision_user(fresh_config, "maria", "senha-da-maria-1", example_path=_EXAMPLE)

        token = client.post(
            "/api/auth/token",
            data={"username": "maria", "password": "senha-da-maria-1"},
        )
        assert token.status_code == 200, token.text

    def test_setup_com_config_ausente_cria_do_example(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /setup sem settings.yaml cria o arquivo a partir do example."""
        config_path = tmp_path / "settings.yaml"
        monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
        client = TestClient(app)

        response = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )

        assert response.status_code == 201, response.text
        assert config_path.exists()
        token = client.post(
            "/api/auth/token",
            data={"username": "admin", "password": "senha-forte-123"},
        )
        assert token.status_code == 200, token.text

    def test_setup_preserva_secret_existente_sem_usuarios(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /setup no estado 'secret válido + zero usuários' não troca a chave."""
        import yaml

        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            'security:\n  secret_key: "chave-forte-configurada-pelo-operador"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))
        client = TestClient(app)

        response = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "senha-forte-123"},
        )

        assert response.status_code == 201, response.text
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert raw["security"]["secret_key"] == "chave-forte-configurada-pelo-operador"

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
