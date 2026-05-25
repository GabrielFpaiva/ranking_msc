"""
tests/test_api_auth.py
~~~~~~~~~~~~~~~~~~~~~~~

Testes dos endpoints de autenticação JWT:
  POST /api/auth/token — emite token via OAuth2 password flow
  GET  /api/auth/me    — retorna usuário autenticado

E testes de proteção de rotas existentes:
  Sem token → 401
  Com token válido → 200
"""

from __future__ import annotations

import pytest
from app.api.auth import get_password_hash
from app.api.deps import get_current_user
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.config.settings import SecuritySettings, UserSettings


def _make_settings_with_user(username: str = "test", password: str = "secret"):
    """Cria SecuritySettings com um usuário de teste."""
    return SecuritySettings(
        secret_key="test-secret-key-for-tests-only",
        algorithm="HS256",
        access_token_expire_minutes=60,
        users=[UserSettings(username=username, hashed_password=get_password_hash(password))],
    )


@pytest.fixture
def clean_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client sem bypass de auth — usa JWT real.

    Remove a substituição de get_current_user do conftest global e
    injetar settings com usuário de teste.
    """
    import app.api.deps as deps_module
    import app.api.routes.auth as auth_routes_module

    test_security = _make_settings_with_user()

    # Remove o bypass de auth global do conftest (que retorna "test-user" sem token)
    app.dependency_overrides.pop(get_current_user, None)

    # Faz get_settings retornar settings com usuário de teste
    from ranking_msc.config.settings import Settings
    test_settings = Settings(security=test_security)
    monkeypatch.setattr(deps_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(auth_routes_module, "get_settings", lambda: test_settings)

    client = TestClient(app)
    yield client

    # Restaura o bypass global
    app.dependency_overrides[get_current_user] = lambda: "test-user"


# ---------------------------------------------------------------------------
# POST /api/auth/token
# ---------------------------------------------------------------------------


class TestAuthToken:
    def test_credenciais_validas_retornam_token(
        self, clean_client: TestClient
    ) -> None:
        """Login com credenciais válidas retorna access_token e token_type bearer."""
        response = clean_client.post(
            "/api/auth/token",
            data={"username": "test", "password": "secret"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 10

    def test_senha_errada_retorna_401(self, clean_client: TestClient) -> None:
        """Senha incorreta retorna 401."""
        response = clean_client.post(
            "/api/auth/token",
            data={"username": "test", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_usuario_inexistente_retorna_401(self, clean_client: TestClient) -> None:
        """Usuário não cadastrado retorna 401."""
        response = clean_client.post(
            "/api/auth/token",
            data={"username": "nobody", "password": "secret"},
        )
        assert response.status_code == 401

    def test_campos_ausentes_retorna_422(self, clean_client: TestClient) -> None:
        """Payload sem username/password retorna 422 (validação)."""
        response = clean_client.post("/api/auth/token", data={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


class TestAuthMe:
    def test_token_valido_retorna_username(self, clean_client: TestClient) -> None:
        """Token válido em /api/auth/me retorna o username."""
        # Obtém token
        login_resp = clean_client.post(
            "/api/auth/token",
            data={"username": "test", "password": "secret"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        me_resp = clean_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "test"

    def test_sem_token_retorna_401(self, clean_client: TestClient) -> None:
        """Sem Authorization header retorna 401."""
        response = clean_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_token_invalido_retorna_401(self, clean_client: TestClient) -> None:
        """Token forjado retorna 401."""
        response = clean_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token.invalido.aqui"},
        )
        assert response.status_code == 401

    def test_token_sub_inexistente_retorna_401(self, clean_client: TestClient) -> None:
        """Token válido mas cujo sub não existe na lista de usuários retorna 401."""
        from app.api.auth import create_access_token

        settings = _make_settings_with_user()
        token = create_access_token("usuario-que-nao-existe", settings)
        response = clean_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Proteção de rotas existentes
# ---------------------------------------------------------------------------


class TestRotasProtegidas:
    def test_rota_sem_token_retorna_401(self, clean_client: TestClient) -> None:
        """GET /api/competencias sem token retorna 401."""
        response = clean_client.get("/api/competencias?siconfi=250400")
        assert response.status_code == 401

    def test_rota_com_token_valido_retorna_200_ou_404(
        self, clean_client: TestClient
    ) -> None:
        """GET /api/competencias com token válido não retorna 401 (dados podem estar vazios)."""
        login_resp = clean_client.post(
            "/api/auth/token",
            data={"username": "test", "password": "secret"},
        )
        token = login_resp.json()["access_token"]

        response = clean_client.get(
            "/api/competencias?siconfi=250400",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code != 401

    def test_healthcheck_nao_requer_token(self, clean_client: TestClient) -> None:
        """/api/health é público — não requer autenticação."""
        response = clean_client.get("/api/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Lógica pura de auth (sem HTTP)
# ---------------------------------------------------------------------------


class TestAuthLogicaPura:
    def test_verify_password_correto(self) -> None:
        """verify_password retorna True para senha correta."""
        from app.api.auth import verify_password

        hashed = get_password_hash("minha-senha")
        assert verify_password("minha-senha", hashed) is True

    def test_verify_password_incorreto(self) -> None:
        """verify_password retorna False para senha errada."""
        from app.api.auth import verify_password

        hashed = get_password_hash("minha-senha")
        assert verify_password("outra-senha", hashed) is False

    def test_create_e_decode_token_roundtrip(self) -> None:
        """Token criado pode ser decodificado e retorna o username correto."""
        from app.api.auth import create_access_token, decode_token

        settings = _make_settings_with_user()
        token = create_access_token("alice", settings)
        assert decode_token(token, settings) == "alice"

    def test_decode_token_invalido_levanta_valueerror(self) -> None:
        """Token malformado levanta ValueError."""
        from app.api.auth import decode_token

        settings = _make_settings_with_user()
        with pytest.raises(ValueError):
            decode_token("nao.e.um.jwt", settings)

    def test_authenticate_user_credenciais_validas(self) -> None:
        """authenticate_user retorna UserSettings para credenciais válidas."""
        from app.api.auth import authenticate_user

        sec = _make_settings_with_user("admin", "s3cr3t")
        result = authenticate_user(sec, "admin", "s3cr3t")
        assert result is not None
        assert result.username == "admin"

    def test_authenticate_user_credenciais_invalidas(self) -> None:
        """authenticate_user retorna None para credenciais inválidas."""
        from app.api.auth import authenticate_user

        sec = _make_settings_with_user("admin", "s3cr3t")
        assert authenticate_user(sec, "admin", "errado") is None
        assert authenticate_user(sec, "desconhecido", "s3cr3t") is None

    def test_verify_password_hash_malformado_retorna_false(self) -> None:
        """Hash malformado em settings.yaml retorna False em vez de propagar ValueError."""
        from app.api.auth import verify_password

        assert verify_password("qualquer-senha", "nao-e-um-hash-bcrypt") is False

    def test_authenticate_user_hash_malformado_retorna_none(self) -> None:
        """Usuário com hash inválido no settings retorna None — não propaga como 500."""
        from app.api.auth import authenticate_user

        sec = _make_settings_with_user()
        import dataclasses

        bad_user = dataclasses.replace(sec.users[0], hashed_password="hash-invalido")
        sec_bad = dataclasses.replace(sec, users=[bad_user])
        assert authenticate_user(sec_bad, "test", "secret") is None


# ---------------------------------------------------------------------------
# _parse_users — ConfigError em entradas mal-formadas
# ---------------------------------------------------------------------------


class TestParseUsers:
    def test_entrada_sem_username_levanta_configerror(self) -> None:
        """Entrada sem 'username' levanta ConfigError."""
        from ranking_msc.config.settings import _parse_users
        from ranking_msc.exceptions import ConfigError

        with pytest.raises(ConfigError, match="username"):
            _parse_users([{"hashed_password": "$2b$12$abc"}])

    def test_entrada_sem_hashed_password_levanta_configerror(self) -> None:
        """Entrada sem 'hashed_password' levanta ConfigError."""
        from ranking_msc.config.settings import _parse_users
        from ranking_msc.exceptions import ConfigError

        with pytest.raises(ConfigError, match="hashed_password"):
            _parse_users([{"username": "admin"}])

    def test_entrada_nao_dict_levanta_configerror(self) -> None:
        """Entrada que não é dict levanta ConfigError."""
        from ranking_msc.config.settings import _parse_users
        from ranking_msc.exceptions import ConfigError

        with pytest.raises(ConfigError):
            _parse_users(["apenas-uma-string"])

    def test_lista_vazia_retorna_lista_vazia(self) -> None:
        """Lista vazia (sem usuários configurados) é válida."""
        from ranking_msc.config.settings import _parse_users

        assert _parse_users([]) == []

    def test_entrada_valida_retorna_usersettings(self) -> None:
        """Entrada bem-formada retorna UserSettings correto."""
        from ranking_msc.config.settings import _parse_users

        result = _parse_users([{"username": "alice", "hashed_password": "$2b$12$abc"}])
        assert len(result) == 1
        assert result[0].username == "alice"


# ---------------------------------------------------------------------------
# Segurança: secret_key padrão + timing equalization
# ---------------------------------------------------------------------------


class TestSecurityHardening:
    def test_secret_key_padrao_com_usuarios_levanta_configerror(self) -> None:
        """secret_key padrão com users configurados levanta ConfigError na inicialização."""
        from ranking_msc.config.settings import SecuritySettings, UserSettings
        from ranking_msc.exceptions import ConfigError

        sec = SecuritySettings(
            secret_key="change-me-in-production",
            algorithm="HS256",
            access_token_expire_minutes=60,
            users=[UserSettings(username="admin", hashed_password=get_password_hash("x"))],
        )
        with pytest.raises(ConfigError, match="secret_key"):
            from ranking_msc.config.settings import _validate_security
            _validate_security(sec)

    def test_secret_key_padrao_sem_usuarios_emite_aviso(self) -> None:
        """secret_key padrão sem users emite UserWarning (modo dev), não ConfigError."""
        import warnings as _warnings

        from ranking_msc.config.settings import SecuritySettings, _validate_security

        sec = SecuritySettings(
            secret_key="change-me-in-production",
            algorithm="HS256",
            access_token_expire_minutes=60,
            users=[],
        )
        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            _validate_security(sec)
        assert any("secret_key" in str(w.message) for w in caught)

    def test_username_inexistente_retorna_none_sem_excecao(self) -> None:
        """Username desconhecido retorna None mesmo executando bcrypt (timing equalization)."""
        from app.api.auth import authenticate_user

        sec = _make_settings_with_user("alice", "correta")
        # bob não existe — deve executar dummy bcrypt e retornar None
        assert authenticate_user(sec, "bob", "qualquer") is None
