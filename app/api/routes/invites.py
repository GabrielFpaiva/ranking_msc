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
import threading
from collections.abc import Callable, Coroutine
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel

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
    InviteKeyMismatchError,
    InviteKeyPasswordError,
    InviteUsedError,
)
from ranking_msc.services.invite_email import build_invite_message, send_invite_email
from ranking_msc.services.invites import (
    MSG_INVALID_EMAIL,
    InviteConfig,
    InviteStore,
    IssuerConfig,
    decrypt_secret,
    is_valid_email,
    issue_invite,
    load_invite_config,
    load_public_key,
    normalize_email,
    verify_invite,
)
from ranking_msc.services.users import find_username, provision_user

logger = logging.getLogger("ranking_msc")

# O nome da constante do Starlette mudou entre versões (ENTITY → CONTENT): o número é estável.
_STATUS_422 = 422

_MSG_BAD_BODY = (
    "Os dados enviados estão incompletos ou em formato inesperado. "
    "Recarregue a página e tente de novo."
)


class _PortugueseValidationRoute(APIRoute):
    """Rota cujo 422 de corpo malformado vem em português, com ``detail`` em texto.

    Os campos do corpo são ``str`` sem restrição: quem valida o conteúdo é a própria
    rota (mensagem em português que diz o que fazer). Falta de campo, tipo errado e
    JSON quebrado caem aqui, em vez da lista em inglês do FastAPI.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Embrulha o handler padrão: ``RequestValidationError`` vira 422 em português."""
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                raise HTTPException(status_code=_STATUS_422, detail=_MSG_BAD_BODY) from None

        return handler


public_router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=_PortugueseValidationRoute)
router = APIRouter(prefix="/api/invites", tags=["invites"], route_class=_PortugueseValidationRoute)

_EXAMPLE_PATH: Path = PROJECT_ROOT / "config" / "settings.yaml.example"

# Um aceite por vez neste processo (o app desktop serve a API num processo só, com
# rotas síncronas em threads). Sem ele, dois aceites simultâneos do mesmo código
# passavam juntos pelo ``ensure_unused`` antes de qualquer ``mark_used``, e o convite
# de uso único criava a conta duas vezes.
_ACCEPT_LOCK = threading.Lock()

EmailSender = Callable[[EmailMessage, str, str], bool]
"""``sender(mensagem, usuário SMTP, senha de app) -> enviou?`` — trocado nos testes."""

MIN_PASSWORD_CHARS = 8
MAX_PASSWORD_BYTES = 72  # limite do bcrypt: além disso o hash levanta ValueError

_MSG_DISABLED = (
    "Os convites não estão ativados nesta versão do MCRA. "
    "Peça ao responsável técnico o instalador mais recente."
)
_MSG_FORBIDDEN = (
    "Você não tem permissão para convidar neste computador. Entre com a conta do "
    "responsável técnico, no computador onde a chave de convites foi instalada."
)
_MSG_CODE_EMPTY = "Cole o código do convite que veio no e-mail."
_MSG_PASSWORD = (
    f"A senha deve ter no mínimo {MIN_PASSWORD_CHARS} caracteres e no máximo "
    f"{MAX_PASSWORD_BYTES} bytes (letras com acento e símbolos contam mais de um byte). "
    "Escolha outra senha."
)
_MSG_KEY_PASSWORD_EMPTY = "Digite a senha da chave."
_MSG_SETTINGS = (
    "Não foi possível gravar a conta: o arquivo de configuração do MCRA está com problema. "
    "Peça ajuda ao responsável técnico."
)


# --------------------------------------------------------------------------- dependências


def get_invite_config(
    path: Path = Depends(get_invites_config_path),  # noqa: B008
) -> InviteConfig:
    """Carrega o ``invites.yaml``; arquivo ausente ou sem chave pública = desligado.

    ``invites.yaml`` ilegível levanta 409 com a mensagem (que diz o arquivo e o que
    fazer). As rotas que só decidem se o recurso aparece (``invite-status`` e
    ``capability``) não usam esta dependência: veja ``_usable_config``.
    """
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
    password: str


