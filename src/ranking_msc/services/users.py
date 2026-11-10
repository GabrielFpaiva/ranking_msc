"""
ranking_msc.services.users
~~~~~~~~~~~~~~~~~~~~~~~~~~

Provisionamento de usuários no ``config/settings.yaml``: gera o hash bcrypt
da senha e um ``secret_key`` seguro quando o atual é o placeholder, gravando
tudo no YAML. Consumido pela CLI (``scripts/create_user.py``), pelo
entrypoint Docker e pelo endpoint de primeiro acesso (``POST /api/auth/setup``).

Nota: o YAML é regravado via PyYAML — comentários do arquivo são perdidos.
A documentação de cada campo permanece em ``config/settings.yaml.example``.
"""

from __future__ import annotations

import logging
import secrets
import shutil
from pathlib import Path
from typing import Any

import bcrypt
import yaml

from ranking_msc.config.settings import _INSECURE_SECRETS
from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")


def config_has_users(config_path: Path) -> bool:
    """Indica se o YAML tem ao menos um usuário em ``security.users``.

    Inspeciona o arquivo cru, sem a validação completa de ``load_settings()``:
    estados não provisionados (arquivo ausente, secret configurado mas sem
    usuários) fazem o loader levantar ``ConfigError`` e não podem impedir o
    fluxo de primeiro acesso de responder. YAML ilegível conta como "sem
    usuários" — o ``provision_user()`` subsequente falha fechado ao parsear.
    """
    if not config_path.exists():
        return False
    try:
        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    users = (raw.get("security") or {}).get("users") or []
    return bool(users)


def find_username(config_path: Path, email: str) -> str | None:
    """Acha o ``username`` já gravado que corresponde ao e-mail, sem diferenciar caixa.

    O login compara com ``strip().casefold()``, mas o ``provision_user`` compara
    o ``username`` cru; quem cadastra por e-mail (convite) usa esta busca para
    reaproveitar o nome gravado (``Fulano@X.com``) em vez de criar um segundo
    usuário para ``fulano@x.com``.

    Como ``config_has_users``, inspeciona o YAML cru: arquivo ausente ou ilegível
    conta como "sem usuários".

    Args:
        config_path: caminho do settings.yaml.
        email: e-mail procurado (é normalizado com ``strip().casefold()``).

    Returns:
        O ``username`` exatamente como está gravado, ou ``None`` se não existir.
    """
    if not config_path.exists():
        return None
    try:
        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    wanted = email.strip().casefold()
    for user in (raw.get("security") or {}).get("users") or []:
        username = str(user.get("username", ""))
        if username.strip().casefold() == wanted:
            return username
    return None


def provision_user(
    config_path: Path,
    username: str,
    password: str,
    *,
    example_path: Path,
) -> Path:
    """Cadastra/atualiza o usuário no YAML, gerando hash e secret_key.

    Se o arquivo de configuração não existir, ele é criado a partir do
    ``settings.yaml.example``. Se o ``secret_key`` atual for o placeholder
    inseguro, um novo é gerado com ``secrets.token_hex(32)``. Um usuário com
    o mesmo ``username`` é substituído (troca de senha), nunca duplicado.

    Args:
        config_path: caminho do settings.yaml a atualizar.
        username: nome do usuário a cadastrar/atualizar.
        password: senha em texto plano (apenas o hash bcrypt é gravado).
        example_path: template usado quando o config ainda não existe.

    Returns:
        Path do arquivo de configuração gravado.

    Raises:
        ConfigError: se nem o config nem o example existirem, ou se o YAML
            existente for inválido.
    """
    if not config_path.exists():
        if not example_path.exists():
            raise ConfigError(
                f"Nem {config_path} nem o template {example_path} existem."
            )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example_path, config_path)
        logger.info("Config criado a partir do template: %s", config_path)

    try:
        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {config_path}: {exc}") from exc

    security: dict[str, Any] = dict(raw.get("security") or {})

    if str(security.get("secret_key", "")) in _INSECURE_SECRETS:
        security["secret_key"] = secrets.token_hex(32)
        logger.info("secret_key inseguro/ausente — novo secret_key gerado.")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    users: list[dict[str, str]] = [
        u for u in (security.get("users") or []) if u.get("username") != username
    ]
    users.append({"username": username, "hashed_password": hashed})
    security["users"] = users
    raw["security"] = security

    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    logger.info("Usuário '%s' gravado em %s.", username, config_path)
    return config_path
