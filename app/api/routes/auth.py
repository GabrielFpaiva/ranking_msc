"""
app.api.routes.auth
~~~~~~~~~~~~~~~~~~~

POST /api/auth/token — emite JWT via OAuth2 password flow.
GET  /api/auth/me    — retorna o usuário autenticado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.api.auth import authenticate_user, create_access_token
from app.api.deps import get_current_user, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
