"""Testes do provisionamento de usuários (services.users + scripts/create_user.py)."""

from __future__ import annotations

from pathlib import Path

import bcrypt
import pytest
import scripts.create_user as cli
import yaml

from ranking_msc.config.settings import load_settings
from ranking_msc.exceptions import ConfigError
from ranking_msc.services.users import config_has_users, provision_user

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"


class TestConfigHasUsers:
    def test_arquivo_ausente_retorna_false(self, tmp_path: Path) -> None:
        """Config inexistente → sem usuários (estado de primeiro acesso)."""
        assert config_has_users(tmp_path / "nao-existe.yaml") is False

    def test_config_com_usuario_retorna_true(self, tmp_path: Path) -> None:
        """Config com um usuário provisionado → True."""
        config_path = tmp_path / "settings.yaml"
        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)
        assert config_has_users(config_path) is True

    def test_secret_sem_usuarios_retorna_false(self, tmp_path: Path) -> None:
        """secret_key configurado mas sem users → ainda precisa de setup."""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text('security:\n  secret_key: "abc"\n', encoding="utf-8")
        assert config_has_users(config_path) is False

    def test_yaml_invalido_retorna_false(self, tmp_path: Path) -> None:
        """YAML ilegível → False (provision_user subsequente falha fechado)."""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text("security: [invalido\n  users:", encoding="utf-8")
        assert config_has_users(config_path) is False


class TestProvisionUser:
    def test_cria_config_do_example_quando_ausente(self, tmp_path: Path) -> None:
        """Sem settings.yaml, cria a partir do example e cadastra o usuário."""
        config_path = tmp_path / "settings.yaml"

        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)

        assert config_path.exists()
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert raw["security"]["users"][0]["username"] == "admin"

    def test_hash_bcrypt_valida_a_senha_original(self, tmp_path: Path) -> None:
        """O hash gravado confere com a senha via bcrypt.checkpw."""
        config_path = tmp_path / "settings.yaml"

        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        hashed = raw["security"]["users"][0]["hashed_password"]
        assert bcrypt.checkpw(b"senha-forte", hashed.encode("ascii"))
        assert not bcrypt.checkpw(b"senha-errada", hashed.encode("ascii"))

    def test_secret_key_inseguro_e_substituido(self, tmp_path: Path) -> None:
        """O placeholder 'change-me-in-production' é trocado por chave gerada."""
        config_path = tmp_path / "settings.yaml"

        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        secret = raw["security"]["secret_key"]
        assert secret != "change-me-in-production"
        assert len(secret) == 64  # token_hex(32)

    def test_secret_key_existente_e_preservado(self, tmp_path: Path) -> None:
        """secret_key já configurado não é regenerado (não invalida tokens)."""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            'security:\n  secret_key: "chave-ja-configurada-pela-equipe"\n',
            encoding="utf-8",
        )

        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert raw["security"]["secret_key"] == "chave-ja-configurada-pela-equipe"

    def test_usuario_existente_e_atualizado_sem_duplicar(self, tmp_path: Path) -> None:
        """Cadastrar o mesmo username troca a senha em vez de duplicar."""
        config_path = tmp_path / "settings.yaml"
        provision_user(config_path, "admin", "senha-antiga", example_path=_EXAMPLE)
        provision_user(config_path, "maria", "outra-senha", example_path=_EXAMPLE)

        provision_user(config_path, "admin", "senha-nova", example_path=_EXAMPLE)

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        users = raw["security"]["users"]
        assert sorted(u["username"] for u in users) == ["admin", "maria"]
        admin = next(u for u in users if u["username"] == "admin")
        assert bcrypt.checkpw(b"senha-nova", admin["hashed_password"].encode("ascii"))

    def test_resultado_passa_no_loader_oficial(self, tmp_path: Path) -> None:
        """O config gerado carrega sem warning/erro em load_settings()."""
        config_path = tmp_path / "settings.yaml"

        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)

        settings = load_settings(config_path)
        assert settings.security.users[0].username == "admin"
        assert len(settings.rules.enabled) > 0  # herdado do example

    def test_sem_config_nem_example_levanta_configerror(self, tmp_path: Path) -> None:
        """Sem config e sem template, falha explícita."""
        with pytest.raises(ConfigError, match="template"):
            provision_user(
                tmp_path / "settings.yaml",
                "admin",
                "senha",
                example_path=tmp_path / "nao-existe.yaml",
            )


class TestRunCli:
    def test_password_env_ausente_retorna_codigo_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--password-env apontando para variável vazia falha com código 2."""
        monkeypatch.delenv("SENHA_TESTE_XYZ", raising=False)

        exit_code = cli.run_cli(
            [
                "--username",
                "admin",
                "--password-env",
                "SENHA_TESTE_XYZ",
                "--config",
                str(tmp_path / "settings.yaml"),
            ]
        )

        assert exit_code == 2

    def test_fluxo_nao_interativo_com_password_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fluxo do entrypoint Docker: senha via env var, saída 0."""
        monkeypatch.setenv("SENHA_TESTE_XYZ", "senha-do-deploy")
        config_path = tmp_path / "settings.yaml"

        exit_code = cli.run_cli(
            [
                "--username",
                "admin",
                "--password-env",
                "SENHA_TESTE_XYZ",
                "--config",
                str(config_path),
            ]
        )

        assert exit_code == 0
        settings = load_settings(config_path)
        assert settings.security.users[0].username == "admin"
