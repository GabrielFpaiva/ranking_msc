"""
ranking_msc.services.users
~~~~~~~~~~~~~~~~~~~~~~~~~~

Provisionamento de usuários no ``config/settings.yaml``: gera o hash bcrypt
da senha e um ``secret_key`` seguro quando o atual é o placeholder, gravando
tudo no YAML. Consumido pela CLI (``scripts/create_user.py``), pelo
entrypoint Docker e pelo endpoint de primeiro acesso (``POST /api/auth/setup``).

Nota: o YAML é regravado via PyYAML — comentários do arquivo são perdidos.
A documentação de cada campo permanece em ``config/settings.yaml.example``.

A regravação é atômica (temporário na mesma pasta + ``os.replace``) e serializada
por um lock do processo: quem lê o arquivo durante a gravação vê a versão antiga
ou a nova, nunca um arquivo truncado, e duas gravações simultâneas não perdem
usuário uma da outra.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import bcrypt
import yaml

from ranking_msc.config.settings import _INSECURE_SECRETS
from ranking_msc.exceptions import ConfigError

logger = logging.getLogger("ranking_msc")

# Serializa ler → alterar → gravar o settings.yaml dentro do processo (o app desktop
# serve a API num processo só, com rotas síncronas em threads): sem ele, o aceite de
# convite e o primeiro acesso gravando juntos perderiam o usuário um do outro.
_SETTINGS_LOCK = threading.Lock()

# No Windows o ``os.replace`` falha com PermissionError enquanto outro leitor tem o
# destino aberto (o login lê o settings.yaml a cada tentativa). Leitura é rápida:
# poucas tentativas curtas bastam antes de desistir com ConfigError.
_REPLACE_TENTATIVAS = 5
_REPLACE_ESPERA_S = 0.05


def _write_text_atomic(destino: Path, conteudo: str) -> None:
    """Grava ``conteudo`` em ``destino`` via temporário na mesma pasta + ``os.replace``.

    Raises:
        ConfigError: se o destino seguir bloqueado depois das tentativas (o arquivo
            antigo fica intacto e o temporário é apagado).
    """
    fd, tmp_nome = tempfile.mkstemp(dir=destino.parent, prefix=".settings-", suffix=".tmp")
    tmp = Path(tmp_nome)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        for tentativa in range(1, _REPLACE_TENTATIVAS + 1):
            try:
                os.replace(tmp, destino)
                return
            except PermissionError as exc:
                if tentativa == _REPLACE_TENTATIVAS:
                    raise ConfigError(
                        f"Não foi possível gravar {destino}: o arquivo está em uso por "
                        "outro programa. Feche-o e tente de novo."
                    ) from exc
                time.sleep(_REPLACE_ESPERA_S)
    finally:
        tmp.unlink(missing_ok=True)


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
        ConfigError: se nem o config nem o example existirem, se o YAML
            existente for inválido, ou se o arquivo seguir bloqueado para gravação.
    """
    with _SETTINGS_LOCK:
        return _provision_user_locked(config_path, username, password, example_path)


def _provision_user_locked(
    config_path: Path, username: str, password: str, example_path: Path
) -> Path:
    """Corpo de ``provision_user``; quem chama já segura ``_SETTINGS_LOCK``."""
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

    _write_text_atomic(
        config_path,
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
    )
    logger.info("Usuário '%s' gravado em %s.", username, config_path)
    return config_path
