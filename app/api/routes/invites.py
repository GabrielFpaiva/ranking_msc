"""
app.api.routes.invites
~~~~~~~~~~~~~~~~~~~~~~

Convite assinado por e-mail (spec ``2026-11-10-convite-assinado``).

Públicas (RM-13: o convidado ainda não tem conta; a prova é a assinatura Ed25519):

GET  /api/auth/invite-status  — indica se os convites estão ligados (há chave pública).
POST /api/auth/invite/accept  — aceita um código: cria a conta ou troca a senha.

Com login (só quem é o emissor, no computador que tem a chave):

GET  /api/invites/capability  — o usuário logado pode convidar?
POST /api/invites             — emite um convite e o envia por e-mail.
GET  /api/invites             — convites emitidos neste computador.

Nunca vai para log: o código do convite, a senha da chave, a senha de app e a senha
nova do convidado.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from email.message import EmailMessage
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from app.api.deps import (
    PROJECT_ROOT,
    get_config_path,
    get_current_user,
    get_invites_config_path,
)
from ranking_msc.exceptions import (
    ConfigError,
    InviteExpiredError,
    InviteInvalidError,
    InviteKeyPasswordError,
    InviteUsedError,
)
from ranking_msc.services.invite_email import build_invite_message, send_invite_email
from ranking_msc.services.invites import (
    InviteConfig,
    InviteStore,
    IssuerConfig,
    decrypt_secret,
    issue_invite,
    load_invite_config,
    normalize_email,
    verify_invite,
)
from ranking_msc.services.users import find_username, provision_user

logger = logging.getLogger("ranking_msc")

public_router = APIRouter(prefix="/api/auth", tags=["auth"])
router = APIRouter(prefix="/api/invites", tags=["invites"])

_EXAMPLE_PATH: Path = PROJECT_ROOT / "config" / "settings.yaml.example"

# Sem EmailStr (o email_validator não é dependência): algo@algo.algo, sem espaço.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
EmailText = Annotated[str, StringConstraints(strip_whitespace=True, pattern=_EMAIL_PATTERN)]

EmailSender = Callable[[EmailMessage, str, str], bool]
"""``sender(mensagem, usuário SMTP, senha de app) -> enviou?`` — trocado nos testes."""

_MSG_DISABLED = (
    "Os convites não estão ativados nesta versão do MCRA. "
    "Peça ao responsável técnico o instalador mais recente."
)
_MSG_FORBIDDEN = (
    "Você não tem permissão para convidar neste computador. Entre com a conta do "
    "responsável técnico, no computador onde a chave de convites foi instalada."
)


# --------------------------------------------------------------------------- dependências


def get_invite_config(
    path: Path = Depends(get_invites_config_path),  # noqa: B008
) -> InviteConfig:
    """Carrega o ``invites.yaml``; arquivo ausente ou sem chave pública = desligado."""
    try:
        return load_invite_config(path)
    except ConfigError as exc:
        raise _config_error(exc) from exc


def get_invite_store() -> InviteStore:
    """Arquivos de convite na pasta de config local (a do ``settings.yaml`` em uso)."""
    return InviteStore(get_config_path().parent)


def get_email_sender() -> EmailSender:
    """Envio real do e-mail (Gmail); os testes trocam por um falso, sem rede."""

    def _send(message: EmailMessage, smtp_user: str, smtp_password: str) -> bool:
        return send_invite_email(message, smtp_user=smtp_user, smtp_password=smtp_password)

    return _send


# --------------------------------------------------------------------------- modelos


class InviteStatusOut(BaseModel):
    """Indica se os convites estão ligados nesta versão do MCRA."""

    enabled: bool


class AcceptIn(BaseModel):
    """Código colado pela pessoa e a senha que ela escolheu."""

    code: str
    password: str = Field(min_length=8, max_length=128)


class AcceptOut(BaseModel):
    """Conta criada (ou com a senha trocada) pelo convite."""

    username: str
    password_reset: bool


class CapabilityOut(BaseModel):
    """O usuário logado pode emitir convites neste computador?"""

    can_invite: bool


class InviteIn(BaseModel):
    """Quem convidar e a senha da chave que autoriza a emissão."""

    email: EmailText
    key_password: str


class InviteOut(BaseModel):
    """Convite emitido: ``code`` volta sempre, para a tela mostrar se o envio falhar."""

    email: str
    expires_at: str
    email_sent: bool
    code: str


class SentInviteOut(BaseModel):
    """Um convite já emitido neste computador (sem o código)."""

    email: str
    issued_at: str
    expires_at: str
    email_sent: bool


# --------------------------------------------------------------------------- auxiliares


def _config_error(exc: ConfigError) -> HTTPException:
    """Arquivo de convite ilegível: 500 com a mensagem (que já diz o arquivo e o que fazer)."""
    logger.error("Falha de configuração do convite: %s", exc)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _issuer_for(user: str, config: InviteConfig, store: InviteStore) -> IssuerConfig | None:
    """Devolve o emissor se ``user`` pode convidar aqui; senão ``None``.

    As três condições da spec: chave pública configurada; ``invite_issuer.yaml``
    existe e o emissor dele é o usuário logado (comparação normalizada); e
    ``invite_key.pem`` existe.
    """
    if not config.enabled:
        return None
    try:
        issuer = store.read_issuer()
    except ConfigError as exc:
        raise _config_error(exc) from exc
    if issuer is None or issuer.email != normalize_email(user):
        return None
    if not store.has_private_key():
        return None
    return issuer


def _require_issuer(user: str, config: InviteConfig, store: InviteStore) -> IssuerConfig:
    """Como ``_issuer_for``, mas sem permissão levanta 403."""
    issuer = _issuer_for(user, config, store)
    if issuer is None:
        logger.warning("Convite: usuário '%s' sem permissão para convidar.", user)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_MSG_FORBIDDEN)
    return issuer


def _refuse(code: int, reason: str, detail: str) -> HTTPException:
    """Recusa de aceite: WARNING com o motivo (nunca o código) e a exceção HTTP."""
    logger.warning("Convite recusado: %s.", reason)
    return HTTPException(status_code=code, detail=detail)


# --------------------------------------------------------------------------- rotas públicas


@public_router.get(
    "/invite-status",
    response_model=InviteStatusOut,
    summary="Indica se os convites estão ligados",
)
def invite_status(
    config: InviteConfig = Depends(get_invite_config),  # noqa: B008
) -> InviteStatusOut:
    """Retorna ``enabled=True`` quando há chave pública no ``invites.yaml``."""
    return InviteStatusOut(enabled=config.enabled)


@public_router.post(
    "/invite/accept",
    response_model=AcceptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Aceita um convite: cria a conta ou troca a senha",
)
def accept_invite(
    body: AcceptIn,
    config: InviteConfig = Depends(get_invite_config),  # noqa: B008
    store: InviteStore = Depends(get_invite_store),  # noqa: B008
) -> AcceptOut:
    """Confere o código (assinatura, validade, uso) e grava a conta do e-mail convidado.

    Se o e-mail já tem conta neste computador, a senha dela é trocada (usando o
    ``username`` como está gravado); senão a conta nasce com o e-mail normalizado.
    O ``jti`` só é marcado como usado depois de a conta gravada.

    Raises:
        HTTPException 403: convites desligados nesta versão.
        HTTPException 400: código inválido. 410: vencido. 409: já usado aqui.
    """
    if not config.enabled:
        raise _refuse(status.HTTP_403_FORBIDDEN, "recurso desligado", _MSG_DISABLED)
    try:
        payload = verify_invite(body.code, config.public_key)
        store.ensure_unused(payload.jti)
    except InviteInvalidError as exc:
        raise _refuse(status.HTTP_400_BAD_REQUEST, "código inválido", str(exc)) from exc
    except InviteExpiredError as exc:
        raise _refuse(status.HTTP_410_GONE, "código vencido", str(exc)) from exc
    except InviteUsedError as exc:
        raise _refuse(status.HTTP_409_CONFLICT, "código já usado", str(exc)) from exc
    except ConfigError as exc:
        raise _config_error(exc) from exc

    config_path = get_config_path()
    existing = find_username(config_path, payload.email)
    username = existing if existing is not None else normalize_email(payload.email)
    password_reset = existing is not None
    try:
        provision_user(config_path, username, body.password, example_path=_EXAMPLE_PATH)
        store.mark_used(payload.jti)
    except ConfigError as exc:
        raise _config_error(exc) from exc

    logger.info(
        "Convite aceito: e-mail=%s jti=%s password_reset=%s",
        normalize_email(payload.email),
        payload.jti,
        password_reset,
    )
    return AcceptOut(username=username, password_reset=password_reset)


# --------------------------------------------------------------------------- rotas com login


@router.get(
    "/capability",
    response_model=CapabilityOut,
    summary="O usuário logado pode convidar neste computador?",
)
def capability(
    current_user: str = Depends(get_current_user),  # noqa: B008
    config: InviteConfig = Depends(get_invite_config),  # noqa: B008
    store: InviteStore = Depends(get_invite_store),  # noqa: B008
) -> CapabilityOut:
    """Verdadeiro só com chave pública, emissor igual ao logado e chave privada presente."""
    return CapabilityOut(can_invite=_issuer_for(current_user, config, store) is not None)


@router.post(
    "",
    response_model=InviteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Emite um convite e o envia por e-mail",
)
def create_invite(
    body: InviteIn,
    current_user: str = Depends(get_current_user),  # noqa: B008
    config: InviteConfig = Depends(get_invite_config),  # noqa: B008
    store: InviteStore = Depends(get_invite_store),  # noqa: B008
    send_email: EmailSender = Depends(get_email_sender),  # noqa: B008
) -> InviteOut:
    """Assina o convite com a chave privada, envia o e-mail e registra a emissão.

    O envio pode falhar sem invalidar o convite: ``email_sent`` fica falso e a
    tela mostra o ``code`` para a pessoa copiar.

    Raises:
        HTTPException 403: sem permissão (não é o emissor, ou falta a chave).
        HTTPException 400: senha da chave incorreta.
    """
    issuer = _require_issuer(current_user, config, store)
    try:
        invite = issue_invite(
            store.read_private_key(),
            body.key_password,
            body.email,
            issuer.email,
            validity_days=config.validity_days,
        )
        smtp_password = decrypt_secret(issuer.smtp_password_encrypted, body.key_password)
    except InviteKeyPasswordError as exc:
        logger.warning("Convite: emissão recusada (senha da chave incorreta).")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ConfigError as exc:
        raise _config_error(exc) from exc

    message = build_invite_message(
        sender=issuer.smtp_user,
        recipient=invite.payload.email,
        code=invite.code,
        installer_url=config.installer_url,
        expires_at=invite.payload.expires_at,
    )
    email_sent = send_email(message, issuer.smtp_user, smtp_password)
    store.record_sent(invite, email_sent=email_sent)
    logger.info(
        "Convite emitido: e-mail=%s jti=%s email_sent=%s",
        invite.payload.email,
        invite.payload.jti,
        email_sent,
    )
    return InviteOut(
        email=invite.payload.email,
        expires_at=invite.payload.expires_at.isoformat(timespec="seconds"),
        email_sent=email_sent,
        code=invite.code,
    )


@router.get(
    "",
    response_model=list[SentInviteOut],
    summary="Convites emitidos neste computador",
)
def list_invites(
    current_user: str = Depends(get_current_user),  # noqa: B008
    config: InviteConfig = Depends(get_invite_config),  # noqa: B008
    store: InviteStore = Depends(get_invite_store),  # noqa: B008
) -> list[SentInviteOut]:
    """Lista os convites emitidos aqui, o mais recente primeiro (sem o código).

    Raises:
        HTTPException 403: sem permissão para convidar neste computador.
    """
    _require_issuer(current_user, config, store)
    return [
        SentInviteOut(
            email=sent.email,
            issued_at=sent.issued_at.isoformat(timespec="seconds"),
            expires_at=sent.expires_at.isoformat(timespec="seconds"),
            email_sent=sent.email_sent,
        )
        for sent in store.list_sent()
    ]
