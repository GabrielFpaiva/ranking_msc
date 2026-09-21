"""Testes de scripts/seed_users.py — geração do template com usuários."""

from __future__ import annotations

import sys
from pathlib import Path

import bcrypt
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed_users import gerar_senha, seed  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"


def test_senha_gerada_tem_tamanho_minimo_e_varia() -> None:
    """Cada chamada devolve senha nova, com pelo menos 16 caracteres."""
    a, b = gerar_senha(), gerar_senha()
    assert len(a) >= 16
    assert a != b


def test_seed_grava_um_usuario_por_email(tmp_path: Path) -> None:
    """Os e-mails viram username e a senha confere pelo bcrypt."""
    destino = tmp_path / "settings.desktop.yaml"
    emails = ["a@exemplo.com", "b@exemplo.com"]

    senhas = seed(destino, emails, example_path=_EXAMPLE)

    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    users = raw["security"]["users"]
    assert [u["username"] for u in users] == emails
    for user in users:
        senha = senhas[user["username"]]
        assert bcrypt.checkpw(senha.encode("utf-8"), user["hashed_password"].encode("ascii"))


def test_seed_mantem_secret_key_no_placeholder(tmp_path: Path) -> None:
    """O secret é gerado por máquina na primeira execução, não no template."""
    destino = tmp_path / "settings.desktop.yaml"
    seed(destino, ["a@exemplo.com"], example_path=_EXAMPLE)
    raw = yaml.safe_load(destino.read_text(encoding="utf-8"))
    assert raw["security"]["secret_key"] == "change-me-in-production"


def test_seed_recusa_email_duplicado(tmp_path: Path) -> None:
    """E-mail repetido é erro de entrada, não sobrescrita silenciosa."""
    destino = tmp_path / "settings.desktop.yaml"
    with pytest.raises(ValueError):
        seed(destino, ["a@exemplo.com", "a@exemplo.com"], example_path=_EXAMPLE)
