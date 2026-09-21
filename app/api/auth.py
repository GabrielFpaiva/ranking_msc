"""
app.api.auth
~~~~~~~~~~~~

Lógica de autenticação JWT para a API MCRA.

Funções puras sem dependências de FastAPI — testáveis isoladamente.
O binding FastAPI (OAuth2PasswordBearer, Depends) fica em deps.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from ranking_msc.config.settings import SecuritySettings, UserSettings

# Hash dummy usado quando o username não existe — garante que ambos os caminhos
# de falha (usuário ausente e senha errada) executem bcrypt, neutralizando o
# side channel de timing que permitiria enumerar usernames por latência.
_DUMMY_HASH: str = bcrypt.hashpw(b"dummy-timing-equalization", bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto claro bate com o hash bcrypt.

    Retorna False (em vez de propagar) se o hash estiver malformado — evita
    que um settings.yaml corrompido converta falha de config em HTTP 500.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """Gera hash bcrypt de uma senha (utilitário para setup de usuários)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def authenticate_user(
    settings: SecuritySettings,
    username: str,
    password: str,
) -> UserSettings | None:
    """Autentica usuário contra a lista de usuários do settings.

    Returns:
        ``UserSettings`` do usuário autenticado, ou ``None`` se credenciais inválidas.
    """
    user = find_user(settings, username)
    if user is None:
        verify_password(password, _DUMMY_HASH)  # equaliza timing — não autentica
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def find_user(settings: SecuritySettings, username: str) -> UserSettings | None:
    """Busca usuário por username na lista de usuários configurados.

    A comparação ignora maiúsculas e espaços nas pontas: o username é um e-mail,
    e quem digita ``Fulano@...`` ou cola com espaço não pode levar 401.
    """
    procurado = username.strip().casefold()
    for user in settings.users:
        if user.username.strip().casefold() == procurado:
            return user
    return None


def create_access_token(username: str, settings: SecuritySettings) -> str:
    """Cria JWT assinado com expiração configurada em settings.

    Args:
        username: subject do token.
        settings: configurações de segurança (secret_key, algorithm, expire).

    Returns:
        JWT serializado como string.
    """
    expire = datetime.now(tz=UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, object] = {"sub": username, "exp": expire}
    token: str = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token


def decode_token(token: str, settings: SecuritySettings) -> str:
    """Decodifica e valida JWT, retornando o username.

    Args:
        token: Bearer token recebido do cliente.
        settings: configurações de segurança.

    Returns:
        Username extraído do claim ``sub``.

    Raises:
        ValueError: se o token for inválido, expirado ou sem claim ``sub``.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError(f"Token JWT inválido: {exc}") from exc

    username: str | None = payload.get("sub")
    if not username:
        raise ValueError("Token JWT não contém claim 'sub'.")

    return username
