"""Testes do e-mail do convite (services.invite_email), com servidor SMTP falso."""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

import pytest

from ranking_msc.services import invite_email
from ranking_msc.services.invite_email import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_TIMEOUT_SECONDS,
    build_invite_message,
    format_deadline,
    send_invite_email,
)

CODIGO = "MCRA1.eyJ2IjoxfQ.SEGREDO-DO-CODIGO-1234567890"
SENHA_APP = "abcdwxyzabcdwxyz"
URL = "https://drive.google.com/drive/folders/PASTA-DO-INSTALADOR"
# 2026-11-17 12:00 UTC = 09:00 em Recife (UTC-3)
VENCE = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _mensagem(**kw: Any) -> EmailMessage:
    args: dict[str, Any] = {
        "sender": "envio@gmail.com",
        "recipient": "fulano@exemplo.com",
        "code": CODIGO,
        "installer_url": URL,
        "expires_at": VENCE,
    }
    args.update(kw)
    return build_invite_message(**args)


class _SmtpFalso:
    """Substituto de smtplib.SMTP_SSL: grava o que recebe e falha sob encomenda."""

    instances: list[_SmtpFalso] = []
    login_error: Exception | None = None
    send_error: Exception | None = None

    def __init__(self, host: str, port: int, *, context: ssl.SSLContext, timeout: float) -> None:
        self.host, self.port, self.context, self.timeout = host, port, context, timeout
        self.logged_in: tuple[str, str] | None = None
        self.sent: list[EmailMessage] = []
        self.closed = False
        type(self).instances.append(self)

    def __enter__(self) -> _SmtpFalso:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True

    def login(self, user: str, password: str) -> None:
        if type(self).login_error is not None:
            raise type(self).login_error
        self.logged_in = (user, password)

    def send_message(self, msg: EmailMessage) -> None:
        if type(self).send_error is not None:
            raise type(self).send_error
        self.sent.append(msg)


@pytest.fixture(autouse=True)
def _reset_falso() -> None:
    _SmtpFalso.instances = []
    _SmtpFalso.login_error = None
    _SmtpFalso.send_error = None


# --------------------------------------------------------------------------- data por extenso


class TestFormatDeadline:
    @pytest.mark.parametrize(
        ("mes", "nome"),
        [
            (1, "janeiro"),
            (2, "fevereiro"),
            (3, "março"),
            (4, "abril"),
            (5, "maio"),
            (6, "junho"),
            (7, "julho"),
            (8, "agosto"),
            (9, "setembro"),
            (10, "outubro"),
            (11, "novembro"),
            (12, "dezembro"),
        ],
    )
    def test_nome_do_mes_vem_da_tabela_em_portugues(self, mes: int, nome: str) -> None:
        """Cada um dos 12 meses sai por extenso em português (sem depender de locale)."""
        texto = format_deadline(datetime(2026, mes, 15, 15, 0, tzinfo=UTC))
        assert texto == f"15 de {nome} de 2026, 12h00 (horário de Recife)"

    def test_converte_para_o_fuso_de_recife_e_muda_o_dia(self) -> None:
        """02h00 UTC de 1º/12 ainda é 30/11 às 23h00 em Recife: o dia e o mês acompanham o fuso."""
        texto = format_deadline(datetime(2026, 12, 1, 2, 0, tzinfo=UTC))
        assert texto == "30 de novembro de 2026, 23h00 (horário de Recife)"

    def test_minutos_com_dois_digitos(self) -> None:
        """Minuto menor que 10 sai com zero à esquerda."""
        assert format_deadline(datetime(2026, 11, 17, 12, 5, tzinfo=UTC)).startswith(
            "17 de novembro de 2026, 09h05"
        )


# --------------------------------------------------------------------------- mensagem


class TestBuildInviteMessage:
    def test_cabecalhos(self) -> None:
        """Assunto em português, remetente e destinatário como informados."""
        msg = _mensagem()
        assert msg["Subject"] == "Convite para o MCRA"
        assert msg["From"] == "envio@gmail.com"
        assert msg["To"] == "fulano@exemplo.com"

    def test_texto_puro_tem_link_codigo_validade_e_senha_propria(self) -> None:
        """O texto traz link, código, validade por extenso e 'você mesmo cria a senha'."""
        corpo = _mensagem().get_body(("plain",)).get_content()  # type: ignore[union-attr]
        assert URL in corpo
        assert CODIGO in corpo
        assert "17 de novembro de 2026, 09h00 (horário de Recife)" in corpo
        assert "Tenho um convite" in corpo
        assert "você mesmo cria a senha" in corpo.lower()

    def test_html_alternativo_tem_o_mesmo_conteudo(self) -> None:
        """A parte HTML traz link clicável, código, validade e a frase da senha."""
        msg = _mensagem()
        assert msg.get_content_type() == "multipart/alternative"
        html = msg.get_body(("html",)).get_content()  # type: ignore[union-attr]
        assert f'href="{URL}"' in html
        assert CODIGO in html
        assert "17 de novembro de 2026, 09h00 (horário de Recife)" in html
        assert "você mesmo cria a senha" in html.lower()

    def test_html_escapa_o_link_e_o_texto_puro_fica_cru(self) -> None:
        """Link com '&' vira '&amp;' no HTML (e não quebra o atributo); no texto puro fica cru."""
        url = "https://x.example/p?a=1&b=2"
        msg = _mensagem(installer_url=url)
        html = msg.get_body(("html",)).get_content()  # type: ignore[union-attr]
        assert 'href="https://x.example/p?a=1&amp;b=2"' in html
        assert url in msg.get_body(("plain",)).get_content()  # type: ignore[union-attr]


