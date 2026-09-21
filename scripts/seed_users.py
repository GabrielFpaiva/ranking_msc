#!/usr/bin/env python3
"""Gera o template de configuração embutido no instalador desktop.

Recebe a lista de e-mails da equipe, sorteia uma senha para cada um, grava os
hashes bcrypt em ``config/settings.desktop.yaml`` e imprime o par
``e-mail → senha`` no stdout. A senha em texto claro existe apenas nessa saída:
nada dela é gravado em disco.

O destino é um arquivo próprio, não o ``settings.yaml.example``. O
``provision_user()`` regrava o YAML via PyYAML e perde os comentários, e o
``.example`` é onde cada campo está documentado.

Uso:
    python scripts/seed_users.py a@pmjp.pb.gov.br b@pmjp.pb.gov.br
    python scripts/seed_users.py --destino config/settings.desktop.yaml <emails>
"""

from __future__ import annotations

import argparse
import logging
import secrets
import string
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.services.users import provision_user  # noqa: E402

logger = logging.getLogger("ranking_msc")

_EXAMPLE_PATH = _PROJECT_ROOT / "config" / "settings.yaml.example"
_DEFAULT_DESTINO = _PROJECT_ROOT / "config" / "settings.desktop.yaml"
_PLACEHOLDER_SECRET = "change-me-in-production"
_ALFABETO = string.ascii_letters + string.digits


def gerar_senha(tamanho: int = 20) -> str:
    """Sorteia uma senha alfanumérica.

    Sem pontuação de propósito: a senha é ditada e digitada por pessoas no
    treinamento, e caractere especial em teclado ABNT2 gera erro de digitação
    mais do que segurança.

    Args:
        tamanho: número de caracteres. Mínimo aceito: 16.

    Returns:
        Senha aleatória.
    """
    if tamanho < 16:
        raise ValueError(f"Senha curta demais: {tamanho} caracteres (mínimo 16).")
    return "".join(secrets.choice(_ALFABETO) for _ in range(tamanho))


def seed(destino: Path, emails: list[str], *, example_path: Path) -> dict[str, str]:
    """Grava o template com um usuário por e-mail.

    Args:
        destino: arquivo YAML a criar ou sobrescrever.
        emails: e-mails que viram ``username``, na ordem informada. São gravados
            com ``.strip().casefold()``, igual à comparação do login.
        example_path: template base, usado quando o destino não existe.

    Returns:
        Mapa ``e-mail → senha em texto claro``, apenas em memória.

    Raises:
        ValueError: se a lista estiver vazia ou tiver e-mail repetido.
    """
    emails = [email.strip().casefold() for email in emails]
    if not emails:
        raise ValueError("Nenhum e-mail informado.")
    if len(set(emails)) != len(emails):
        raise ValueError("E-mail repetido na lista.")

    if destino.exists():
        destino.unlink()

    senhas: dict[str, str] = {}
    for email in emails:
        senha = gerar_senha()
        provision_user(destino, email, senha, example_path=example_path)
        senhas[email] = senha

    raw = yaml.safe_load(destino.read_text(encoding="utf-8")) or {}
    raw["security"]["secret_key"] = _PLACEHOLDER_SECRET
    destino.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return senhas


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Gera o template de config do instalador.")
    parser.add_argument("emails", nargs="+", help="e-mails da equipe")
    parser.add_argument(
        "--destino",
        type=Path,
        default=_DEFAULT_DESTINO,
        help=f"arquivo a gravar (padrão: {_DEFAULT_DESTINO})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Executa o seed e imprime as senhas geradas."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    senhas = seed(args.destino, args.emails, example_path=_EXAMPLE_PATH)

    print(f"\nTemplate gravado em {args.destino}\n")
    print("Senhas geradas (anote agora, não ficam em lugar nenhum):\n")
    for email, senha in senhas.items():
        print(f"  {email}  ->  {senha}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
