#!/usr/bin/env python3
"""CLI para cadastrar/atualizar usuários no ``config/settings.yaml``.

Elimina o passo manual de gerar hash bcrypt na mão: o script pede a senha
(ou lê de variável de ambiente, para uso em Docker/CI), gera o hash e um
``secret_key`` seguro quando o atual é o placeholder, e grava tudo no YAML.

Alternativa sem terminal: com o app no ar e nenhum usuário configurado, a
tela de login vira "primeiro acesso" e cria o administrador pelo navegador.

Uso interativo:
    python scripts/create_user.py --username admin
    (a senha é pedida no prompt, sem eco)

Uso não interativo (ex.: docker/entrypoint.sh):
    RANKING_MSC_ADMIN_PASSWORD=... python scripts/create_user.py \\
        --username admin --password-env RANKING_MSC_ADMIN_PASSWORD
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.exceptions import ConfigError  # noqa: E402
from ranking_msc.services.users import provision_user  # noqa: E402

logger = logging.getLogger("ranking_msc")

_EXAMPLE_PATH = _PROJECT_ROOT / "config" / "settings.yaml.example"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando.

    Args:
        argv: lista de argumentos (sem nome do programa). Se ``None``,
            usa ``sys.argv``.

    Returns:
        Namespace com ``username``, ``password``, ``password_env`` e ``config``.
    """
    parser = argparse.ArgumentParser(
        description="Cadastra ou atualiza um usuário no config/settings.yaml.",
    )
    parser.add_argument("--username", required=True, help="Nome do usuário.")
    parser.add_argument(
        "--password",
        required=False,
        help="Senha em texto plano (evite em shells compartilhados; prefira o prompt).",
    )
    parser.add_argument(
        "--password-env",
        required=False,
        help="Nome da variável de ambiente que contém a senha (uso não interativo).",
    )
    parser.add_argument(
        "--secret-key-env",
        required=False,
        help=(
            "Nome da variável de ambiente com um secret_key fixo. Sem disco "
            "persistente (ex.: Render free), evita gerar uma chave nova a "
            "cada reinício e derrubar as sessões já logadas."
        ),
    )
    parser.add_argument(
        "--config",
        required=False,
        help="Caminho do settings.yaml (padrão: config/settings.yaml do projeto).",
    )
    return parser.parse_args(argv)


def _resolve_password(args: argparse.Namespace) -> str:
    """Obtém a senha do argumento, da variável de ambiente ou do prompt.

    Raises:
        ConfigError: se a variável de ambiente indicada não existir/estiver
            vazia, ou se a senha final for vazia.
    """
    if args.password:
        return str(args.password)

    if args.password_env:
        value = os.environ.get(args.password_env, "")
        if not value:
            raise ConfigError(
                f"Variável de ambiente '{args.password_env}' vazia ou inexistente."
            )
        return value

    password = getpass.getpass(f"Senha para '{args.username}': ")
    if not password:
        raise ConfigError("Senha vazia não é permitida.")
    return password


def _resolve_secret_key(args: argparse.Namespace) -> str | None:
    """Obtém o secret_key fixo de ``--secret-key-env``, se informado.

    Raises:
        ConfigError: se ``--secret-key-env`` foi passado mas a variável de
            ambiente correspondente está vazia/inexistente.
    """
    if not args.secret_key_env:
        return None

    value = os.environ.get(args.secret_key_env, "")
    if not value:
        raise ConfigError(
            f"Variável de ambiente '{args.secret_key_env}' vazia ou inexistente."
        )
    return value


def run_cli(argv: list[str] | None = None) -> int:
    """Executa a CLI com tratamento padronizado de erros.

    Returns:
        Código de saída Unix (0 = sucesso, 2 = erro de configuração).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)
    config_path = (
        Path(args.config).expanduser().resolve()
        if args.config
        else _PROJECT_ROOT / "config" / "settings.yaml"
    )

    try:
        password = _resolve_password(args)
        secret_key = _resolve_secret_key(args)
        provision_user(
            config_path,
            args.username,
            password,
            example_path=_EXAMPLE_PATH,
            secret_key=secret_key,
        )
        # Valida o resultado com o loader oficial — falha aqui indica bug.
        load_settings(config_path)
    except ConfigError as exc:
        logger.error("Falha ao cadastrar usuário: %s", exc)
        return 2
    return 0


def main() -> None:
    """Ponto de entrada do script CLI."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
