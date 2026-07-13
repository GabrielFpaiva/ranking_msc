"""
app.api.routes.auth
~~~~~~~~~~~~~~~~~~~

POST /api/auth/token        — emite JWT via OAuth2 password flow.
GET  /api/auth/me           — retorna o usuário autenticado.
GET  /api/auth/setup-status — indica se o primeiro acesso está pendente.
POST /api/auth/setup        — cria o primeiro usuário (só com zero usuários).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.api.auth import authenticate_user, create_access_token
from app.api.deps import PROJECT_ROOT, get_config_path, get_current_user, get_settings
from ranking_msc.services.users import provision_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EXAMPLE_PATH: Path = PROJECT_ROOT / "config" / "settings.yaml.example"


class TokenOut(BaseModel):
    """Resposta do endpoint de login."""
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Representação pública do usuário autenticado."""
    username: str


@router.post(
    "/token",
    response_model=TokenOut,
    summary="Obter token JWT via usuário e senha",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
) -> TokenOut:
    """Autentica usuário e retorna Bearer token JWT."""
    settings = get_settings()
    user = authenticate_user(settings.security, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.username, settings.security)
    return TokenOut(access_token=token)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Retorna o usuário autenticado",
)
def me(current_user: str = Depends(get_current_user)) -> UserOut:  # noqa: B008
    """Retorna o username do token JWT presente na requisição."""
    return UserOut(username=current_user)


class SetupStatusOut(BaseModel):
    """Indica se o sistema aguarda a criação do primeiro usuário."""
    needs_setup: bool


class SetupIn(BaseModel):
    """Payload do primeiro acesso — criação do usuário administrador."""
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


@router.get(
    "/setup-status",
    response_model=SetupStatusOut,
    summary="Indica se o primeiro acesso está pendente",
)
def setup_status() -> SetupStatusOut:
    """Retorna ``needs_setup=True`` enquanto nenhum usuário está configurado."""
    return SetupStatusOut(needs_setup=not get_settings().security.users)


@router.post(
    "/setup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria o primeiro usuário (disponível apenas com zero usuários)",
)
def setup(body: SetupIn) -> UserOut:
    """Cria o usuário administrador do primeiro acesso pelo navegador.

    Grava o usuário (hash bcrypt) e um ``secret_key`` seguro no
    ``settings.yaml`` e recarrega as configurações. Assim que existir
    qualquer usuário configurado, o endpoint responde 403 para sempre —
    novos usuários passam a ser cadastrados via ``scripts/create_user.py``.
    """
    if get_settings().security.users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup já concluído. Cadastre usuários via scripts/create_user.py.",
        )

    provision_user(
        get_config_path(),
        body.username,
        body.password,
        example_path=_EXAMPLE_PATH,
    )
    # Invalida o cache para que o login enxergue o usuário recém-criado.
    get_settings.cache_clear()
    return UserOut(username=body.username)
