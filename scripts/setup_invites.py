#!/usr/bin/env python3
"""CLI de instalação do convite assinado (quem convida roda uma vez, no computador dele).

Dois comandos:

``init``
    Gera o par de chaves Ed25519, grava a chave privada cifrada e o
    ``invite_issuer.yaml`` (conta do Gmail e senha de app, cifrada com a senha da
    chave) na pasta de config do MCRA e a chave pública em ``config/invites.yaml``.
    Pede a senha da chave (duas vezes, 12 caracteres ou mais) e a senha de app do
    Gmail, sem eco. Recusa sobrescrever uma chave existente sem ``--force``. ``--issuer``
    e ``--smtp-user`` precisam ser só o endereço (sem nome, ``;`` ou sinais). A chave
    privada fica cifrada com a senha da chave (scrypt + Fernet), nunca em claro.

``set-url``
    Troca o link do instalador (``installer_url``) em ``config/invites.yaml``; o link
    precisa começar com ``https://``.

Só a linha ``public_key:`` ou ``installer_url:`` do ``invites.yaml`` é editada: os
comentários e o resto do arquivo ficam como estão. Nenhum segredo é impresso.

Uso (rode no PowerShell: o ``getpass`` no Git Bash não foi medido)::

    python scripts/setup_invites.py init --issuer gabriel@exemplo.com --smtp-user envio@gmail.com
    python scripts/setup_invites.py set-url https://drive.google.com/drive/folders/XXXX

Uso não interativo (as senhas vêm de variáveis de ambiente)::

    python scripts/setup_invites.py init --issuer ... --smtp-user ... \\
        --key-password-env MCRA_KEY_PASSWORD --smtp-password-env MCRA_SMTP_PASSWORD
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
# A raiz do repositório entra no path (não só src/): `desktop.bootstrap` só é
# importável por ela quando o script roda à mão, fora do pytest.
for _entry in (_PROJECT_ROOT, _PROJECT_ROOT / "src"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from desktop.bootstrap import data_home  # noqa: E402

from ranking_msc.exceptions import ConfigError, InviteError  # noqa: E402
from ranking_msc.services.invites import (  # noqa: E402
    MIN_KEY_PASSWORD_LENGTH,
    MSG_INVALID_EMAIL,
    InviteStore,
    IssuerConfig,
    encrypt_secret,
    generate_keypair,
    is_valid_email,
    load_invite_config,
)
from ranking_msc.services.users import find_username  # noqa: E402

_DEFAULT_INVITES_FILE = _PROJECT_ROOT / "config" / "invites.yaml"
_HTTPS_PREFIX = "https://"

# Uma linha `chave: valor  # comentário` no nível raiz do YAML. O valor pode vir
# entre aspas duplas ou simples, ou puro; o que sobra da linha (espaços e comentário)
# é preservado.
_VALUE_RE = r"""(?P<value>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^#\s]*)"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz parse dos argumentos da linha de comando.

    Args:
        argv: lista de argumentos (sem o nome do programa). Se ``None``, usa ``sys.argv``.

    Returns:
        Namespace com ``command`` (``init`` ou ``set-url``) e as opções do comando.
    """
    parser = argparse.ArgumentParser(
        description="Instala a chave do convite assinado e troca o link do instalador.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="{init,set-url}")

    init = commands.add_parser(
        "init",
        help="Gera a chave de convites e grava o emissor.",
        description=(
            "Gera o par de chaves, grava a chave privada cifrada e o emissor na pasta de "
            "config do MCRA e a chave pública em config/invites.yaml."
        ),
    )
    init.add_argument(
        "--issuer",
        required=True,
        help="E-mail do emissor no MCRA (o login de quem convida).",
    )
    init.add_argument(
        "--smtp-user",
        required=True,
        help="Conta do Gmail que envia os convites.",
    )
    init.add_argument(
        "--key-password-env",
        help="Variável de ambiente com a senha da chave (uso não interativo).",
    )
    init.add_argument(
        "--smtp-password-env",
        help="Variável de ambiente com a senha de app do Gmail (uso não interativo).",
    )
    init.add_argument(
        "--state-dir",
        help="Pasta de config do MCRA (padrão: %%LOCALAPPDATA%%\\MCRA\\config).",
    )
    init.add_argument(
        "--invites-file",
        help="Caminho do invites.yaml (padrão: config/invites.yaml do repositório).",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve a chave existente (os convites antigos deixam de valer).",
    )

    set_url = commands.add_parser(
        "set-url",
        help="Troca o link do instalador no invites.yaml.",
        description="Troca o link do instalador (installer_url) em config/invites.yaml.",
    )
    set_url.add_argument("url", help="Novo link da pasta do Drive com o instalador.")
    set_url.add_argument(
        "--invites-file",
        help="Caminho do invites.yaml (padrão: config/invites.yaml do repositório).",
    )
    return parser.parse_args(argv)


def replace_yaml_value(text: str, key: str, value: str) -> str:
    """Troca o valor da linha ``key:`` do YAML, preservando comentários e fim de linha.

    O valor novo é gravado entre aspas duplas. Só a primeira linha ``key:`` do nível
    raiz é editada; o resto do texto fica byte a byte como está.

    Raises:
        ConfigError: o texto não tem uma linha ``key:`` no nível raiz.
    """
    pattern = re.compile(rf"^(?P<head>{re.escape(key)}:[ \t]*){_VALUE_RE}(?P<rest>.*)$")
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        content = line.rstrip("\r\n")
        match = pattern.match(content)
        if match is None:
            continue
        eol = line[len(content) :]
        head = match["head"] if match["head"].endswith((" ", "\t")) else f"{match['head']} "
        lines[index] = f"{head}{json.dumps(value)}{match['rest']}{eol}"
        return "".join(lines)
    raise ConfigError(f"Não achei uma linha '{key}:' no invites.yaml.")


def _read_invites_text(path: Path) -> str:
    """Lê o ``invites.yaml`` em UTF-8, sem trocar fim de linha."""
    try:
        return path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise ConfigError(f"Não consegui ler {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"O arquivo {path} não está em UTF-8.") from exc


def _write_invites_text(path: Path, text: str) -> None:
    """Grava o ``invites.yaml`` em bytes (LF fica LF) por arquivo temporário e troca."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def _resolve_password(env_name: str | None, prompt: str, *, confirm: bool) -> str:
    """Obtém uma senha da variável de ambiente ou do prompt (sem eco).

    Raises:
        ConfigError: variável vazia ou inexistente, senha vazia ou confirmação diferente.
    """
    if env_name:
        value = os.environ.get(env_name, "")
        if not value:
            raise ConfigError(f"Variável de ambiente '{env_name}' vazia ou inexistente.")
        return value
    value = getpass.getpass(prompt)
    if not value:
        raise ConfigError("Senha vazia não é permitida.")
    if confirm and getpass.getpass("Repita a senha da chave: ") != value:
        raise ConfigError("As duas senhas da chave são diferentes. Rode o comando de novo.")
    return value


def _clean_address(value: str, option: str) -> str:
    """Devolve o endereço sem espaços nas pontas, ou levanta ``ConfigError`` com a opção."""
    address = value.strip()
    if not is_valid_email(address):
        raise ConfigError(f"{option}: {MSG_INVALID_EMAIL}")
    return address


def _run_init(args: argparse.Namespace) -> int:
    """Executa ``init``: valida tudo, depois grava a chave, o emissor e a chave pública."""
    issuer_email = _clean_address(args.issuer, "--issuer")
    smtp_user = _clean_address(args.smtp_user, "--smtp-user")
    state_dir = Path(args.state_dir).expanduser() if args.state_dir else data_home() / "config"
    invites_file = (
        Path(args.invites_file).expanduser() if args.invites_file else _DEFAULT_INVITES_FILE
    )
    store = InviteStore(state_dir)

    # 1. Tudo o que pode recusar vem antes de qualquer gravação: nunca fica chave nova
    #    no disco com a chave pública antiga no invites.yaml.
    invites_text = _read_invites_text(invites_file)
    replace_yaml_value(invites_text, "public_key", "")  # confere que a linha existe
    existing_public = load_invite_config(invites_file).public_key
    if (store.has_private_key() or existing_public) and not args.force:
        raise ConfigError(
            "Já existe uma chave de convites (em "
            f"{store.private_key_path} ou no {invites_file.name}). Trocá-la invalida todos os "
            "convites já emitidos; contas criadas continuam. Para trocar mesmo assim, "
            "rode de novo com --force."
        )
    key_password = _resolve_password(
        args.key_password_env, "Senha da chave (12 caracteres ou mais): ", confirm=True
    )
    if len(key_password) < MIN_KEY_PASSWORD_LENGTH:
        raise ConfigError(
            f"A senha da chave precisa ter {MIN_KEY_PASSWORD_LENGTH} caracteres ou mais."
        )
    smtp_password = _resolve_password(
        args.smtp_password_env, "Senha de app do Gmail: ", confirm=False
    )

    # 2. Só então gera e grava. O invites.yaml vai por último.
    pem, public_key = generate_keypair(key_password)
    issuer = IssuerConfig(
        email=issuer_email,
        smtp_user=smtp_user,
        smtp_password_encrypted=encrypt_secret(smtp_password, key_password),
    )
    new_invites_text = replace_yaml_value(invites_text, "public_key", public_key)
    store.write_private_key(pem)
    store.write_issuer(issuer)
    _write_invites_text(invites_file, new_invites_text)

    print(f"Chave privada (cifrada) gravada em: {store.private_key_path}")
    print(f"Emissor e conta de envio gravados em: {store.issuer_path}")
    print(f"Chave pública gravada em: {invites_file}")
    if find_username(state_dir / "settings.yaml", issuer_email) is None:
        print(
            f"AVISO: o e-mail {issuer_email} ainda não tem conta no MCRA em {state_dir}. "
            "Crie antes, para o item 'Convidar' aparecer no login dele:\n"
            f'  python scripts/create_user.py --username {issuer_email} --config '
            f'"{state_dir / "settings.yaml"}"',
            file=sys.stderr,
        )
    print(
        "Próximos passos: faça o commit do config/invites.yaml (só a chave pública mudou), "
        "gere o instalador novo e guarde uma cópia do invite_key.pem num lugar seguro."
    )
    return 0


def _run_set_url(args: argparse.Namespace) -> int:
    """Executa ``set-url``: troca só a linha ``installer_url:`` do invites.yaml.

    Raises:
        ConfigError: link vazio ou que não começa com ``https://``.
    """
    url = str(args.url).strip()
    if not url.startswith(_HTTPS_PREFIX) or not url[len(_HTTPS_PREFIX) :].strip():
        raise ConfigError(
            f"O link do instalador precisa começar com {_HTTPS_PREFIX} (copie o link inteiro "
            "da pasta do Drive)."
        )
    invites_file = (
        Path(args.invites_file).expanduser() if args.invites_file else _DEFAULT_INVITES_FILE
    )
    new_text = replace_yaml_value(_read_invites_text(invites_file), "installer_url", url)
    _write_invites_text(invites_file, new_text)
    print(f"Link do instalador gravado em: {invites_file}")
    print("Próximos passos: faça o commit do arquivo e gere um instalador novo.")
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    """Executa a CLI com tratamento padronizado de erros.

    Returns:
        Código de saída (0 = sucesso, 2 = erro de configuração ou de uso).
    """
    args = parse_args(argv)
    try:
        if args.command == "init":
            return _run_init(args)
        return _run_set_url(args)
    except (ConfigError, InviteError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    """Ponto de entrada do script CLI."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