class AcceptOut(BaseModel):
    """Conta criada (ou com a senha trocada) pelo convite."""

    username: str
    password_reset: bool


class CapabilityOut(BaseModel):
    """O usuário logado pode emitir convites neste computador?"""

    can_invite: bool


class InviteIn(BaseModel):
    """Quem convidar e a senha da chave que autoriza a emissão."""

    email: str
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
    """Arquivo de convite ilegível ou em estado ruim: 409 com a mensagem.

    Só vale para os arquivos do convite (``invites.yaml``, ``invite_issuer.yaml``,
    ``invite_key.pem``, ``invites_used.json``): a mensagem deles já diz o arquivo e
    o que fazer, e nunca traz trecho de conteúdo secreto. 409 (e não 5xx) porque a
    tela mostra o texto da resposta em vez de "não foi possível conectar".
    """
    logger.error("Falha de configuração do convite: %s", exc)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _settings_error(path: Path, exc: ConfigError) -> HTTPException:
    """Falha ao gravar a conta no ``settings.yaml``: 409 com texto fixo.

    A mensagem do ``ConfigError`` traz um trecho do arquivo (o do PyYAML pode incluir
    o ``secret_key``): fica fora da resposta e do log, que registram só o tipo e o caminho.
    O status é 409, não 500, porque a tela trata todo 5xx como falha de conexão e a
    orientação ("peça ajuda ao responsável técnico") não chegaria à pessoa.
    """
    logger.error("Convite: falha ao gravar a conta em %s (%s).", path, type(exc).__name__)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_MSG_SETTINGS)


def _usable_config(path: Path) -> InviteConfig | None:
    """Config do ``invites.yaml`` para decidir se o recurso aparece; defeito = ``None``.

    ``invites.yaml`` ilegível ou chave pública que não é Ed25519 desligam o recurso
    (com um WARNING), em vez de dar 5xx ou de ligar um botão cujo aceite sempre falha.
    """
    try:
        config = load_invite_config(path)
        if config.enabled:
            load_public_key(config.public_key)
    except ConfigError as exc:
        logger.warning("Convites desligados nesta máquina: %s", exc)
        return None
    return config


def _issuer_for(user: str, config: InviteConfig, store: InviteStore) -> IssuerConfig | None:
    """Devolve o emissor se ``user`` pode convidar aqui; senão ``None``.

    As três condições da spec: chave pública configurada; ``invite_issuer.yaml``
    existe e o emissor dele é o usuário logado (comparação normalizada); e
    ``invite_key.pem`` existe.

    Raises:
        ConfigError: ``invite_issuer.yaml`` ilegível.
    """
    if not config.enabled:
        return None
    issuer = store.read_issuer()
    if issuer is None or issuer.email != normalize_email(user):
        return None
    if not store.has_private_key():
        return None
    return issuer


def _require_issuer(user: str, config: InviteConfig, store: InviteStore) -> IssuerConfig:
    """Como ``_issuer_for``, mas sem permissão levanta 403 e arquivo ilegível levanta 409."""
    try:
        issuer = _issuer_for(user, config, store)
    except ConfigError as exc:
        raise _config_error(exc) from exc
    if issuer is None:
        logger.warning("Convite: usuário '%s' sem permissão para convidar.", user)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_MSG_FORBIDDEN)
    return issuer


def _unprocessable(detail: str) -> HTTPException:
    """422 com ``detail`` em texto (a tela mostra a frase como está)."""
    return HTTPException(status_code=_STATUS_422, detail=detail)


