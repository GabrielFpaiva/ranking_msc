"""
ranking_msc.services.invite_email
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

E-mail do convite assinado: monta a mensagem (texto e HTML, em português) e a
envia pelo Gmail com senha de app (SMTP sobre TLS, ``smtp.gmail.com:465``).

O envio nunca levanta exceção: o convite continua válido mesmo que o e-mail
falhe, e quem chama mostra o código para a pessoa copiar. Nada sensível vai
para o log: nem o código, nem a senha de app, nem a mensagem do servidor (que
pode repeti-los); só o tipo do erro.
"""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
from collections.abc import Callable
from datetime import datetime
from email.message import EmailMessage
from types import TracebackType
from typing import Protocol, Self

from ranking_msc.services.invites import FUSO

logger = logging.getLogger("ranking_msc")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT_SECONDS = 20

SUBJECT = "Convite para o MCRA"

_MONTHS_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


class SmtpConnection(Protocol):
    """O que o envio usa de uma conexão SMTP (``smtplib.SMTP_SSL`` ou um falso de teste)."""

    def __enter__(self) -> Self:
        """Abre a conexão como gerenciador de contexto."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> None:
        """Fecha a conexão."""
        ...

    def login(self, user: str, password: str) -> object:
        """Autentica no servidor."""
        ...

    def send_message(self, msg: EmailMessage) -> object:
        """Envia a mensagem."""
        ...


SmtpConnectionFactory = Callable[..., SmtpConnection]
"""Chamada como ``factory(host, port, context=<SSLContext>, timeout=<segundos>)``."""


def format_deadline(expires_at: datetime) -> str:
    """Formata o fim da validade por extenso, no fuso de Recife.

    O nome do mês vem de tabela própria em português (sem ``locale``, que muda de
    máquina para máquina). Exemplo: ``17 de novembro de 2026, 09h00 (horário de Recife)``.

    Args:
        expires_at: instante do vencimento, com fuso.
    """
    local = expires_at.astimezone(FUSO)
    return (
        f"{local.day} de {_MONTHS_PT[local.month - 1]} de {local.year}, "
        f"{local.hour:02d}h{local.minute:02d} (horário de Recife)"
    )


def build_invite_message(
    *,
    sender: str,
    recipient: str,
    code: str,
    installer_url: str,
    expires_at: datetime,
) -> EmailMessage:
    """Monta o e-mail do convite, com texto puro e alternativa HTML.

    Args:
        sender: endereço de envio (a conta do Gmail).
        recipient: e-mail do convidado.
        code: código do convite (``MCRA1.…``).
        installer_url: link do instalador (a última release do GitHub).
        expires_at: fim da validade, com fuso.

    Returns:
        ``EmailMessage`` pronta para ``send_invite_email``.
    """
    deadline = format_deadline(expires_at)

    text = (
        "Olá,\n"
        "\n"
        "Você foi convidado(a) para usar o MCRA, o aplicativo que confere a MSC do mês "
        "contra as regras do Ranking SICONFI.\n"
        "\n"
        "1. Baixe o instalador do MCRA por este link e instale:\n"
        f"   {installer_url}\n"
        "\n"
        '2. Abra o MCRA e, na tela de entrada, clique em "Tenho um convite".\n'
        "\n"
        "3. Cole o código abaixo e escolha a sua senha. Você mesmo cria a senha: "
        "ninguém precisa saber dela.\n"
        "\n"
        "Código do convite:\n"
        f"{code}\n"
        "\n"
        f"O convite vale até {deadline}. Depois disso, peça um novo convite a quem "
        "convidou você.\n"
        "\n"
        "Este convite é pessoal: não encaminhe este e-mail.\n"
    )

    url_html = html.escape(installer_url, quote=True)
    page = (
        "<!doctype html>\n"
        '<html lang="pt-BR"><head><meta charset="utf-8"></head>\n'
        '<body style="font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">\n'
        "<p>Olá,</p>\n"
        "<p>Você foi convidado(a) para usar o MCRA, o aplicativo que confere a MSC do mês "
        "contra as regras do Ranking SICONFI.</p>\n"
        "<ol>\n"
        f'<li><a href="{url_html}">Baixe o instalador do MCRA</a> e instale.</li>\n'
        '<li>Abra o MCRA e, na tela de entrada, clique em <b>"Tenho um convite"</b>.</li>\n'
        "<li>Cole o código abaixo e escolha a sua senha. Você mesmo cria a senha: "
        "ninguém precisa saber dela.</li>\n"
        "</ol>\n"
        "<p><b>Código do convite:</b></p>\n"
        '<p style="font-family:Consolas,monospace;word-break:break-all;background:#f3f3f3;'
        f'padding:8px;">{html.escape(code)}</p>\n'
        f"<p>O convite vale até <b>{html.escape(deadline)}</b>. Depois disso, peça um novo "
        "convite a quem convidou você.</p>\n"
        "<p>Este convite é pessoal: não encaminhe este e-mail.</p>\n"
        "</body></html>\n"
    )

    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text)
    message.add_alternative(page, subtype="html")
    return message


def send_invite_email(
    message: EmailMessage,
    *,
    smtp_user: str,
    smtp_password: str,
    connection_factory: SmtpConnectionFactory | None = None,
) -> bool:
    """Envia o e-mail pelo Gmail (``smtp.gmail.com:465``, TLS com certificado verificado).

    Args:
        message: mensagem de ``build_invite_message``.
        smtp_user: conta do Gmail que envia.
        smtp_password: senha de app dessa conta.
        connection_factory: fábrica da conexão (padrão: ``smtplib.SMTP_SSL``);
            existe para os testes trocarem a rede por um servidor falso.

    Returns:
        ``True`` se o servidor aceitou a mensagem; ``False`` em qualquer falha
        (senha recusada, rede, prazo, certificado). Nunca levanta exceção.
    """
    factory: SmtpConnectionFactory = (
        connection_factory if connection_factory is not None else smtplib.SMTP_SSL
    )
    recipient = str(message["To"])
    try:
        with factory(
            SMTP_HOST,
            SMTP_PORT,
            context=ssl.create_default_context(),
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(message)
    except Exception as exc:  # qualquer falha vira False: o convite segue válido
        logger.warning(
            "Falha ao enviar o e-mail do convite para %s (%s).", recipient, type(exc).__name__
        )
        return False
    logger.info("E-mail do convite enviado para %s.", recipient)
    return True
