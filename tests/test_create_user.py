"""Testes do provisionamento de usuários (services.users + scripts/create_user.py)."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import bcrypt
import pytest
import scripts.create_user as cli
import yaml

import ranking_msc.services.users as users_service
from ranking_msc.config.settings import load_settings
from ranking_msc.exceptions import ConfigError
from ranking_msc.services.users import config_has_users, find_username, provision_user

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


class TestFindUsername:
    def _config(self, tmp_path: Path, *usernames: str) -> Path:
        config_path = tmp_path / "settings.yaml"
        for username in usernames:
            provision_user(config_path, username, "senha-forte", example_path=_EXAMPLE)
        return config_path

    def test_acha_em_outra_caixa_e_devolve_o_nome_gravado(self, tmp_path: Path) -> None:
        """'fulano@x.com' acha o usuário gravado como 'Fulano@X.com' e devolve o nome gravado."""
        config_path = self._config(tmp_path, "Fulano@X.com")
        assert find_username(config_path, "fulano@x.com") == "Fulano@X.com"

    def test_espacos_em_volta_do_email_sao_ignorados(self, tmp_path: Path) -> None:
        """A busca faz strip(): ' FULANO@x.com\\n' acha o mesmo usuário."""
        config_path = self._config(tmp_path, "fulano@x.com")
        assert find_username(config_path, " FULANO@x.com\n") == "fulano@x.com"

    def test_acha_entre_varios_usuarios(self, tmp_path: Path) -> None:
        """Com 3 usuários, devolve o certo (não o primeiro nem o último por engano)."""
        config_path = self._config(tmp_path, "a@x.com", "Meio@x.com", "z@x.com")
        assert find_username(config_path, "MEIO@x.com") == "Meio@x.com"

    def test_inexistente_retorna_none(self, tmp_path: Path) -> None:
        """E-mail de ninguém → None; 'a@x.co' não casa por prefixo com 'a@x.com'."""
        config_path = self._config(tmp_path, "a@x.com")
        assert find_username(config_path, "a@x.co") is None

    def test_arquivo_ausente_retorna_none(self, tmp_path: Path) -> None:
        """Config inexistente → None, sem exceção."""
        assert find_username(tmp_path / "nao-existe.yaml", "a@x.com") is None

    def test_sem_usuarios_retorna_none(self, tmp_path: Path) -> None:
        """Config com secret mas sem users → None."""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text('security:\n  secret_key: "abc"\n', encoding="utf-8")
        assert find_username(config_path, "a@x.com") is None

    def test_yaml_invalido_retorna_none(self, tmp_path: Path) -> None:
        """YAML ilegível → None (como config_has_users)."""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text("security: [invalido\n  users:", encoding="utf-8")
        assert find_username(config_path, "a@x.com") is None


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


class TestProvisionUserGravacaoAtomica:
    def test_destino_bloqueado_uma_vez_grava_na_tentativa_seguinte(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Windows: leitor com o arquivo aberto faz o replace falhar; tenta de novo e grava."""
        config_path = tmp_path / "settings.yaml"
        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)
        real = os.replace
        chamadas: list[int] = []

        def replace_ocupado_uma_vez(origem: Any, destino: Any) -> None:
            chamadas.append(1)
            if len(chamadas) == 1:
                raise PermissionError("arquivo em uso")
            real(origem, destino)

        monkeypatch.setattr(users_service.os, "replace", replace_ocupado_uma_vez)
        provision_user(config_path, "maria", "senha-forte-2", example_path=_EXAMPLE)

        assert len(chamadas) == 2
        assert find_username(config_path, "maria") == "maria"
        assert list(tmp_path.glob(".settings-*.tmp")) == []

    def test_destino_sempre_bloqueado_levanta_configerror_e_preserva_o_arquivo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bloqueio que não passa → ConfigError; o settings.yaml antigo fica inteiro."""
        config_path = tmp_path / "settings.yaml"
        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)
        antes = config_path.read_bytes()

        def replace_ocupado(origem: Any, destino: Any) -> None:
            raise PermissionError("arquivo em uso")

        monkeypatch.setattr(users_service.os, "replace", replace_ocupado)
        monkeypatch.setattr(users_service, "_REPLACE_ESPERA_S", 0)
        with pytest.raises(ConfigError, match="em uso"):
            provision_user(config_path, "maria", "senha-forte-2", example_path=_EXAMPLE)

        assert config_path.read_bytes() == antes
        assert list(tmp_path.glob(".settings-*.tmp")) == []

    def test_gravacoes_simultaneas_nao_perdem_usuario(self, tmp_path: Path) -> None:
        """Vários provisionamentos ao mesmo tempo → todos os usuários ficam no arquivo."""
        config_path = tmp_path / "settings.yaml"
        provision_user(config_path, "admin", "senha-forte", example_path=_EXAMPLE)
        nomes = [f"usuario{i}" for i in range(6)]
        largada = threading.Barrier(len(nomes))

        def provisionar(nome: str) -> None:
            largada.wait()
            provision_user(config_path, nome, "senha-forte-9", example_path=_EXAMPLE)

        threads = [threading.Thread(target=provisionar, args=(nome,)) for nome in nomes]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        gravados = {u["username"] for u in raw["security"]["users"]}
        assert gravados == {"admin", *nomes}


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