def _password_in_range(password: str) -> bool:
    """Senha de 8 caracteres a 72 bytes em UTF-8 (limite do bcrypt).

    Texto que nem codifica em UTF-8 (``\\ud800`` solto no JSON) também fica de fora.
    """
    try:
        size = len(password.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return len(password) >= MIN_PASSWORD_CHARS and size <= MAX_PASSWORD_BYTES


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
    path: Path = Depends(get_invites_config_path),  # noqa: B008
) -> InviteStatusOut:
    """Retorna ``enabled=True`` quando há chave pública válida no ``invites.yaml``.

    ``invites.yaml`` ilegível ou chave pública malformada = ``enabled=False`` (WARNING
    no log): ligar o botão faria todo aceite falhar.
    """
    config = _usable_config(path)
    return InviteStatusOut(enabled=config is not None and config.enabled)


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
    O ``jti`` só é marcado como usado depois de a conta gravada; conferir o uso,
    gravar a conta e marcar o ``jti`` acontecem sob ``_ACCEPT_LOCK``, então dois
    aceites simultâneos do mesmo código não passam os dois (o segundo leva 409).

    Raises:
        HTTPException 422: código vazio, ou senha fora de 8 caracteres a 72 bytes.
        HTTPException 403: convites desligados nesta versão.
        HTTPException 400: código inválido. 410: vencido. 409: já usado aqui, ou
            arquivo de convite (``invites.yaml``, ``invites_used.json``) ilegível.
        HTTPException 500: ``settings.yaml`` com problema (texto fixo, sem trecho do arquivo).
    """
    if not body.code.strip():
        raise _unprocessable(_MSG_CODE_EMPTY)
    if not _password_in_range(body.password):
        raise _unprocessable(_MSG_PASSWORD)
    if not config.enabled:
        raise _refuse(status.HTTP_403_FORBIDDEN, "recurso desligado", _MSG_DISABLED)
    with _ACCEPT_LOCK:
        return _accept_locked(body, config, store)


def _accept_locked(body: AcceptIn, config: InviteConfig, store: InviteStore) -> AcceptOut:
    """Corpo do aceite, já sob ``_ACCEPT_LOCK``: confere, grava a conta e marca o uso."""
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
    except ConfigError as exc:
        raise _settings_error(config_path, exc) from None
    try:
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
    path: Path = Depends(get_invites_config_path),  # noqa: B008
    store: InviteStore = Depends(get_invite_store),  # noqa: B008
) -> CapabilityOut:
    """Verdadeiro só com chave pública, emissor igual ao logado e chave privada presente.

    Qualquer arquivo de convite com defeito (``invites.yaml``, chave pública malformada,
    ``invite_issuer.yaml``) dá ``can_invite=False`` com um WARNING: a pergunta é feita
    por todo usuário ao entrar, e não pode virar erro para quem nem é o emissor.
    """
    config = _usable_config(path)
    if config is None:
        return CapabilityOut(can_invite=False)
    try:
        issuer = _issuer_for(current_user, config, store)
    except ConfigError as exc:
        logger.warning("Convite: sem permissão para convidar, arquivo ilegível: %s", exc)
        return CapabilityOut(can_invite=False)
    return CapabilityOut(can_invite=issuer is not None)


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
        HTTPException 422: e-mail fora do padrão estrito, ou senha da chave vazia.
        HTTPException 400: senha da chave incorreta.
        HTTPException 409: a chave privada não é o par da chave pública da versão
            instalada (nada é emitido nem enviado), ou arquivo de convite ilegível.
    """
    issuer = _require_issuer(current_user, config, store)
    email = body.email.strip()
    if not is_valid_email(email):
        raise _unprocessable(MSG_INVALID_EMAIL)
    if not body.key_password:
        raise _unprocessable(_MSG_KEY_PASSWORD_EMPTY)
    try:
        invite = issue_invite(
            store.read_private_key(),
            body.key_password,
            email,
            issuer.email,
            validity_days=config.validity_days,
            expected_public_key=config.public_key,
        )
        smtp_password = decrypt_secret(issuer.smtp_password_encrypted, body.key_password)
    except InviteKeyPasswordError as exc:
        logger.warning("Convite: emissão recusada (senha da chave incorreta).")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InviteKeyMismatchError as exc:
        logger.warning("Convite: emissão recusada (a chave privada não é o par da pública).")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
