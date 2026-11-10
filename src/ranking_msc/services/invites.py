"""
ranking_msc.services.invites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convite assinado por e-mail: quem tem a chave privada (o responsável técnico)
emite um código, e qualquer cópia do MCRA que conheça a chave pública
(``config/invites.yaml``) confere esse código sem servidor.

Formato do código (sem padding, base64url)::

    MCRA1.<payload JSON>.<assinatura Ed25519 do segmento do payload>

O payload é ``{"v":1,"email":…,"exp":<epoch s>,"iat":<epoch s>,"jti":<16 bytes
hex>,"by":<e-mail do emissor>}``. O e-mail é sempre normalizado com
``strip().casefold()``.

Segredos (decisão da spec do convite):

* a chave privada (PEM PKCS8 sem cifra, só em memória) é cifrada com a *senha da
  chave* pelo mesmo esquema da senha de app (``encrypt_secret``: Fernet, chave
  derivada por scrypt); o ``invite_key.pem`` guarda só esse token, nunca o PEM;
* a senha de app do Gmail é cifrada com a mesma senha da chave e do mesmo jeito,
  para nunca ficar em texto puro no disco;
* o código do convite, a senha da chave e a senha de app nunca vão para log
  nem para mensagem de exceção.

O relógio é sempre injetável (parâmetro ``now``, com fuso); sem ele vale o
relógio real em UTC. Datas de validade são expostas no fuso America/Recife.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ranking_msc.exceptions import (
    ConfigError,
    InviteError,
    InviteExpiredError,
    InviteInvalidError,
    InviteKeyMismatchError,
    InviteKeyPasswordError,
    InviteUsedError,
)

logger = logging.getLogger("ranking_msc")

FUSO = ZoneInfo("America/Recife")
"""Fuso das datas de validade mostradas à pessoa (o mesmo de ``app/api/uso_store.py``)."""

CODE_PREFIX = "MCRA1"
PAYLOAD_VERSION = 1
DEFAULT_VALIDITY_DAYS = 7
MIN_KEY_PASSWORD_LENGTH = 12

PRIVATE_KEY_FILENAME = "invite_key.pem"
ISSUER_FILENAME = "invite_issuer.yaml"
SENT_FILENAME = "invites_sent.jsonl"
USED_FILENAME = "invites_used.json"

_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
# Endereço estrito, só o endereço: sem nome, sem ponto e vírgula, sem sinais nas pontas.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16


# --------------------------------------------------------------------------- tipos


@dataclass(frozen=True)
class InviteConfig:
    """Configuração versionada do convite (``config/invites.yaml``)."""

    public_key: str
    installer_url: str
    validity_days: int

    @property
    def enabled(self) -> bool:
        """Verdadeiro quando há chave pública configurada; vazio = convites desligados."""
        return bool(self.public_key)


@dataclass(frozen=True)
class InvitePayload:
    """Conteúdo autenticado de um convite (já conferido por ``verify_invite``)."""

    email: str
    issued_by: str
    jti: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class IssuedInvite:
    """Resultado de ``issue_invite``: o código a entregar e o payload que ele carrega."""

    code: str
    payload: InvitePayload


@dataclass(frozen=True)
class IssuerConfig:
    """Conteúdo do ``invite_issuer.yaml``: quem emite e a conta de envio.

    ``smtp_password_encrypted`` é o resultado de ``encrypt_secret``; nunca a
    senha de app em texto puro.
    """

    email: str
    smtp_user: str
    smtp_password_encrypted: str


@dataclass(frozen=True)
class SentInvite:
    """Linha do ``invites_sent.jsonl``: um convite emitido neste computador (sem o código)."""

    email: str
    issued_at: datetime
    expires_at: datetime
    email_sent: bool


# --------------------------------------------------------------------------- utilidades


def normalize_email(email: str) -> str:
    """Normaliza o e-mail como o resto do sistema compara: ``strip().casefold()``."""
    return email.strip().casefold()


def is_valid_email(email: str) -> bool:
    """Indica se ``email`` (depois do ``strip``) é só um endereço ``algo@dominio.sufixo``.

    Recusa nome (``Fulano <a@b.co>``), ``;`` ou ``,`` colados de outro programa,
    ponto final, aspas, espaços e quebras de linha no meio. Quem chama grava o
    valor já limpo (``strip``); esta função não o altera.
    """
    return _EMAIL_RE.fullmatch(email.strip()) is not None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode_strict(text: str) -> bytes:
    """Decodifica base64url sem padding; alfabeto estranho ou tamanho impossível → ``ValueError``.

    ``urlsafe_b64decode`` descarta em silêncio os caracteres fora do alfabeto,
    por isso o alfabeto é conferido antes.
    """
    if not _B64URL_RE.fullmatch(text):
        raise ValueError("caractere fora do alfabeto base64url")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except binascii.Error as exc:
        raise ValueError("base64url com tamanho impossível") from exc


def _b64url_decode(text: str) -> bytes:
    """Decodifica um segmento do código; qualquer defeito vira ``InviteInvalidError``."""
    try:
        return _b64url_decode_strict(text)
    except ValueError as exc:
        raise InviteInvalidError(_MSG_INVALID) from exc


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Grava em arquivo temporário da mesma pasta e troca com ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporario = path.with_name(f".{path.name}.tmp")
    temporario.write_bytes(data)
    os.replace(temporario, path)


def _timestamp(moment: datetime) -> int:
    return int(moment.timestamp())


def _from_epoch(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=FUSO)


_MSG_INVALID = (
    "O código do convite é inválido. Copie o código inteiro, exatamente como veio "
    "no e-mail, ou peça um novo convite."
)
_MSG_EXPIRED = "O convite venceu. Peça um novo convite ao responsável técnico."
_MSG_KEY_PASSWORD = "Senha da chave incorreta. Confira a senha e tente de novo."
_MSG_KEY_MISMATCH = (
    "A chave de convites deste computador não é a da versão instalada. Instale a versão "
    "do MCRA gerada depois da troca da chave e tente de novo."
)

MSG_INVALID_EMAIL = "E-mail inválido. Digite só o endereço, sem nome, ponto e vírgula ou sinais."
"""Texto único para endereço fora do padrão (rota de emissão e CLI de instalação)."""


# --------------------------------------------------------------------------- configuração


def load_invite_config(path: Path) -> InviteConfig:
    """Lê o ``config/invites.yaml``.

    Arquivo ausente ou ``public_key`` vazio = recurso desligado, sem exceção. O
    arquivo ausente registra um ``WARNING`` com o caminho procurado (o
    instalador deveria trazê-lo); a chave vazia é o estado normal e fica em
    silêncio.

    Raises:
        ConfigError: YAML ilegível ou ``validity_days`` que não é inteiro positivo.
    """
    if not path.exists():
        logger.warning("Arquivo de convites não encontrado: %s (convites desligados).", path)
        return InviteConfig(public_key="", installer_url="", validity_days=DEFAULT_VALIDITY_DAYS)
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"O arquivo {path} deveria ser um mapa de chave e valor.")

    days = raw.get("validity_days", DEFAULT_VALIDITY_DAYS)
    if type(days) is not int or days <= 0:
        raise ConfigError(
            f"validity_days em {path} deve ser um número inteiro de dias maior que zero."
        )
    return InviteConfig(
        public_key=str(raw.get("public_key") or "").strip(),
        installer_url=str(raw.get("installer_url") or "").strip(),
        validity_days=days,
    )


# --------------------------------------------------------------------------- chaves e segredo


def generate_keypair(passphrase: str) -> tuple[bytes, str]:
    """Gera um par Ed25519.

    A chave privada é serializada (PEM PKCS8, sem cifra) só em memória e cifrada
    com ``encrypt_secret`` (scrypt + Fernet), o mesmo esquema da senha de app: o
    arquivo ``invite_key.pem`` nunca contém a chave em claro.

    Args:
        passphrase: senha da chave (mínimo de 12 caracteres), que cifra a chave privada.

    Returns:
        ``(conteúdo do invite_key.pem: token cifrado em ASCII, chave pública crua
        em base64)``.

    Raises:
        InviteError: senha da chave curta demais.
    """
    if len(passphrase) < MIN_KEY_PASSWORD_LENGTH:
        raise InviteError(
            f"A senha da chave precisa ter {MIN_KEY_PASSWORD_LENGTH} caracteres ou mais."
        )
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = encrypt_secret(pem.decode("ascii"), passphrase)
    return token.encode("ascii"), _public_key_b64(private.public_key())


def _public_key_b64(key: Ed25519PublicKey) -> str:
    return base64.b64encode(_raw_public_key(key)).decode("ascii")


def _raw_public_key(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def _load_private_key(blob: bytes, key_password: str) -> Ed25519PrivateKey:
    """Abre o conteúdo do ``invite_key.pem`` com a senha da chave.

    Raises:
        InviteKeyPasswordError: a senha da chave não abre o arquivo.
        ConfigError: arquivo corrompido, de formato desconhecido ou sem chave Ed25519.
    """
    try:
        token = blob.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _corrupt_secret(PRIVATE_KEY_FILENAME) from exc
    pem = decrypt_secret(token, key_password, source=PRIVATE_KEY_FILENAME)
    try:
        key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise _corrupt_secret(PRIVATE_KEY_FILENAME) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise _corrupt_secret(PRIVATE_KEY_FILENAME)
    return key


def load_public_key(public_key: str) -> Ed25519PublicKey:
    """Lê a chave pública Ed25519 (base64) do ``invites.yaml``.

    Raises:
        ConfigError: texto que não é base64 de uma chave Ed25519 de 32 bytes.
    """
    try:
        raw = base64.b64decode(public_key.strip(), validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (binascii.Error, ValueError) as exc:
        raise ConfigError(
            "A chave pública em config/invites.yaml é inválida. "
            "Peça ao responsável técnico para gerá-la de novo."
        ) from exc


def _fernet_for(passphrase: str, salt: bytes) -> Fernet:
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8"))))


def encrypt_secret(secret: str, passphrase: str) -> str:
    """Cifra ``secret`` com a senha da chave (Fernet, chave derivada por scrypt).

    Returns:
        ``<sal base64url>.<token Fernet>``, texto seguro para gravar em YAML.
    """
    salt = os.urandom(_SALT_BYTES)
    token = _fernet_for(passphrase, salt).encrypt(secret.encode("utf-8")).decode("ascii")
    return f"{_b64url_encode(salt)}.{token}"


def _corrupt_secret(source: str) -> ConfigError:
    """Erro de arquivo cifrado ilegível, com o nome do arquivo e o que fazer (sem conteúdo)."""
    return ConfigError(
        f"O arquivo {source} está corrompido ou em formato desconhecido. Restaure uma cópia "
        "dele ou refaça a configuração com `python scripts/setup_invites.py init --force`."
    )


def decrypt_secret(token: str, passphrase: str, *, source: str = ISSUER_FILENAME) -> str:
    """Decifra o resultado de ``encrypt_secret``.

    Args:
        token: texto cifrado.
        passphrase: senha da chave.
        source: nome do arquivo de onde o texto veio (só para a mensagem de erro).

    Raises:
        InviteKeyPasswordError: a senha da chave não abre o texto.
        ConfigError: o texto cifrado está corrompido (formato desconhecido).
    """
    partes = token.strip().split(".")
    if len(partes) != 2:
        raise _corrupt_secret(source)
    try:
        salt = _b64url_decode_strict(partes[0])
    except ValueError as exc:
        raise _corrupt_secret(source) from exc
    try:
        return _fernet_for(passphrase, salt).decrypt(partes[1].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError) as exc:
        raise InviteKeyPasswordError(_MSG_KEY_PASSWORD) from exc


# --------------------------------------------------------------------------- emitir e conferir


def issue_invite(
    private_key_pem: bytes,
    key_password: str,
    email: str,
    issuer_email: str,
    *,
    validity_days: int = DEFAULT_VALIDITY_DAYS,
    now: datetime | None = None,
    expected_public_key: str | None = None,
) -> IssuedInvite:
    """Emite um convite assinado para ``email``.

    Args:
        private_key_pem: conteúdo do ``invite_key.pem`` (o que ``generate_keypair`` devolve).
        key_password: senha da chave.
        email: e-mail do convidado (é normalizado).
        issuer_email: e-mail de quem convida (é normalizado; vai em ``by``).
        validity_days: validade em dias.
        now: instante da emissão, com fuso; padrão: o relógio real.
        expected_public_key: chave pública embutida na versão instalada
            (``invites.yaml``). Quando dada, a chave privada precisa ser o par
            dela: um convite assinado por outro par chegaria morto.

    Raises:
        InviteKeyPasswordError: senha da chave incorreta.
        InviteKeyMismatchError: a chave privada não é o par de ``expected_public_key``.
        ConfigError: arquivo da chave corrompido, ou ``expected_public_key`` inválida.
    """
    private = _load_private_key(private_key_pem, key_password)
    if expected_public_key is not None:
        expected = load_public_key(expected_public_key)
        if _raw_public_key(private.public_key()) != _raw_public_key(expected):
            raise InviteKeyMismatchError(_MSG_KEY_MISMATCH)
    moment = now if now is not None else datetime.now(tz=UTC)
    issued = _timestamp(moment)
    expires = _timestamp(moment + timedelta(days=validity_days))
    email_norm = normalize_email(email)
    issuer_norm = normalize_email(issuer_email)
    jti = secrets.token_hex(16)

    payload_json = json.dumps(
        {
            "v": PAYLOAD_VERSION,
            "email": email_norm,
            "exp": expires,
            "iat": issued,
            "jti": jti,
            "by": issuer_norm,
        },
        separators=(",", ":"),
    )
    segment = _b64url_encode(payload_json.encode("utf-8"))
    signature = _b64url_encode(private.sign(segment.encode("ascii")))
    return IssuedInvite(
        code=f"{CODE_PREFIX}.{segment}.{signature}",
        payload=InvitePayload(
            email=email_norm,
            issued_by=issuer_norm,
            jti=jti,
            issued_at=_from_epoch(issued),
            expires_at=_from_epoch(expires),
        ),
    )


def _epoch_datetime(value: object) -> datetime:
    """Converte o ``exp``/``iat`` do payload; o que não for inteiro de época vira inválido."""
    if type(value) is not int:  # bool também é int: `type is` o recusa
        raise InviteInvalidError(_MSG_INVALID)
    try:
        return _from_epoch(value)
    except (OverflowError, OSError, ValueError) as exc:
        raise InviteInvalidError(_MSG_INVALID) from exc


def _parse_payload(raw: bytes) -> InvitePayload:
    """Converte o JSON do payload; qualquer desvio do formato da spec vira inválido."""
    try:
        data: Any = json.loads(raw)
    except ValueError as exc:
        raise InviteInvalidError(_MSG_INVALID) from exc
    if not isinstance(data, dict):
        raise InviteInvalidError(_MSG_INVALID)
    email, by, jti = data.get("email"), data.get("by"), data.get("jti")
    version = data.get("v")
    if (
        type(version) is not int
        or version != PAYLOAD_VERSION
        or not isinstance(email, str)
        or not isinstance(by, str)
        or not isinstance(jti, str)
        or not jti
    ):
        raise InviteInvalidError(_MSG_INVALID)
    return InvitePayload(
        email=email,
        issued_by=by,
        jti=jti,
        issued_at=_epoch_datetime(data.get("iat")),
        expires_at=_epoch_datetime(data.get("exp")),
    )


def verify_invite(code: str, public_key: str, *, now: datetime | None = None) -> InvitePayload:
    """Confere um código colado: formato, assinatura e validade (nessa ordem).

    Todo espaço e quebra de linha do código sai antes da conferência. O ``jti``
    não é conferido aqui: quem aceita consulta ``InviteStore.ensure_unused``.

    Args:
        code: código como colado pela pessoa.
        public_key: chave pública Ed25519 em base64 (``config/invites.yaml``).
        now: instante da conferência, com fuso; padrão: o relógio real.

    Raises:
        InviteInvalidError: lixo, adulterado ou assinado por outra chave.
        InviteExpiredError: assinatura boa, mas ``exp`` anterior a ``now``.
        ConfigError: a chave pública configurada é inválida.
    """
    key = load_public_key(public_key)
    partes = "".join(code.split()).split(".")
    if len(partes) != 3 or partes[0] != CODE_PREFIX:
        raise InviteInvalidError(_MSG_INVALID)
    _, segment, signature = partes
    signature_bytes = _b64url_decode(signature)
    payload_bytes = _b64url_decode(segment)
    try:
        key.verify(signature_bytes, segment.encode("ascii"))
    except InvalidSignature as exc:
        raise InviteInvalidError(_MSG_INVALID) from exc

    payload = _parse_payload(payload_bytes)
    moment = now if now is not None else datetime.now(tz=UTC)
    if moment > payload.expires_at:
        raise InviteExpiredError(_MSG_EXPIRED)
    return payload


# --------------------------------------------------------------------------- guarda local


def _used_file_corrupt() -> ConfigError:
    return ConfigError(
        f"O arquivo {USED_FILENAME} está ilegível. Apague-o (convites já usados poderão "
        "ser aceitos de novo até vencer) ou peça ajuda ao responsável técnico."
    )


class InviteStore:
    """Arquivos de convite na pasta de config local (a do ``settings.yaml`` em uso).

    Nada daqui mora no ``settings.yaml``: ele é recriado do modelo quando faltam
    usuários, e isso apagaria a configuração do emissor.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @property
    def private_key_path(self) -> Path:
        """Chave privada cifrada (``invite_key.pem``)."""
        return self.directory / PRIVATE_KEY_FILENAME

    @property
    def issuer_path(self) -> Path:
        """Emissor e conta de envio (``invite_issuer.yaml``)."""
        return self.directory / ISSUER_FILENAME

    @property
    def sent_path(self) -> Path:
        """Convites emitidos aqui, sem o código (``invites_sent.jsonl``)."""
        return self.directory / SENT_FILENAME

    @property
    def used_path(self) -> Path:
        """Convites já aceitos neste computador (``invites_used.json``)."""
        return self.directory / USED_FILENAME

    # chave privada

    def has_private_key(self) -> bool:
        """Indica se o ``invite_key.pem`` existe."""
        return self.private_key_path.is_file()

    def write_private_key(self, pem: bytes) -> None:
        """Grava o PEM cifrado de forma atômica."""
        _atomic_write_bytes(self.private_key_path, pem)

    def read_private_key(self) -> bytes:
        """Lê o PEM cifrado (confira antes com ``has_private_key``)."""
        return self.private_key_path.read_bytes()

    # emissor

    def write_issuer(self, issuer: IssuerConfig) -> None:
        """Grava o ``invite_issuer.yaml`` (e-mail do emissor normalizado) de forma atômica."""
        issuer = replace(issuer, email=normalize_email(issuer.email))
        text = yaml.safe_dump(
            {
                "issuer": issuer.email,
                "smtp_user": issuer.smtp_user,
                "smtp_password_encrypted": issuer.smtp_password_encrypted,
            },
            allow_unicode=True,
            sort_keys=False,
        )
        _atomic_write_bytes(self.issuer_path, text.encode("utf-8"))

    def read_issuer(self) -> IssuerConfig | None:
        """Lê o ``invite_issuer.yaml``; ``None`` quando o arquivo não existe.

        Raises:
            ConfigError: arquivo ilegível ou sem algum dos três campos de texto.
        """
        if not self.issuer_path.exists():
            return None
        corrompido = ConfigError(
            f"O arquivo {ISSUER_FILENAME} está ilegível ou incompleto. "
            "Refaça a configuração com `python scripts/setup_invites.py init --force`."
        )
        try:
            raw: Any = yaml.safe_load(self.issuer_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, ValueError) as exc:
            raise corrompido from exc
        campos = ("issuer", "smtp_user", "smtp_password_encrypted")
        if not isinstance(raw, dict) or not all(isinstance(raw.get(c), str) for c in campos):
            raise corrompido
        return IssuerConfig(
            email=normalize_email(raw["issuer"]),
            smtp_user=raw["smtp_user"],
            smtp_password_encrypted=raw["smtp_password_encrypted"],
        )

    # convites emitidos

    def record_sent(self, invite: IssuedInvite, *, email_sent: bool) -> SentInvite:
        """Acrescenta uma linha ao ``invites_sent.jsonl``. O código não é gravado."""
        sent = SentInvite(
            email=invite.payload.email,
            issued_at=invite.payload.issued_at,
            expires_at=invite.payload.expires_at,
            email_sent=email_sent,
        )
        line = json.dumps(
            {
                "email": sent.email,
                "issued_at": sent.issued_at.isoformat(timespec="seconds"),
                "expires_at": sent.expires_at.isoformat(timespec="seconds"),
                "email_sent": sent.email_sent,
            },
            ensure_ascii=False,
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.sent_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        return sent

    def list_sent(self) -> list[SentInvite]:
        """Convites emitidos aqui, o mais recente primeiro.

        Linha ilegível (por exemplo, truncada por uma queda de energia no meio
        de um append) é pulada com um ``WARNING``: uma linha ruim não pode
        derrubar a tela. O aviso traz só o número da linha, nunca o conteúdo.
        """
        if not self.sent_path.exists():
            return []
        result: list[SentInvite] = []
        text = self.sent_path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                result.append(
                    SentInvite(
                        email=str(row["email"]),
                        issued_at=datetime.fromisoformat(row["issued_at"]),
                        expires_at=datetime.fromisoformat(row["expires_at"]),
                        email_sent=bool(row["email_sent"]),
                    )
                )
            except (ValueError, KeyError, TypeError):
                logger.warning(
                    "Linha %d de %s ilegível; ignorada na lista de convites.",
                    number,
                    SENT_FILENAME,
                )
        result.reverse()
        return result

    # convites usados

    def _read_used(self) -> dict[str, str]:
        """Lê o ``invites_used.json``; ilegível levanta ``ConfigError`` (sem regravar)."""
        if not self.used_path.exists():
            return {}
        try:
            used: Any = json.loads(self.used_path.read_text(encoding="utf-8"))
        except ValueError as exc:  # JSON inválido ou UTF-8 quebrado
            raise _used_file_corrupt() from exc
        if not isinstance(used, dict):
            raise _used_file_corrupt()
        return {str(k): str(v) for k, v in used.items()}

    def is_used(self, jti: str) -> bool:
        """Indica se o convite ``jti`` já foi aceito neste computador."""
        return jti in self._read_used()

    def ensure_unused(self, jti: str) -> None:
        """Levanta ``InviteUsedError`` se o convite ``jti`` já foi aceito aqui."""
        if self.is_used(jti):
            raise InviteUsedError(
                "Este convite já foi usado neste computador. Peça um novo convite "
                "ao responsável técnico."
            )

    def mark_used(self, jti: str, *, now: datetime | None = None) -> None:
        """Marca o convite ``jti`` como usado (gravação atômica do ``invites_used.json``)."""
        moment = now if now is not None else datetime.now(tz=UTC)
        used = self._read_used()
        used[jti] = moment.astimezone(FUSO).isoformat(timespec="seconds")
        text = json.dumps(used, indent=2, sort_keys=True)
        _atomic_write_bytes(self.used_path, text.encode("utf-8"))
