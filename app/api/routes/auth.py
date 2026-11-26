"""
app.api.routes.auth
~~~~~~~~~~~~~~~~~~~

POST /api/auth/token        — emite JWT via OAuth2 password flow.
GET  /api/auth/me           — retorna o usuário autenticado.
GET  /api/auth/setup-status — indica se o primeiro acesso está pendente.
POST /api/auth/setup        — cria o primeiro usuário (só com zero usuários).
POST /api/auth/change-password — troca a senha do usuário logado (pede a atual).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.api.auth import authenticate_user, create_access_token
from app.api.deps import PROJECT_ROOT, get_config_path, get_current_user, get_settings
from ranking_msc.exceptions import ConfigError
from ranking_msc.services.users import config_has_users, provision_user

logger = logging.getLogger("ranking_msc")

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD_CHARS = 8
MAX_PASSWORD_BYTES = 72  # limite do bcrypt: além disso o hash levanta ValueError

_EXAMPLE_PATH: Path = PROJECT_ROOT / "config" / "settings.yaml.example"


def _needs_setup() -> bool:
    """True enquanto nenhum usuário está configurado.

    Lê o YAML cru (``config_has_users``) em vez de ``get_settings()``: nos
    estados não provisionados — arquivo ausente ou secret_key configurado sem
    usuários — o loader levanta ``ConfigError`` e o onboarding pelo navegador
    ficaria inutilizável (status 500 e setup nunca liberado).
    """
    return not config_has_users(get_config_path())


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
    return SetupStatusOut(needs_setup=_needs_setup())


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
    if not _needs_setup():
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
    # get_settings() recarrega sozinho: o cache é keyed pelo mtime do arquivo,
    # que acabou de mudar. Vale também para usuários criados por
    # scripts/create_user.py com a API no ar.
    return UserOut(username=body.username)


class ChangePasswordIn(BaseModel):
    """Senha atual (prova de que é a própria pessoa) e a senha nova."""
    current_password: str
    new_password: str


def _password_in_range(password: str) -> bool:
    """Senha de 8 caracteres a 72 bytes em UTF-8 (limite do bcrypt)."""
    try:
        size = len(password.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return len(password) >= MIN_PASSWORD_CHARS and size <= MAX_PASSWORD_BYTES


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Troca a senha do usuário logado",
)
def change_password(
    body: ChangePasswordIn,
    current_user: str = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Confere a senha atual e grava o hash da nova no ``settings.yaml``.

    Até aqui não havia como a pessoa trocar a própria senha: as senhas iniciais
    vão por e-mail no convite de acesso, e o único caminho era pedir um convite
    novo. O token atual continua válido (o JWT não depende da senha).

    Senha atual errada volta **400**, não 401: o frontend trata todo 401 como
    sessão vencida e desloga.

    Raises:
        HTTPException 400: senha atual incorreta.
        HTTPException 422: senha nova fora de 8 caracteres a 72 bytes, ou igual à atual.
        HTTPException 409: ``settings.yaml`` não pôde ser gravado (texto fixo, sem trecho).
    """
    settings = get_settings()
    user = authenticate_user(settings.security, current_user, body.current_password)
    if user is None:
        logger.warning("Troca de senha recusada para '%s': senha atual incorreta.", current_user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta."
        )
    if not _password_in_range(body.new_password):
        raise HTTPException(
            status_code=422,
            detail=(
                f"A senha nova deve ter no mínimo {MIN_PASSWORD_CHARS} caracteres e no máximo "
                f"{MAX_PASSWORD_BYTES} bytes (letras com acento contam mais de um byte)."
            ),
        )
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=422, detail="A senha nova precisa ser diferente da atual."
        )
    config_path = get_config_path()
    try:
        provision_user(config_path, user.username, body.new_password, example_path=_EXAMPLE_PATH)
    except ConfigError:
        # A mensagem do ConfigError pode trazer trecho do arquivo (secret_key): fica fora.
        logger.error("Troca de senha: falha ao gravar %s.", config_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível gravar a senha nova. Peça ajuda ao responsável técnico.",
        ) from None
    logger.info("Senha trocada pelo próprio usuário '%s'.", user.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
