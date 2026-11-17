"""Testes das rotas do convite assinado (app/api/routes/invites.py).

Cada teste roda isolado: ``RANKING_MSC_CONFIG`` aponta para um ``tmp_path`` (a pasta de
estado do convite é a do ``settings.yaml``), o caminho do ``invites.yaml`` é trocado por
dependência e o envio do e-mail é um falso que só guarda a chamada. Nenhum teste abre rede
nem lê/escreve o ``config/invites.yaml`` versionado. As chaves são descartáveis.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import app.api.routes.invites as invites_route
import pytest
import yaml
from app.api.deps import get_current_user, get_invites_config_path
from app.api.main import app
from app.api.routes.invites import get_email_sender
from fastapi.testclient import TestClient

from ranking_msc.services.invites import (
    InviteStore,
    IssuerConfig,
    encrypt_secret,
    generate_keypair,
    issue_invite,
    verify_invite,
)
from ranking_msc.services.users import provision_user

_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"

KEY_PASSWORD = "senha-da-chave-123"
APP_PASSWORD = "abcd efgh ijkl mnop"
SENHA_NOVA = "senha-nova-do-convidado-9"
EMISSOR = "gabriel@exemplo.com"
SMTP_USER = "envio@gmail.com"
INSTALLER_URL = "https://drive.example/pasta-do-instalador"


@dataclass
class EnvioFalso:
    """Substitui o envio por SMTP: guarda cada chamada e devolve ``ok``."""

    ok: bool = True
    chamadas: list[tuple[EmailMessage, str, str]] = field(default_factory=list)

    def __call__(self, message: EmailMessage, smtp_user: str, smtp_password: str) -> bool:
        self.chamadas.append((message, smtp_user, smtp_password))
        return self.ok


@dataclass
class Ambiente:
    """Tudo o que um teste de convite precisa, isolado em ``tmp_path``."""

    client: TestClient
    state_dir: Path
    config_path: Path
    invites_path: Path
    pem: bytes
    public_key: str
    envio: EnvioFalso

    @property
    def store(self) -> InviteStore:
        return InviteStore(self.state_dir)

    def como(self, usuario: str) -> None:
        """Faz as rotas com login enxergarem ``usuario`` como o usuário logado."""
        app.dependency_overrides[get_current_user] = lambda: usuario

    def sem_login(self) -> None:
        """Remove o bypass de login do conftest: sem token, as rotas protegidas dão 401."""
        app.dependency_overrides.pop(get_current_user, None)

    def desligar(self) -> None:
        """Deixa o ``invites.yaml`` sem chave pública (recurso dormente)."""
        _escrever_invites(self.invites_path, "")

    def configurar_emissor(self, email: str = EMISSOR, *, com_chave: bool = True) -> None:
        """Grava ``invite_issuer.yaml`` (senha de app cifrada) e, se pedido, a chave privada."""
        self.store.write_issuer(
            IssuerConfig(email, SMTP_USER, encrypt_secret(APP_PASSWORD, KEY_PASSWORD))
        )
        if com_chave:
            self.store.write_private_key(self.pem)

    def codigo(
        self, email: str = "Fulano@Exemplo.com", *, emitido_ha: timedelta = timedelta(0)
    ) -> str:
        """Emite um código válido direto pelo serviço (sem passar pela rota de emissão)."""
        return issue_invite(
            self.pem, KEY_PASSWORD, email, EMISSOR, now=datetime.now(tz=UTC) - emitido_ha
        ).code

    def aceitar(self, code: str, password: str = SENHA_NOVA):  # noqa: ANN201
        return self.client.post(
            "/api/auth/invite/accept", json={"code": code, "password": password}
        )


def _escrever_invites(path: Path, public_key: str, validity_days: int = 7) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "public_key": public_key,
                "installer_url": INSTALLER_URL,
                "validity_days": validity_days,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def keypair() -> tuple[bytes, str]:
    """Par descartável (PEM privado cifrado, chave pública base64), gerado uma vez."""
    return generate_keypair(KEY_PASSWORD)


@pytest.fixture
def ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keypair: tuple[bytes, str]
) -> Iterator[Ambiente]:
    """Config e estado em ``tmp_path``; ``invites.yaml`` ligado; envio falso; login "test-user"."""
    state_dir = tmp_path / "estado"
    state_dir.mkdir()
    config_path = state_dir / "settings.yaml"
    config_path.write_text(_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("RANKING_MSC_CONFIG", str(config_path))

    pem, public_key = keypair
    invites_path = tmp_path / "invites.yaml"
    _escrever_invites(invites_path, public_key)
    envio = EnvioFalso()
    app.dependency_overrides[get_invites_config_path] = lambda: invites_path
    app.dependency_overrides[get_email_sender] = lambda: envio

    yield Ambiente(
        client=TestClient(app),
        state_dir=state_dir,
        config_path=config_path,
        invites_path=invites_path,
        pem=pem,
        public_key=public_key,
        envio=envio,
    )

    app.dependency_overrides.pop(get_invites_config_path, None)
    app.dependency_overrides.pop(get_email_sender, None)
    # Restaura o bypass global do conftest (como tests/test_api_auth.py).
    app.dependency_overrides[get_current_user] = lambda: "test-user"


# --------------------------------------------------------------------------- invite-status


class TestInviteStatus:
    def test_com_chave_publica_esta_habilitado(self, ambiente: Ambiente) -> None:
        """Há chave pública no invites.yaml → enabled verdadeiro."""
        resposta = ambiente.client.get("/api/auth/invite-status")
        assert resposta.status_code == 200
        assert resposta.json() == {"enabled": True}

    def test_sem_chave_publica_esta_desligado(self, ambiente: Ambiente) -> None:
        """Recurso dormente → enabled falso."""
        ambiente.desligar()
        assert ambiente.client.get("/api/auth/invite-status").json() == {"enabled": False}

    def test_arquivo_ausente_esta_desligado(self, ambiente: Ambiente) -> None:
        """Sem invites.yaml o recurso fica desligado, sem erro."""
        ambiente.invites_path.unlink()
        resposta = ambiente.client.get("/api/auth/invite-status")
        assert resposta.status_code == 200
        assert resposta.json() == {"enabled": False}

    def test_e_publica_nao_pede_login(self, ambiente: Ambiente) -> None:
        """O convidado ainda não tem conta: a rota responde sem token."""
        ambiente.sem_login()
        assert ambiente.client.get("/api/auth/invite-status").status_code == 200

    def test_yaml_invalido_desliga_e_avisa_em_vez_de_500(
        self, ambiente: Ambiente, caplog: pytest.LogCaptureFixture
    ) -> None:
        """invites.yaml quebrado: o botão não aparece (enabled falso) e o log tem um WARNING."""
        ambiente.invites_path.write_text("public_key: [\n", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            resposta = ambiente.client.get("/api/auth/invite-status")
        assert resposta.status_code == 200
        assert resposta.json() == {"enabled": False}
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    @pytest.mark.parametrize("malformada", ["isto-nao-e-base64!", "AAAA", "QUJD"])
    def test_chave_publica_malformada_desliga_e_avisa(
        self, ambiente: Ambiente, caplog: pytest.LogCaptureFixture, malformada: str
    ) -> None:
        """Chave pública que não é Ed25519 de 32 bytes: ligar o botão faria todo aceite falhar."""
        _escrever_invites(ambiente.invites_path, malformada)
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            resposta = ambiente.client.get("/api/auth/invite-status")
        assert resposta.status_code == 200
        assert resposta.json() == {"enabled": False}
        assert any(r.levelno == logging.WARNING for r in caplog.records)


# --------------------------------------------------------------------------- aceite


class TestAceitar:
    def test_fluxo_completo_emitir_aceitar_e_logar(self, ambiente: Ambiente) -> None:
        """Emite pela rota, aceita sem login, entra com a senha escolhida e o jti fica usado."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        emitido = ambiente.client.post(
            "/api/invites", json={"email": "Fulano@Exemplo.com", "key_password": KEY_PASSWORD}
        )
        assert emitido.status_code == 201, emitido.text
        code = emitido.json()["code"]

        ambiente.sem_login()
        aceito = ambiente.aceitar(code)

        assert aceito.status_code == 201, aceito.text
        assert aceito.json() == {"username": "fulano@exemplo.com", "password_reset": False}
        token = ambiente.client.post(
            "/api/auth/token", data={"username": "fulano@exemplo.com", "password": SENHA_NOVA}
        )
        assert token.status_code == 200, token.text
        jti = verify_invite(code, ambiente.public_key).jti
        assert ambiente.store.is_used(jti)

    def test_codigo_com_espacos_e_quebras_de_linha_e_aceito(self, ambiente: Ambiente) -> None:
        """O e-mail quebra o código em linhas e põe espaços: tudo sai antes de conferir."""
        code = ambiente.codigo()
        colado = f"  {code[:20]} \r\n{code[20:60]}\n\t{code[60:]}  \n"
        assert ambiente.aceitar(colado).status_code == 201

    def test_email_existente_em_outra_caixa_troca_a_senha_sem_duplicar(
        self, ambiente: Ambiente
    ) -> None:
        """Conta gravada como Fulano@X.com + convite para fulano@x.com → um usuário só."""
        provision_user(ambiente.config_path, "Fulano@X.com", "senha-antiga-123",
                       example_path=_EXAMPLE)

        resposta = ambiente.aceitar(ambiente.codigo("fulano@x.com"))

        assert resposta.status_code == 201, resposta.text
        assert resposta.json() == {"username": "Fulano@X.com", "password_reset": True}
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert [u["username"] for u in raw["security"]["users"]] == ["Fulano@X.com"]
        novo = ambiente.client.post(
            "/api/auth/token", data={"username": "fulano@x.com", "password": SENHA_NOVA}
        )
        assert novo.status_code == 200, novo.text
        antigo = ambiente.client.post(
            "/api/auth/token", data={"username": "fulano@x.com", "password": "senha-antiga-123"}
        )
        assert antigo.status_code == 401

    def test_codigo_adulterado_retorna_400_e_nao_cria_conta(self, ambiente: Ambiente) -> None:
        """Um caractere trocado na assinatura → 400, sem conta nem jti marcado."""
        code = ambiente.codigo()
        prefixo, payload, assinatura = code.split(".")
        troca = "A" if assinatura[10] != "A" else "B"
        adulterado = ".".join([prefixo, payload, assinatura[:10] + troca + assinatura[11:]])

        resposta = ambiente.aceitar(adulterado)

        assert resposta.status_code == 400
        assert "convite" in resposta.json()["detail"].lower()
        assert not ambiente.store.used_path.exists()
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert not (raw.get("security") or {}).get("users")

    def test_codigo_de_outra_chave_retorna_400(self, ambiente: Ambiente) -> None:
        """Assinado por um par que não é o do invites.yaml → inválido."""
        outro_pem, _ = generate_keypair(KEY_PASSWORD)
        code = issue_invite(outro_pem, KEY_PASSWORD, "x@y.co", EMISSOR).code
        assert ambiente.aceitar(code).status_code == 400

    @pytest.mark.parametrize(
        "lixo",
        ["abc", "MCRA1", "MCRA1.x", "MCRA1.a.b.c", "MCRA1.!!!.???", "MCRA2.abc.def"],
    )
    def test_lixo_colado_retorna_400(self, ambiente: Ambiente, lixo: str) -> None:
        """O que não é um código vira 400 (nunca 422 nem 500)."""
        resposta = ambiente.aceitar(lixo)
        assert resposta.status_code == 400, resposta.text
        assert resposta.json()["detail"]

    def test_codigo_vencido_retorna_410(self, ambiente: Ambiente) -> None:
        """Assinatura boa, mas emitido há 8 dias (validade de 7) → 410 e a conta não nasce."""
        code = ambiente.codigo(emitido_ha=timedelta(days=8))
        resposta = ambiente.aceitar(code)
        assert resposta.status_code == 410
        assert "novo convite" in resposta.json()["detail"]
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert not (raw.get("security") or {}).get("users")

    def test_codigo_reusado_retorna_409_e_nao_troca_a_senha(self, ambiente: Ambiente) -> None:
        """Segundo aceite do mesmo código → 409; a senha da primeira vez continua valendo."""
        code = ambiente.codigo()
        assert ambiente.aceitar(code).status_code == 201

        segundo = ambiente.aceitar(code, "outra-senha-qualquer-1")

        assert segundo.status_code == 409
        assert "novo convite" in segundo.json()["detail"]
        mantida = ambiente.client.post(
            "/api/auth/token", data={"username": "fulano@exemplo.com", "password": SENHA_NOVA}
        )
        assert mantida.status_code == 200

    def test_dois_aceites_simultaneos_do_mesmo_codigo_so_um_passa(
        self, ambiente: Ambiente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dois aceites ao mesmo tempo → um 201 e um 409; a conta nasce uma vez só.

        ``provision_user`` fica lento de propósito: sem a trava, os dois passam pelo
        ``ensure_unused`` antes de qualquer ``mark_used`` e o convite vale duas vezes.
        """
        real = invites_route.provision_user

        def provision_lento(*args: Any, **kwargs: Any) -> Path:
            time.sleep(0.3)
            return real(*args, **kwargs)

        monkeypatch.setattr(invites_route, "provision_user", provision_lento)
        code = ambiente.codigo()
        largada = threading.Barrier(2)
        respostas: list[int] = []

        def aceitar(senha: str) -> None:
            largada.wait()
            respostas.append(ambiente.aceitar(code, senha).status_code)

        threads = [
            threading.Thread(target=aceitar, args=(senha,))
            for senha in ("primeira-senha-12", "segunda-senha-34")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert sorted(respostas) == [201, 409]
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert [u["username"] for u in raw["security"]["users"]] == ["fulano@exemplo.com"]

    def test_recurso_desligado_retorna_403_antes_de_conferir(self, ambiente: Ambiente) -> None:
        """Sem chave pública nem um código válido entra: 403 e nenhuma conta."""
        code = ambiente.codigo()
        ambiente.desligar()
        resposta = ambiente.aceitar(code)
        assert resposta.status_code == 403
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert not (raw.get("security") or {}).get("users")

    @pytest.mark.parametrize(
        "senha",
        [
            "",
            "curta",
            "1234567",  # 7 caracteres
            "ç" * 37,  # 37 caracteres, 74 bytes em UTF-8
            "x" * 73,  # 73 bytes
            "x" * 129,
        ],
    )
    def test_senha_fora_de_8_caracteres_a_72_bytes_retorna_422_em_portugues(
        self, ambiente: Ambiente, senha: str
    ) -> None:
        """8 caracteres no mínimo, 72 bytes UTF-8 no máximo (limite do bcrypt): detail é texto."""
        resposta = ambiente.aceitar(ambiente.codigo(), senha)
        assert resposta.status_code == 422, resposta.text
        detalhe = resposta.json()["detail"]
        assert isinstance(detalhe, str)
        assert "8 caracteres" in detalhe and "72 bytes" in detalhe
        assert not ambiente.store.used_path.exists()

    @pytest.mark.parametrize("senha", ["12345678", "x" * 72, "ç" * 36, "é" * 8])
    def test_senha_nos_limites_e_aceita(self, ambiente: Ambiente, senha: str) -> None:
        """8 caracteres, 72 bytes ASCII e 72 bytes de acentos (36 'ç') passam e dão login."""
        resposta = ambiente.aceitar(ambiente.codigo(), senha)
        assert resposta.status_code == 201, resposta.text
        token = ambiente.client.post(
            "/api/auth/token", data={"username": "fulano@exemplo.com", "password": senha}
        )
        assert token.status_code == 200, token.text

    @pytest.mark.parametrize("codigo", ["", "   ", "\n\t \r\n"])
    def test_codigo_vazio_retorna_422_em_portugues(
        self, ambiente: Ambiente, codigo: str
    ) -> None:
        """Nada colado no campo: pede o código em vez de dizer que ele é inválido."""
        resposta = ambiente.aceitar(codigo)
        assert resposta.status_code == 422, resposta.text
        detalhe = resposta.json()["detail"]
        assert isinstance(detalhe, str)
        assert "código" in detalhe.lower()

    @pytest.mark.parametrize(
        "corpo",
        [{}, {"code": "x"}, {"password": "12345678"}, {"code": 7, "password": "12345678"},
         {"code": "x", "password": None}],
    )  # fmt: skip
    def test_corpo_incompleto_ou_de_tipo_errado_retorna_422_em_portugues(
        self, ambiente: Ambiente, corpo: dict[str, object]
    ) -> None:
        """Nada do 422 padrão do FastAPI (lista em inglês): detail é uma frase em português."""
        resposta = ambiente.client.post("/api/auth/invite/accept", json=corpo)
        assert resposta.status_code == 422, resposta.text
        detalhe = resposta.json()["detail"]
        assert isinstance(detalhe, str)
        assert "tente de novo" in detalhe

    def test_corpo_que_nao_e_json_retorna_422_em_portugues(self, ambiente: Ambiente) -> None:
        """JSON quebrado também não vaza o texto em inglês do pydantic."""
        resposta = ambiente.client.post(
            "/api/auth/invite/accept",
            content="{nao-e-json",
            headers={"Content-Type": "application/json"},
        )
        assert resposta.status_code == 422
        assert isinstance(resposta.json()["detail"], str)

    def test_senha_com_surrogate_solto_no_json_retorna_422_e_nao_500(
        self, ambiente: Ambiente
    ) -> None:
        """`\\ud800` solto no JSON não codifica em UTF-8: 422 em português, nunca 500."""
        corpo = b'{"code":"x","password":"' + bytes([92]) + b'ud800abcdefgh"}'
        resposta = ambiente.client.post(
            "/api/auth/invite/accept",
            content=corpo,
            headers={"Content-Type": "application/json"},
        )
        assert resposta.status_code == 422, resposta.text
        assert isinstance(resposta.json()["detail"], str)

    def test_aceite_e_publico_nao_pede_login(self, ambiente: Ambiente) -> None:
        """Sem token o aceite funciona: a prova é a assinatura."""
        ambiente.sem_login()
        assert ambiente.aceitar(ambiente.codigo()).status_code == 201

    def test_arquivo_de_usados_ilegivel_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """invites_used.json corrompido: falha fechada (nada é aceito) e a mensagem diz qual."""
        ambiente.store.used_path.write_text("{", encoding="utf-8")
        resposta = ambiente.aceitar(ambiente.codigo())
        assert resposta.status_code == 409
        assert "invites_used.json" in resposta.json()["detail"]
        raw = yaml.safe_load(ambiente.config_path.read_text(encoding="utf-8"))
        assert not (raw.get("security") or {}).get("users")

    def test_invites_yaml_ilegivel_no_aceite_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """invites.yaml quebrado depois da emissão: 409 que diz qual arquivo, não 500."""
        code = ambiente.codigo()
        ambiente.invites_path.write_text("public_key: [\n", encoding="utf-8")
        resposta = ambiente.aceitar(code)
        assert resposta.status_code == 409
        assert "invites.yaml" in resposta.json()["detail"]

    def test_chave_publica_malformada_no_aceite_retorna_409(self, ambiente: Ambiente) -> None:
        """Chave pública com lixo no invites.yaml: o aceite diz o que fazer, em 409."""
        code = ambiente.codigo()
        _escrever_invites(ambiente.invites_path, "isto-nao-e-base64!")
        resposta = ambiente.aceitar(code)
        assert resposta.status_code == 409
        assert "invites.yaml" in resposta.json()["detail"]

    def test_settings_quebrado_no_secret_key_nao_vaza_o_segredo_no_corpo_nem_no_log(
        self, ambiente: Ambiente, caplog: pytest.LogCaptureFixture
    ) -> None:
        """O erro do PyYAML traz um trecho do arquivo: o secret_key não pode sair (C4)."""
        segredo = "SEGREDO-DO-SECRET-KEY-0123456789abcdef"
        ambiente.config_path.write_text(
            f'security:\n  secret_key: "{segredo}\n  users: []\n', encoding="utf-8"
        )
        code = ambiente.codigo()

        with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
            resposta = ambiente.aceitar(code)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == (
            "Não foi possível gravar a conta: o arquivo de configuração do MCRA está com "
            "problema. Peça ajuda ao responsável técnico."
        )
        assert segredo not in resposta.text
        tudo = caplog.text + "".join(str(r.__dict__) for r in caplog.records)
        assert segredo not in tudo
        assert str(ambiente.config_path) in tudo  # o log diz qual arquivo, sem o trecho
        assert not ambiente.store.used_path.exists()  # conta não gravada: convite segue vivo


# --------------------------------------------------------------------------- capability


class TestCapability:
    def test_emissor_com_chave_pode_convidar(self, ambiente: Ambiente) -> None:
        """Chave pública + emissor = usuário logado + chave privada → can_invite verdadeiro."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.get("/api/invites/capability")
        assert resposta.status_code == 200
        assert resposta.json() == {"can_invite": True}

    def test_comparacao_do_emissor_ignora_caixa_e_espacos(self, ambiente: Ambiente) -> None:
        """O username gravado pode ser Gabriel@Exemplo.com; o emissor está normalizado."""
        ambiente.configurar_emissor()
        ambiente.como(" Gabriel@EXEMPLO.com ")
        assert ambiente.client.get("/api/invites/capability").json() == {"can_invite": True}

    @pytest.mark.parametrize(
        "cenario", ["outro_usuario", "sem_chave_privada", "sem_emissor", "recurso_desligado"]
    )
    def test_falta_uma_condicao_nao_pode_convidar(
        self, ambiente: Ambiente, cenario: str
    ) -> None:
        """Cada uma das três condições da spec, e o recurso desligado, derruba can_invite."""
        usuario = EMISSOR
        if cenario == "outro_usuario":
            ambiente.configurar_emissor()
            usuario = "colega@exemplo.com"
        elif cenario == "sem_chave_privada":
            ambiente.configurar_emissor(com_chave=False)
        elif cenario == "sem_emissor":
            ambiente.store.write_private_key(ambiente.pem)
        else:
            ambiente.configurar_emissor()
            ambiente.desligar()
        ambiente.como(usuario)
        assert ambiente.client.get("/api/invites/capability").json() == {"can_invite": False}

    @pytest.mark.parametrize(
        "defeito", ["yaml_ilegivel", "chave_publica_malformada", "emissor_ilegivel"]
    )
    def test_arquivo_com_defeito_nao_pode_convidar_e_avisa(
        self, ambiente: Ambiente, caplog: pytest.LogCaptureFixture, defeito: str
    ) -> None:
        """invites.yaml, chave pública ou invite_issuer.yaml com defeito: false e WARNING."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        if defeito == "yaml_ilegivel":
            ambiente.invites_path.write_text("public_key: [\n", encoding="utf-8")
        elif defeito == "chave_publica_malformada":
            _escrever_invites(ambiente.invites_path, "isto-nao-e-base64!")
        else:
            ambiente.store.issuer_path.write_text("issuer: [", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="ranking_msc"):
            resposta = ambiente.client.get("/api/invites/capability")
        assert resposta.status_code == 200
        assert resposta.json() == {"can_invite": False}
        assert any(r.levelno == logging.WARNING for r in caplog.records)


# --------------------------------------------------------------------------- emissão


class TestEmitir:
    def test_emite_envia_o_email_e_grava_a_linha(self, ambiente: Ambiente) -> None:
        """201 com os campos do contrato; o envio recebe a senha de app decifrada; linha gravada."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "Fulano@Exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        assert set(corpo) == {"email", "expires_at", "email_sent", "code"}
        assert corpo["email"] == "fulano@exemplo.com"
        assert corpo["email_sent"] is True
        assert datetime.fromisoformat(corpo["expires_at"]).utcoffset() is not None
        assert verify_invite(corpo["code"], ambiente.public_key).email == "fulano@exemplo.com"
        # O envio saiu pela conta do emissor, com a senha de app em texto puro.
        assert len(ambiente.envio.chamadas) == 1
        mensagem, smtp_user, smtp_password = ambiente.envio.chamadas[0]
        assert (smtp_user, smtp_password) == (SMTP_USER, APP_PASSWORD)
        assert mensagem["To"] == "fulano@exemplo.com"
        assert corpo["code"] in mensagem.get_body(("plain",)).get_content()
        assert INSTALLER_URL in mensagem.get_body(("plain",)).get_content()
        # Linha em invites_sent.jsonl, sem o código.
        lista = ambiente.store.list_sent()
        assert [(s.email, s.email_sent) for s in lista] == [("fulano@exemplo.com", True)]
        assert corpo["code"] not in ambiente.store.sent_path.read_text(encoding="utf-8")

    def test_envio_falho_ainda_devolve_o_codigo_e_registra_email_sent_falso(
        self, ambiente: Ambiente
    ) -> None:
        """Gmail recusou: o convite vale, o código volta para a tela e a lista mostra a falha."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        ambiente.envio.ok = False

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        assert corpo["email_sent"] is False
        assert verify_invite(corpo["code"], ambiente.public_key).email == "fulano@exemplo.com"
        assert [s.email_sent for s in ambiente.store.list_sent()] == [False]

    @pytest.mark.parametrize("senha", ["senha-errada-1234", " ", "x" * 200])
    def test_senha_da_chave_errada_retorna_400_sem_enviar_nem_gravar(
        self, ambiente: Ambiente, senha: str
    ) -> None:
        """Senha da chave incorreta → 400 em português; nada enviado, nada registrado."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": senha}
        )

        assert resposta.status_code == 400
        assert "Senha da chave incorreta" in resposta.json()["detail"]
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()

    @pytest.mark.parametrize(
        "cenario", ["outro_usuario", "sem_chave_privada", "sem_emissor", "recurso_desligado"]
    )
    def test_sem_permissao_retorna_403_sem_tentar_a_senha(
        self, ambiente: Ambiente, cenario: str
    ) -> None:
        """Quem não é o emissor (ou não tem a chave) leva 403, mesmo com a senha certa."""
        usuario = EMISSOR
        if cenario == "outro_usuario":
            ambiente.configurar_emissor()
            usuario = "colega@exemplo.com"
        elif cenario == "sem_chave_privada":
            ambiente.configurar_emissor(com_chave=False)
        elif cenario == "sem_emissor":
            ambiente.store.write_private_key(ambiente.pem)
        else:
            ambiente.configurar_emissor()
            ambiente.desligar()
        ambiente.como(usuario)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 403
        assert resposta.json()["detail"]
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "   ",
            "semarroba",
            "a@b",
            "a b@c.de",
            "@c.de",
            "a@@c.de",
            "fulano@x.com;",  # colado do Outlook
            "fulano@x.com,",
            "<fulano@x.com>",
            "Fulano Silva <fulano@x.com>",
            "fulano@x.com.",
            "fulano@x..com",
            "fulano@x.com\nbeltrano@x.com",
            "fulano @x.com",
            "fulano@x.com beltrano@x.com",
            "fulano@x_y.com",
            "fulano@x.com;beltrano@x.com",
            "'fulano@x.com'",
            "\"fulano@x.com\"",
            "fulano@exemplo.cõm",
        ],
    )
    def test_email_malformado_retorna_422_em_portugues_sem_emitir(
        self, ambiente: Ambiente, email: str
    ) -> None:
        """Padrão estrito depois do strip; o detail é texto em português, nada é emitido."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": email, "key_password": KEY_PASSWORD}
        )
        assert resposta.status_code == 422, resposta.text
        assert resposta.json()["detail"] == (
            "E-mail inválido. Digite só o endereço, sem nome, ponto e vírgula ou sinais."
        )
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()

    @pytest.mark.parametrize(
        "email",
        ["fulano@x.com", "a.b_c%d+e-f@sub.exemplo.com.br", " Fulano@X.com\n", "1@2-3.co"],
    )
    def test_email_dentro_do_padrao_e_aceito(self, ambiente: Ambiente, email: str) -> None:
        """Contraprova da tabela: endereço limpo (com strip) emite o convite."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": email, "key_password": KEY_PASSWORD}
        )
        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["email"] == email.strip().casefold()

    def test_senha_da_chave_vazia_retorna_422_em_portugues_sem_tentar_abrir_a_chave(
        self, ambiente: Ambiente
    ) -> None:
        """Campo em branco: pede a senha em vez de dizer que ela está incorreta."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": ""}
        )
        assert resposta.status_code == 422, resposta.text
        detalhe = resposta.json()["detail"]
        assert isinstance(detalhe, str)
        assert "senha da chave" in detalhe.lower()
        assert ambiente.envio.chamadas == []

    @pytest.mark.parametrize(
        "corpo",
        [{}, {"email": "a@b.co"}, {"key_password": "x"}, {"email": 1, "key_password": "x"},
         {"email": "a@b.co", "key_password": None}],
    )  # fmt: skip
    def test_corpo_incompleto_ou_de_tipo_errado_retorna_422_em_portugues(
        self, ambiente: Ambiente, corpo: dict[str, object]
    ) -> None:
        """Nada do 422 padrão do FastAPI: detail é uma frase em português."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post("/api/invites", json=corpo)
        assert resposta.status_code == 422, resposta.text
        detalhe = resposta.json()["detail"]
        assert isinstance(detalhe, str)
        assert "tente de novo" in detalhe

    def test_chave_privada_que_nao_e_par_da_publica_retorna_409_sem_enviar_nem_gravar(
        self, ambiente: Ambiente
    ) -> None:
        """Emissor rodou `init --force` e não instalou o release novo: convite sairia morto."""
        outro_pem, _ = generate_keypair(KEY_PASSWORD)
        ambiente.store.write_issuer(
            IssuerConfig(EMISSOR, SMTP_USER, encrypt_secret(APP_PASSWORD, KEY_PASSWORD))
        )
        ambiente.store.write_private_key(outro_pem)  # par diferente do invites.yaml em uso
        ambiente.como(EMISSOR)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 409, resposta.text
        assert resposta.json()["detail"] == (
            "A chave de convites deste computador não é a da versão instalada. Instale a "
            "versão do MCRA gerada depois da troca da chave e tente de novo."
        )
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()
        assert "MCRA1" not in resposta.text

    def test_senha_errada_com_chave_de_outro_par_continua_400(self, ambiente: Ambiente) -> None:
        """Sem abrir a chave não dá para comparar o par: a senha errada é o primeiro erro."""
        outro_pem, _ = generate_keypair(KEY_PASSWORD)
        ambiente.store.write_issuer(
            IssuerConfig(EMISSOR, SMTP_USER, encrypt_secret(APP_PASSWORD, KEY_PASSWORD))
        )
        ambiente.store.write_private_key(outro_pem)
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": "errada-12345"}
        )
        assert resposta.status_code == 400

    def test_email_com_espacos_nas_pontas_e_normalizado(self, ambiente: Ambiente) -> None:
        """Quem cola o e-mail com espaço ou maiúscula leva um convite para o e-mail limpo."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": "  Fulano@Exemplo.COM ", "key_password": KEY_PASSWORD}
        )
        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["email"] == "fulano@exemplo.com"

    def test_validade_vem_do_invites_yaml(self, ambiente: Ambiente) -> None:
        """validity_days: 3 → o convite emitido vale exatamente 3 dias."""
        _escrever_invites(ambiente.invites_path, ambiente.public_key, validity_days=3)
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )
        [enviado] = ambiente.store.list_sent()
        assert enviado.expires_at - enviado.issued_at == timedelta(days=3)

    def test_emissor_corrompido_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """invite_issuer.yaml ilegível → 409 que diz qual arquivo refazer (a tela não vê 5xx)."""
        ambiente.store.issuer_path.write_text("issuer: [", encoding="utf-8")
        ambiente.como(EMISSOR)
        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )
        assert resposta.status_code == 409
        assert "invite_issuer.yaml" in resposta.json()["detail"]

    @pytest.mark.parametrize("conteudo", [b"", b"lixo", b"a.b", b"\xff\xfe"])
    def test_chave_privada_corrompida_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente, conteudo: bytes
    ) -> None:
        """invite_key.pem corrompido não é 'senha incorreta' (400): é 409 com o arquivo."""
        ambiente.configurar_emissor(com_chave=False)
        ambiente.store.write_private_key(conteudo)
        ambiente.como(EMISSOR)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 409, resposta.text
        assert "invite_key.pem" in resposta.json()["detail"]
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()

    def test_segredo_de_envio_corrompido_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """A senha de app cifrada ilegível no invite_issuer.yaml: 409, sem e-mail e sem registro."""
        ambiente.store.write_issuer(IssuerConfig(EMISSOR, SMTP_USER, "isto-esta-corrompido"))
        ambiente.store.write_private_key(ambiente.pem)
        ambiente.como(EMISSOR)

        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )

        assert resposta.status_code == 409, resposta.text
        assert "invite_issuer.yaml" in resposta.json()["detail"]
        assert ambiente.envio.chamadas == []
        assert not ambiente.store.sent_path.exists()

    def test_invites_yaml_ilegivel_na_emissao_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """invites.yaml quebrado: 409 que diz qual arquivo, não 500."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        ambiente.invites_path.write_text("public_key: [\n", encoding="utf-8")
        resposta = ambiente.client.post(
            "/api/invites", json={"email": "fulano@exemplo.com", "key_password": KEY_PASSWORD}
        )
        assert resposta.status_code == 409
        assert "invites.yaml" in resposta.json()["detail"]


# --------------------------------------------------------------------------- listagem


class TestListar:
    def test_sem_convites_devolve_lista_vazia(self, ambiente: Ambiente) -> None:
        """Emissor sem nenhum convite → 200 e []."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        resposta = ambiente.client.get("/api/invites")
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_lista_o_mais_recente_primeiro_com_os_campos_do_contrato(
        self, ambiente: Ambiente
    ) -> None:
        """Dois convites → dois itens, o último emitido primeiro, sem o código."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        for email in ("um@exemplo.com", "dois@exemplo.com"):
            ambiente.client.post(
                "/api/invites", json={"email": email, "key_password": KEY_PASSWORD}
            )

        resposta = ambiente.client.get("/api/invites")

        assert resposta.status_code == 200
        itens = resposta.json()
        assert [i["email"] for i in itens] == ["dois@exemplo.com", "um@exemplo.com"]
        assert all(set(i) == {"email", "issued_at", "expires_at", "email_sent"} for i in itens)
        assert all(datetime.fromisoformat(i["expires_at"]).utcoffset() is not None for i in itens)
        assert "MCRA1" not in resposta.text

    def test_linha_ilegivel_no_arquivo_nao_derruba_a_lista(self, ambiente: Ambiente) -> None:
        """Queda de energia no meio de um append: a tela ainda lista os outros convites."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        ambiente.client.post(
            "/api/invites", json={"email": "um@exemplo.com", "key_password": KEY_PASSWORD}
        )
        with ambiente.store.sent_path.open("a", encoding="utf-8") as handle:
            handle.write('{"email": "meio@exemplo.com", "issued_at": "2026-11\n')

        resposta = ambiente.client.get("/api/invites")

        assert resposta.status_code == 200
        assert [i["email"] for i in resposta.json()] == ["um@exemplo.com"]

    @pytest.mark.parametrize("cenario", ["outro_usuario", "sem_chave_privada", "sem_emissor"])
    def test_sem_permissao_retorna_403(self, ambiente: Ambiente, cenario: str) -> None:
        """Quem não é o emissor não vê a lista (403, com o texto de como obter permissão)."""
        usuario = EMISSOR
        if cenario == "outro_usuario":
            ambiente.configurar_emissor()
            usuario = "colega@exemplo.com"
        elif cenario == "sem_chave_privada":
            ambiente.configurar_emissor(com_chave=False)
        ambiente.como(usuario)
        resposta = ambiente.client.get("/api/invites")
        assert resposta.status_code == 403
        assert resposta.json()["detail"]

    def test_emissor_corrompido_retorna_409_com_o_nome_do_arquivo(
        self, ambiente: Ambiente
    ) -> None:
        """A lista também diz qual arquivo refazer, em 409 (não 500)."""
        ambiente.store.issuer_path.write_text("issuer: [", encoding="utf-8")
        ambiente.como(EMISSOR)
        resposta = ambiente.client.get("/api/invites")
        assert resposta.status_code == 409
        assert "invite_issuer.yaml" in resposta.json()["detail"]


# --------------------------------------------------------------------------- login obrigatório


class TestLoginObrigatorio:
    @pytest.mark.parametrize(
        ("metodo", "caminho", "corpo"),
        [
            ("get", "/api/invites/capability", None),
            ("get", "/api/invites", None),
            ("post", "/api/invites", {"email": "a@b.co", "key_password": "x"}),
        ],
    )
    def test_rotas_de_emissao_sem_token_retornam_401(
        self, ambiente: Ambiente, metodo: str, caminho: str, corpo: dict[str, str] | None
    ) -> None:
        """RM-13: só as duas rotas de /api/auth/invite* são públicas; estas três pedem login."""
        ambiente.configurar_emissor()
        ambiente.sem_login()
        chamar: Callable[..., object] = getattr(ambiente.client, metodo)
        resposta = chamar(caminho, json=corpo) if corpo is not None else chamar(caminho)
        assert resposta.status_code == 401  # type: ignore[attr-defined]
        assert ambiente.envio.chamadas == []


# --------------------------------------------------------------------------- log


class TestLog:
    def test_aceite_loga_info_e_recusa_loga_warning_sem_segredo(
        self, ambiente: Ambiente, caplog: pytest.LogCaptureFixture
    ) -> None:
        """INFO no aceite, WARNING na recusa; nem código nem senha em registro algum."""
        ambiente.configurar_emissor()
        ambiente.como(EMISSOR)
        with caplog.at_level(logging.DEBUG, logger="ranking_msc"):
            emitido = ambiente.client.post(
                "/api/invites", json={"email": "Fulano@Exemplo.com", "key_password": KEY_PASSWORD}
            )
            ambiente.client.post(  # senha da chave errada: recusa na emissão
                "/api/invites", json={"email": "x@exemplo.com", "key_password": "errada-errada-1"}
            )
            code = emitido.json()["code"]
            ambiente.sem_login()
            aceito = ambiente.aceitar(code)
            reuso = ambiente.aceitar(code, "outra-senha-qualquer-1")
            adulterado = ambiente.aceitar(code[:-6] + "AAAAAA")
        assert (aceito.status_code, reuso.status_code, adulterado.status_code) == (201, 409, 400)

        jti = verify_invite(code, ambiente.public_key).jti
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any(
            "fulano@exemplo.com" in r.getMessage() and jti in r.getMessage()
            and "password_reset" in r.getMessage()
            for r in infos
        )
        avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(avisos) >= 3  # reuso, adulterado e senha da chave errada

        tudo = caplog.text + "".join(str(r.__dict__) for r in caplog.records)
        corpo_do_codigo = code.split(".")
        for segredo in (
            code,
            corpo_do_codigo[1],
            corpo_do_codigo[2],
            KEY_PASSWORD,
            "errada-errada-1",
            APP_PASSWORD,
            SENHA_NOVA,
            "outra-senha-qualquer-1",
        ):
            assert segredo not in tudo