# --------------------------------------------------------------------------- envio


class TestSendInviteEmail:
    def test_sucesso_envia_pelo_gmail_com_tls_verificado(self) -> None:
        """SMTP_SSL em smtp.gmail.com:465 com prazo e contexto que verifica certificado e nome."""
        msg = _mensagem()

        ok = send_invite_email(
            msg, smtp_user="envio@gmail.com", smtp_password=SENHA_APP, connection_factory=_SmtpFalso
        )

        assert ok is True
        (conexao,) = _SmtpFalso.instances
        assert (conexao.host, conexao.port) == ("smtp.gmail.com", 465)
        assert (SMTP_HOST, SMTP_PORT) == ("smtp.gmail.com", 465)
        assert conexao.timeout == SMTP_TIMEOUT_SECONDS
        assert 0 < conexao.timeout <= 60
        assert conexao.context.verify_mode == ssl.CERT_REQUIRED
        assert conexao.context.check_hostname is True
        assert conexao.logged_in == ("envio@gmail.com", SENHA_APP)
        assert conexao.sent == [msg]
        assert conexao.closed is True

    def test_padrao_e_o_smtp_ssl_da_stdlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sem conexão injetada, usa smtplib.SMTP_SSL (trocado aqui por um falso, sem rede)."""
        monkeypatch.setattr(invite_email.smtplib, "SMTP_SSL", _SmtpFalso)
        assert send_invite_email(_mensagem(), smtp_user="u", smtp_password=SENHA_APP) is True
        assert len(_SmtpFalso.instances) == 1

    def test_senha_recusada_devolve_false(self) -> None:
        """O Gmail recusa a senha de app → False, sem exceção, e nada é enviado."""
        _SmtpFalso.login_error = smtplib.SMTPAuthenticationError(535, b"Password not accepted")
        ok = send_invite_email(
            _mensagem(), smtp_user="u", smtp_password=SENHA_APP, connection_factory=_SmtpFalso
        )
        assert ok is False
        assert _SmtpFalso.instances[0].sent == []
        assert _SmtpFalso.instances[0].closed is True

    @pytest.mark.parametrize(
        "erro",
        [
            ConnectionRefusedError("recusada"),
            TimeoutError("estourou o prazo"),
            OSError("rede fora"),
            ssl.SSLCertVerificationError("certificado inválido"),
            smtplib.SMTPServerDisconnected("caiu"),
        ],
    )
    def test_erro_de_rede_ao_conectar_devolve_false(self, erro: Exception) -> None:
        """Falha ao abrir a conexão (rede, prazo, TLS) → False."""

        def fabrica(*_a: object, **_k: object) -> _SmtpFalso:
            raise erro

        ok = send_invite_email(
            _mensagem(), smtp_user="u", smtp_password=SENHA_APP, connection_factory=fabrica
        )
        assert ok is False

    def test_destinatario_recusado_devolve_false(self) -> None:
        """Erro do servidor no envio (destinatário recusado) → False."""
        _SmtpFalso.send_error = smtplib.SMTPRecipientsRefused({"fulano@exemplo.com": (550, b"no")})
        ok = send_invite_email(
            _mensagem(), smtp_user="u", smtp_password=SENHA_APP, connection_factory=_SmtpFalso
        )
        assert ok is False

    def test_log_de_falha_nao_traz_codigo_nem_senha(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mesmo que o erro do servidor repita a senha e o código, nenhum registro os contém."""
        _SmtpFalso.login_error = smtplib.SMTPAuthenticationError(
            535, f"recusou {SENHA_APP} e {CODIGO}".encode()
        )
        with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
            ok = send_invite_email(
                _mensagem(), smtp_user="envio@gmail.com", smtp_password=SENHA_APP,
                connection_factory=_SmtpFalso,
            )
        assert ok is False
        assert any(r.levelno >= logging.WARNING for r in caplog.records)
        texto = caplog.text + "".join(str(r.__dict__) for r in caplog.records)
        assert SENHA_APP not in texto
        assert CODIGO not in texto
        assert "SEGREDO-DO-CODIGO" not in texto

    def test_log_de_sucesso_nao_traz_codigo_nem_senha(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """O registro de sucesso também fica limpo."""
        with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
            send_invite_email(
                _mensagem(), smtp_user="envio@gmail.com", smtp_password=SENHA_APP,
                connection_factory=_SmtpFalso,
            )
        assert caplog.records
        assert SENHA_APP not in caplog.text
        assert "SEGREDO-DO-CODIGO" not in caplog.text
