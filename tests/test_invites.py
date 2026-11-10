"""Testes do convite assinado (services.invites): código, chaves, segredo e guarda local."""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ranking_msc.exceptions import (
    ConfigError,
    InviteError,
    InviteExpiredError,
    InviteInvalidError,
    InviteKeyPasswordError,
    InviteUsedError,
    RankingMSCError,
)
from ranking_msc.services.invites import (
    FUSO,
    InviteConfig,
    InviteStore,
    IssuerConfig,
    decrypt_secret,
    encrypt_secret,
    generate_keypair,
    issue_invite,
    load_invite_config,
    normalize_email,
    verify_invite,
)

KEY_PASSWORD = "senha-da-chave-123"
AGORA = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@pytest.fixture(scope="module")
def keypair() -> tuple[bytes, str]:
    """Par descartável (PEM privado cifrado, chave pública base64), gerado uma vez."""
    return generate_keypair(KEY_PASSWORD)


def _emitir(keypair: tuple[bytes, str], email: str = "Fulano@Exemplo.com") -> str:
    pem, _ = keypair
    return issue_invite(pem, KEY_PASSWORD, email, "gabriel@exemplo.com", now=AGORA).code


def _assinar(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    """Monta um código com assinatura válida sobre um payload qualquer (cria casos de lixo)."""
    segmento = _b64(payload)
    assinatura = _b64(private_key.sign(segmento.encode("ascii")))
    return f"MCRA1.{segmento}.{assinatura}"


def _chave_publica(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.b64encode(raw).decode("ascii")


# --------------------------------------------------------------------------- config


class TestLoadInviteConfig:
    def test_arquivo_ausente_desliga_e_avisa_o_caminho(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sem o arquivo: recurso desligado, sem exceção, com WARNING do caminho procurado."""
        caminho = tmp_path / "invites.yaml"
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            cfg = load_invite_config(caminho)
        assert cfg.enabled is False
        assert any(str(caminho) in r.getMessage() for r in caplog.records)

    def test_chave_vazia_desliga_em_silencio(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """public_key vazio é o estado dormente: desligado e nenhum registro de log."""
        caminho = tmp_path / "invites.yaml"
        caminho.write_text(
            'public_key: ""\ninstaller_url: "https://x.example/p"\nvalidity_days: 7\n',
            encoding="utf-8",
        )
        with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
            cfg = load_invite_config(caminho)
        assert cfg == InviteConfig(
            public_key="", installer_url="https://x.example/p", validity_days=7
        )
        assert cfg.enabled is False
        assert caplog.records == []

    def test_chave_presente_liga(self, tmp_path: Path) -> None:
        """Com public_key preenchido o recurso fica ligado e lê link e validade."""
        caminho = tmp_path / "invites.yaml"
        caminho.write_text(
            'public_key: "AAAA"\ninstaller_url: "https://x.example/p"\nvalidity_days: 3\n',
            encoding="utf-8",
        )
        cfg = load_invite_config(caminho)
        assert cfg.enabled is True
        assert cfg.validity_days == 3
        assert cfg.public_key == "AAAA"

    def test_yaml_invalido_levanta_configerror(self, tmp_path: Path) -> None:
        """YAML ilegível é erro de configuração, não 'desligado'."""
        caminho = tmp_path / "invites.yaml"
        caminho.write_text("public_key: [invalido\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_invite_config(caminho)

    @pytest.mark.parametrize("dias", ["0", "-1", '"sete"', "7.5", "true"])
    def test_validade_invalida_levanta_configerror(self, tmp_path: Path, dias: str) -> None:
        """validity_days precisa ser inteiro positivo."""
        caminho = tmp_path / "invites.yaml"
        caminho.write_text(f'public_key: ""\nvalidity_days: {dias}\n', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_invite_config(caminho)


# --------------------------------------------------------------------------- chaves


class TestKeypair:
    def test_par_gerado_tem_pem_cifrado_e_publica_de_32_bytes(
        self, keypair: tuple[bytes, str]
    ) -> None:
        """A privada sai cifrada (PKCS8) e a pública é a Ed25519 crua em base64."""
        pem, publica = keypair
        assert pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
        assert len(base64.b64decode(publica, validate=True)) == 32

    def test_senha_da_chave_curta_levanta_inviteerror(self) -> None:
        """Senha da chave com menos de 12 caracteres é recusada."""
        with pytest.raises(InviteError):
            generate_keypair("12345678901")  # 11 caracteres

    def test_senha_de_12_caracteres_e_aceita(self) -> None:
        """No limite: 12 caracteres passam."""
        pem, _ = generate_keypair("123456789012")
        assert pem

    def test_emitir_com_senha_errada_levanta_keypassworderror(
        self, keypair: tuple[bytes, str]
    ) -> None:
        """Senha da chave incorreta na emissão → InviteKeyPasswordError."""
        pem, _ = keypair
        with pytest.raises(InviteKeyPasswordError):
            issue_invite(pem, "outra-senha-qualquer", "a@b.co", "g@b.co", now=AGORA)

    def test_excecoes_herdam_de_rankingmscerror(self) -> None:
        """As quatro exceções novas entram na hierarquia do projeto."""
        filhas = (InviteInvalidError, InviteExpiredError, InviteKeyPasswordError, InviteUsedError)
        for exc in filhas:
            assert issubclass(exc, InviteError)
        assert issubclass(InviteError, RankingMSCError)


# --------------------------------------------------------------------------- código


class TestEmitirEVerificar:
    def test_ida_e_volta_devolve_o_payload(self, keypair: tuple[bytes, str]) -> None:
        """Emitir e verificar devolve e-mail normalizado, emissor, jti e as datas."""
        _, publica = keypair
        pem, _ = keypair
        invite = issue_invite(pem, KEY_PASSWORD, "  Fulano@Exemplo.COM ", "Gabriel@Exemplo.com",
                              validity_days=7, now=AGORA)
        payload = verify_invite(invite.code, publica, now=AGORA)
        assert payload == invite.payload
        assert payload.email == "fulano@exemplo.com"
        assert payload.issued_by == "gabriel@exemplo.com"
        assert len(payload.jti) == 32
        int(payload.jti, 16)
        assert payload.issued_at == AGORA
        assert payload.expires_at == AGORA + timedelta(days=7)
        assert payload.expires_at.tzinfo == FUSO
        assert payload.expires_at.isoformat().endswith("-03:00")

    def test_formato_do_codigo_segue_a_spec(self, keypair: tuple[bytes, str]) -> None:
        """MCRA1.<payload>.<assinatura>, base64url sem padding, JSON com as seis chaves."""
        codigo = _emitir(keypair)
        prefixo, segmento, assinatura = codigo.split(".")
        assert prefixo == "MCRA1"
        assert "=" not in codigo and "+" not in codigo and "/" not in codigo
        assert len(_unb64(assinatura)) == 64
        payload = json.loads(_unb64(segmento))
        assert list(payload) == ["v", "email", "exp", "iat", "jti", "by"]
        assert payload["v"] == 1
        assert payload["iat"] == int(AGORA.timestamp())
        assert payload["exp"] == int(AGORA.timestamp()) + 7 * 86400
        assert payload["email"] == "fulano@exemplo.com"

    def test_assinatura_cobre_o_segmento_do_payload(self, keypair: tuple[bytes, str]) -> None:
        """A assinatura confere sobre o texto do segmento: trocar o e-mail e recodificar falha."""
        _, publica = keypair
        prefixo, segmento, assinatura = _emitir(keypair).split(".")
        payload = json.loads(_unb64(segmento))
        payload["email"] = "intruso@exemplo.com"
        segmento_novo = _b64(json.dumps(payload, separators=(",", ":")).encode())
        with pytest.raises(InviteInvalidError):
            verify_invite(f"{prefixo}.{segmento_novo}.{assinatura}", publica, now=AGORA)

    def test_assinatura_adulterada_levanta_invalid(self, keypair: tuple[bytes, str]) -> None:
        """Um byte da assinatura trocado → inválido."""
        _, publica = keypair
        prefixo, segmento, assinatura = _emitir(keypair).split(".")
        bruta = bytearray(_unb64(assinatura))
        bruta[0] ^= 0x01
        with pytest.raises(InviteInvalidError):
            verify_invite(f"{prefixo}.{segmento}.{_b64(bytes(bruta))}", publica, now=AGORA)

    def test_chave_publica_de_outro_par_levanta_invalid(self, keypair: tuple[bytes, str]) -> None:
        """Código de um par verificado com a pública de outro par → inválido."""
        _, outra_publica = generate_keypair(KEY_PASSWORD)
        with pytest.raises(InviteInvalidError):
            verify_invite(_emitir(keypair), outra_publica, now=AGORA)

    def test_chave_publica_malformada_levanta_configerror(self, keypair: tuple[bytes, str]) -> None:
        """Chave pública configurada com lixo é erro de configuração, não 'código inválido'."""
        with pytest.raises(ConfigError):
            verify_invite(_emitir(keypair), "isto-nao-e-base64!", now=AGORA)

    def test_vence_um_segundo_depois_do_exp(self, keypair: tuple[bytes, str]) -> None:
        """No segundo exato do exp ainda vale; um segundo depois, vencido."""
        _, publica = keypair
        codigo = _emitir(keypair)
        exp = AGORA + timedelta(days=7)
        verify_invite(codigo, publica, now=exp)
        with pytest.raises(InviteExpiredError):
            verify_invite(codigo, publica, now=exp + timedelta(seconds=1))

    def test_vencido_so_depois_da_assinatura(self, keypair: tuple[bytes, str]) -> None:
        """Código adulterado e vencido é 'inválido': a assinatura vem antes da validade."""
        _, publica = keypair
        prefixo, segmento, assinatura = _emitir(keypair).split(".")
        outra = "A" if assinatura[0] != "A" else "B"
        longe = AGORA + timedelta(days=30)
        with pytest.raises(InviteInvalidError):
            verify_invite(f"{prefixo}.{segmento}.{outra}{assinatura[1:]}", publica, now=longe)

    def test_relogio_padrao_e_o_real(self, keypair: tuple[bytes, str]) -> None:
        """Sem `now`, emitir e verificar usam o relógio real e o convite recém-emitido vale."""
        pem, publica = keypair
        invite = issue_invite(pem, KEY_PASSWORD, "a@b.co", "g@b.co")
        assert verify_invite(invite.code, publica).email == "a@b.co"

    def test_espacos_e_quebras_no_codigo_colado_saem(self, keypair: tuple[bytes, str]) -> None:
        """Quebra de linha do e-mail, espaços e tabs no meio do código não atrapalham."""
        _, publica = keypair
        codigo = _emitir(keypair)
        quebrado = "\r\n".join(codigo[i : i + 60] for i in range(0, len(codigo), 60))
        colado = f"  \n\t{quebrado[:30]} {quebrado[30:]}\n  "
        assert verify_invite(colado, publica, now=AGORA).email == "fulano@exemplo.com"

    @pytest.mark.parametrize(
        "lixo",
        [
            "",
            "   ",
            "abc",
            "MCRA1",
            "MCRA1.x",
            "MCRA1.x.y",
            "MCRA1.eyJ2IjoxfQ.AAAA",
            "MCRA1..",
            "MCRA2.eyJ2IjoxfQ.AAAA",
            "MCRA1.eyJ2IjoxfQ.AAAA.AAAA",
            "MCRA1.!!!.???",
            "MCRA1.é.é",
            "mcra1.eyJ2IjoxfQ.AAAA",
        ],
    )
    def test_lixo_colado_levanta_invalid_e_nunca_outra_excecao(
        self, keypair: tuple[bytes, str], lixo: str
    ) -> None:
        """Texto que não é código → InviteInvalidError, sempre."""
        _, publica = keypair
        with pytest.raises(InviteInvalidError):
            verify_invite(lixo, publica, now=AGORA)

    @pytest.mark.parametrize(
        "payload",
        [
            b"nao e json",
            b"\xff\xfe",
            b"[1,2,3]",
            b'"texto"',
            b"null",
            b'{"v":1}',
            b'{"v":2,"email":"a@b.co","exp":9999999999,"iat":1,"jti":"x","by":"g@b.co"}',
            b'{"v":1,"email":"a@b.co","exp":"amanha","iat":1,"jti":"x","by":"g@b.co"}',
            b'{"v":1,"email":"a@b.co","exp":true,"iat":1,"jti":"x","by":"g@b.co"}',
            b'{"v":1,"email":7,"exp":9999999999,"iat":1,"jti":"x","by":"g@b.co"}',
            b'{"v":1,"email":"a@b.co","exp":9999999999,"iat":1,"jti":"","by":"g@b.co"}',
            b'{"v":1,"email":"a@b.co","exp":9999999999,"iat":1,"jti":"x","by":null}',
            b'{"v":true,"email":"a@b.co","exp":9999999999,"iat":1,"jti":"x","by":"g@b.co"}',
            b'{"v":1,"email":"a@b.co","exp":99999999999999999999,"iat":1,"jti":"x","by":"g@b.co"}',
        ],
    )
    def test_payload_assinado_mas_malformado_levanta_invalid(self, payload: bytes) -> None:
        """Mesmo com assinatura válida, payload que não é o objeto da spec → inválido."""
        privada = Ed25519PrivateKey.generate()
        with pytest.raises(InviteInvalidError):
            verify_invite(_assinar(privada, payload), _chave_publica(privada), now=AGORA)

    def test_payload_assinado_bem_formado_e_aceito(self) -> None:
        """Contraprova do teste anterior: o objeto certo, assinado, passa."""
        privada = Ed25519PrivateKey.generate()
        payload = json.dumps(
            {"v": 1, "email": "a@b.co", "exp": int(AGORA.timestamp()) + 5, "iat": 1,
             "jti": "j1", "by": "g@b.co"}
        ).encode()
        resultado = verify_invite(_assinar(privada, payload), _chave_publica(privada), now=AGORA)
        assert resultado.jti == "j1"

    def test_mensagens_nao_vazam_o_codigo(self, keypair: tuple[bytes, str]) -> None:
        """A mensagem das exceções nunca traz o código colado."""
        _, publica = keypair
        codigo = _emitir(keypair)
        with pytest.raises(InviteExpiredError) as vencido:
            verify_invite(codigo, publica, now=AGORA + timedelta(days=30))
        with pytest.raises(InviteInvalidError) as invalido:
            verify_invite(codigo[:-3] + "AAA", publica, now=AGORA)
        for excecao in (vencido, invalido):
            assert codigo.split(".")[1] not in str(excecao.value)
            assert codigo.split(".")[2][:20] not in str(excecao.value)


class TestNormalizeEmail:
    def test_strip_e_casefold(self) -> None:
        """A normalização da spec: strip().casefold()."""
        assert normalize_email("  Fulano@X.COM\n") == "fulano@x.com"


# --------------------------------------------------------------------------- segredo


class TestSegredo:
    def test_ida_e_volta(self) -> None:
        """Cifrar e decifrar com a mesma senha devolve o texto."""
        token = encrypt_secret("senha de app 1234", KEY_PASSWORD)
        assert decrypt_secret(token, KEY_PASSWORD) == "senha de app 1234"

    def test_texto_cifrado_nao_contem_o_segredo_e_varia(self) -> None:
        """Nada de texto puro no resultado, e o sal faz duas cifras do mesmo texto diferirem."""
        a = encrypt_secret("abcdefghijklmnop", KEY_PASSWORD)
        b = encrypt_secret("abcdefghijklmnop", KEY_PASSWORD)
        assert "abcdefghijklmnop" not in a
        assert a != b
        assert a.split(".")[0] != b.split(".")[0]  # o sal é novo a cada cifra

    def test_senha_errada_levanta_keypassworderror(self) -> None:
        """Senha da chave errada na decifragem = a mesma exceção da chave privada."""
        token = encrypt_secret("segredo", KEY_PASSWORD)
        with pytest.raises(InviteKeyPasswordError):
            decrypt_secret(token, "senha-errada-123")

    @pytest.mark.parametrize("lixo", ["", "semponto", "a.b", "!!!.???"])
    def test_texto_cifrado_corrompido_levanta_configerror(self, lixo: str) -> None:
        """Arquivo corrompido não é 'senha errada': é erro de configuração."""
        with pytest.raises(ConfigError):
            decrypt_secret(lixo, KEY_PASSWORD)


# --------------------------------------------------------------------------- guarda local


class TestInviteStore:
    def test_chave_privada_ida_e_volta(self, tmp_path: Path, keypair: tuple[bytes, str]) -> None:
        """Grava e lê o PEM; has_private_key acompanha; a pasta é criada."""
        store = InviteStore(tmp_path / "estado" / "config")
        assert store.has_private_key() is False
        store.write_private_key(keypair[0])
        assert store.has_private_key() is True
        assert store.read_private_key() == keypair[0]
        assert store.private_key_path.name == "invite_key.pem"

    def test_emissor_ida_e_volta_sem_senha_de_app_em_texto_puro(self, tmp_path: Path) -> None:
        """O invite_issuer.yaml guarda e-mails e a senha de app só cifrada."""
        store = InviteStore(tmp_path)
        assert store.read_issuer() is None
        cifrada = encrypt_secret("abcd efgh ijkl mnop", KEY_PASSWORD)
        store.write_issuer(IssuerConfig("Gabriel@Exemplo.com", "envio@gmail.com", cifrada))
        lido = store.read_issuer()
        assert lido == IssuerConfig("gabriel@exemplo.com", "envio@gmail.com", cifrada)
        gravado = store.issuer_path.read_text(encoding="utf-8")
        assert "abcd efgh" not in gravado
        assert "issuer: gabriel@exemplo.com" in gravado  # normalizado já na gravação
        assert decrypt_secret(lido.smtp_password_encrypted, KEY_PASSWORD) == "abcd efgh ijkl mnop"

    def test_enviados_mais_recente_primeiro_e_sem_o_codigo(
        self, tmp_path: Path, keypair: tuple[bytes, str]
    ) -> None:
        """A lista volta do mais novo para o mais velho; o código nunca vai para o arquivo."""
        pem, _ = keypair
        store = InviteStore(tmp_path)
        assert store.list_sent() == []
        primeiro = issue_invite(pem, KEY_PASSWORD, "um@x.co", "g@x.co", now=AGORA)
        depois = AGORA + timedelta(hours=1)
        segundo = issue_invite(pem, KEY_PASSWORD, "dois@x.co", "g@x.co", now=depois)
        store.record_sent(primeiro, email_sent=True)
        store.record_sent(segundo, email_sent=False)

        lista = store.list_sent()
        assert [s.email for s in lista] == ["dois@x.co", "um@x.co"]
        assert [s.email_sent for s in lista] == [False, True]
        assert lista[1].issued_at == AGORA
        assert lista[1].expires_at == AGORA + timedelta(days=7)
        bruto = store.sent_path.read_text(encoding="utf-8")
        assert primeiro.code not in bruto and segundo.code not in bruto
        assert primeiro.code.split(".")[2] not in bruto
        assert primeiro.payload.jti not in bruto
        assert bruto.count("\n") == 2

    def test_usado_marca_e_recusa_de_novo(self, tmp_path: Path) -> None:
        """mark_used grava o jti; ensure_unused passa antes e levanta InviteUsedError depois."""
        store = InviteStore(tmp_path)
        store.ensure_unused("jti-1")
        assert store.is_used("jti-1") is False
        store.mark_used("jti-1", now=AGORA)
        assert store.is_used("jti-1") is True
        with pytest.raises(InviteUsedError):
            store.ensure_unused("jti-1")
        store.ensure_unused("jti-2")

    def test_usado_acumula_e_nao_deixa_temporario(self, tmp_path: Path) -> None:
        """Dois jti no mesmo arquivo, JSON válido, sem sobra de .tmp (gravação atômica)."""
        store = InviteStore(tmp_path)
        store.mark_used("a", now=AGORA)
        store.mark_used("b", now=AGORA)
        assert set(json.loads(store.used_path.read_text(encoding="utf-8"))) == {"a", "b"}
        assert sorted(p.name for p in tmp_path.iterdir()) == ["invites_used.json"]

    def test_enviados_pula_linha_ilegivel_e_avisa(
        self, tmp_path: Path, keypair: tuple[bytes, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Queda de energia no meio de um append deixa uma linha truncada: a lista segue."""
        pem, _ = keypair
        store = InviteStore(tmp_path)
        store.record_sent(issue_invite(pem, KEY_PASSWORD, "um@x.co", "g@x.co", now=AGORA),
                          email_sent=True)
        with store.sent_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write('{"email": "meio@x.co", "issued_at": "2026-11-10T09:00\n')  # truncada
            handle.write("[1, 2]\n")  # JSON válido, mas não é uma linha de convite
            handle.write('{"email": "sem-datas@x.co"}\n')  # faltam campos
        store.record_sent(issue_invite(pem, KEY_PASSWORD, "dois@x.co", "g@x.co", now=AGORA),
                          email_sent=False)

        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            lista = store.list_sent()

        assert [s.email for s in lista] == ["dois@x.co", "um@x.co"]
        avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(avisos) == 3
        assert all("invites_sent.jsonl" in r.getMessage() for r in avisos)
        assert "meio@x.co" not in caplog.text

    def test_enviados_com_bytes_invalidos_na_linha_nao_derruba(self, tmp_path: Path) -> None:
        """Um UTF-8 cortado no meio (queda de energia) também é só uma linha ilegível."""
        store = InviteStore(tmp_path)
        store.directory.mkdir(parents=True, exist_ok=True)
        store.sent_path.write_bytes(b'{"email": "\xc3\n')
        assert store.list_sent() == []

    @pytest.mark.parametrize("conteudo", ["{", "[1, 2]", '"texto"', "\x00\x00"])
    def test_usado_ilegivel_levanta_configerror_com_o_nome_do_arquivo(
        self, tmp_path: Path, conteudo: str
    ) -> None:
        """invites_used.json corrompido não vira erro cru, e nada é regravado por cima."""
        store = InviteStore(tmp_path)
        store.used_path.write_text(conteudo, encoding="utf-8")
        with pytest.raises(ConfigError, match="invites_used.json"):
            store.is_used("a")
        with pytest.raises(ConfigError, match="invites_used.json"):
            store.ensure_unused("a")
        with pytest.raises(ConfigError, match="invites_used.json"):
            store.mark_used("a", now=AGORA)
        assert store.used_path.read_text(encoding="utf-8") == conteudo

    @pytest.mark.parametrize(
        "conteudo",
        ["issuer: [", "- a\n- b\n", "issuer: g@x.co\nsmtp_user: e@x.co\n", "issuer: 1\n"],
    )
    def test_emissor_ilegivel_levanta_configerror_com_o_nome_do_arquivo(
        self, tmp_path: Path, conteudo: str
    ) -> None:
        """invite_issuer.yaml corrompido ou incompleto levanta ConfigError com o nome dele."""
        store = InviteStore(tmp_path)
        store.issuer_path.write_text(conteudo, encoding="utf-8")
        with pytest.raises(ConfigError, match="invite_issuer.yaml"):
            store.read_issuer()
