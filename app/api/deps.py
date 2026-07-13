"""
app.api.deps
~~~~~~~~~~~~

Dependências compartilhadas entre rotas: settings carregado, logger configurado,
paths absolutos do projeto e autenticação JWT.

Carrega ``ranking_msc.rules`` por side-effect na importação para popular
RULE_REGISTRY antes que qualquer rota tente listar regras.
"""

from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Adicionar src/ ao path antes de importar ranking_msc.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import ranking_msc.rules  # noqa: E402, F401  -- popular RULE_REGISTRY
from ranking_msc.config.settings import Settings, load_settings  # noqa: E402
from ranking_msc.outputs.logs import setup_logging  # noqa: E402

PROJECT_ROOT: Path = _PROJECT_ROOT

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Carrega o ``settings.yaml``.

    Honra a variável de ambiente ``RANKING_MSC_CONFIG`` (mesma semântica do
    loader e dos CLIs); sem ela, usa ``<raiz do projeto>/config/settings.yaml``.
    """
    env_path = os.environ.get("RANKING_MSC_CONFIG")
    config_path = Path(env_path) if env_path else PROJECT_ROOT / "config" / "settings.yaml"
    return load_settings(config_path)


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    """Configura e retorna o logger padrão do ranking_msc."""
    settings = get_settings()
    return setup_logging(log_dir=PROJECT_ROOT / settings.paths.logs_dir)


def absolute_snapshots_dir() -> Path:
    """Retorna o diretório de snapshots resolvido absolutamente."""
    settings = get_settings()
    return (PROJECT_ROOT / settings.paths.snapshots_dir).resolve()


def absolute_reports_dir() -> Path:
    """Retorna o diretório de relatórios Excel resolvido absolutamente."""
    settings = get_settings()
    return (PROJECT_ROOT / settings.paths.reports_dir).resolve()


def get_current_user(token: str = Depends(_oauth2_scheme)) -> str:  # noqa: B008
    """Decodifica o JWT e retorna o username autenticado.

    Valida o subject do token contra a lista de usuários configurados em
    settings.security.users — tokens assinados com a chave correta mas cujo
    sub não corresponde a nenhum usuário ativo são rejeitados com 401.

    Raises:
        HTTPException 401: se o token for inválido, expirado ou o subject
            não existir na lista de usuários configurados.
    """
    from app.api.auth import decode_token, find_user

    settings = get_settings()
    try:
        username = decode_token(token, settings.security)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if find_user(settings.security, username) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário do token não encontrado na configuração.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return username
