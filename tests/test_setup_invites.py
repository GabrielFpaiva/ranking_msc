"""Testes do CLI de instalação do convite (scripts/setup_invites.py).

Nenhum teste toca o ``config/invites.yaml`` do repositório nem a pasta de dados real do
MCRA: o ``invites.yaml`` é um texto de exemplo gravado em ``tmp_path`` e a pasta de estado
vai sempre por ``--state-dir`` (o teste do padrão aponta ``LOCALAPPDATA`` para ``tmp_path``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.setup_invites as cli
import yaml

from ranking_msc.exceptions import ConfigError
from ranking_msc.services.invites import (
    InviteStore,
    decrypt_secret,
    issue_invite,
    load_invite_config,
    verify_invite,
)
from ranking_msc.services.users import provision_user

_SCRIPT = Path(cli.__file__).resolve()
_EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"

SENHA_CHAVE = "senha-da-chave-123"
SENHA_APP = "abcd efgh ijkl mnop"
EMISSOR = "gabriel@exemplo.com"
SMTP_USER = "envio@gmail.com"
URL_ANTIGA = "https://drive.example/pasta-antiga"
URL_NOVA = "https://drive.example/pasta-nova?usp=sharing"

INVITES_YAML = f"""\
# Configuração do convite assinado (exemplo de teste).
# Nada aqui é segredo.

# Chave pública Ed25519, em base64.
# Vazio = convites desligados.
public_key: ""

# Pasta do Drive com o instalador.
installer_url: "{URL_ANTIGA}"

# Quantos dias um convite vale.
validity_days: 7
"""


@pytest.fixture
def invites_file(tmp_path: Path) -> Path:
    """invites.yaml de exemplo (LF), em tmp_path."""
    path = tmp_path / "invites.yaml"
    path.write_bytes(INVITES_YAML.encode("utf-8"))
    return path


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Pasta de config do MCRA de mentira, com um settings.yaml onde o emissor já tem conta."""
    pasta = tmp_path / "MCRA" / "config"
    pasta.mkdir(parents=True)
    provision_user(pasta / "settings.yaml", EMISSOR, "senha-do-emissor-1", example_path=_EXAMPLE)
    return pasta


@pytest.fixture
def senhas_por_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Senhas nas variáveis de ambiente que os testes de init passam nas flags."""
    monkeypatch.setenv("T_KEY_PW", SENHA_CHAVE)
    monkeypatch.setenv("T_SMTP_PW", SENHA_APP)


def _init(
    invites_file: Path, state_dir: Path, *extras: str, issuer: str = EMISSOR
) -> int:
    return cli.run_cli(
        [
            "init",
            "--issuer", issuer,
            "--smtp-user", SMTP_USER,
            "--key-password-env", "T_KEY_PW",
            "--smtp-password-env", "T_SMTP_PW",
            "--state-dir", str(state_dir),
            "--invites-file", str(invites_file),
            *extras,
        ]
    )  # fmt: skip


# --------------------------------------------------------------------------- edição da linha


class TestReplaceYamlValue:
    def test_troca_so_a_linha_da_chave_e_preserva_o_resto_byte_a_byte(self) -> None:
        """Comentários, linhas em branco e as outras chaves ficam exatamente como estão."""
        novo = cli.replace_yaml_value(INVITES_YAML, "public_key", "AbC+/=")
        antigas, novas = INVITES_YAML.splitlines(keepends=True), novo.splitlines(keepends=True)
        assert len(antigas) == len(novas)
        diferentes = [(a, n) for a, n in zip(antigas, novas, strict=True) if a != n]
        assert diferentes == [('public_key: ""\n', 'public_key: "AbC+/="\n')]

    @pytest.mark.parametrize(
        ("linha", "esperada"),
        [
            ('public_key: ""', 'public_key: "NOVO"'),
            ("public_key: ''", 'public_key: "NOVO"'),
            ("public_key:", 'public_key: "NOVO"'),
            ('public_key: "antiga"   # nota do Gabriel', 'public_key: "NOVO"   # nota do Gabriel'),
            ("public_key: antiga # nota", 'public_key: "NOVO" # nota'),
        ],
    )
    def test_formas_do_valor_antigo_e_comentario_na_mesma_linha(
        self, linha: str, esperada: str
    ) -> None:
        """Valor com aspas, puro ou ausente: troca o valor, guarda o comentário, YAML válido."""
        novo = cli.replace_yaml_value(f"{linha}\nb: 1\n", "public_key", "NOVO")
        assert novo == f"{esperada}\nb: 1\n"
        assert yaml.safe_load(novo) == {"public_key": "NOVO", "b": 1}

    def test_fim_de_linha_crlf_e_mantido(self) -> None:
        """Arquivo com CRLF continua com CRLF; nenhum LF solto aparece."""
        texto = INVITES_YAML.replace("\n", "\r\n")
        novo = cli.replace_yaml_value(texto, "installer_url", "https://x.example/y")
        assert novo.count("\r\n") == texto.count("\r\n")
        assert "\n" not in novo.replace("\r\n", "")

    def test_valor_com_aspas_e_barra_vira_yaml_valido(self) -> None:
        """O valor é escrito com json.dumps: aspas e barras invertidas não quebram o YAML."""
        novo = cli.replace_yaml_value(INVITES_YAML, "installer_url", 'a"b\\c')
        assert yaml.safe_load(novo)["installer_url"] == 'a"b\\c'

    def test_ignora_chave_indentada_ou_comentada(self) -> None:
        """Só a linha do nível raiz conta: `# public_key:` e `  public_key:` não são editadas."""
        texto = '# public_key: "x"\nsub:\n  public_key: "y"\npublic_key: ""\n'
        novo = cli.replace_yaml_value(texto, "public_key", "Z")
        assert novo == '# public_key: "x"\nsub:\n  public_key: "y"\npublic_key: "Z"\n'

    def test_sem_a_linha_levanta_configerror(self) -> None:
        """Arquivo sem `public_key:` → ConfigError com o nome da chave."""
        with pytest.raises(ConfigError, match="public_key"):
            cli.replace_yaml_value("installer_url: x\n", "public_key", "Z")


# --------------------------------------------------------------------------- set-url


class TestSetUrl:
    def test_troca_a_url_e_so_ela(
        self, invites_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """installer_url muda; comentários e as outras chaves ficam byte a byte; sem CR."""
        codigo = cli.run_cli(["set-url", URL_NOVA, "--invites-file", str(invites_file)])

        assert codigo == 0
        bruto = invites_file.read_bytes()
        assert b"\r" not in bruto
        esperado = INVITES_YAML.replace(f'"{URL_ANTIGA}"', f'"{URL_NOVA}"')
        assert bruto.decode("utf-8") == esperado
        config = load_invite_config(invites_file)
        assert config.installer_url == URL_NOVA
        assert config.public_key == ""
        assert not list(invites_file.parent.glob(".*.tmp"))
        assert str(invites_file) in capsys.readouterr().out

    def test_arquivo_ausente_retorna_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sem invites.yaml: mensagem de erro e código 2, não traceback."""
        assert cli.run_cli(["set-url", URL_NOVA, "--invites-file", str(tmp_path / "x.yaml")]) == 2
        assert "ERRO" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "url",
        ["", "   ", "http://drive.example/p", "drive.example/p", "ftp://x.example", "https://",
         "HTTPS//x"],
    )
    def test_link_vazio_ou_sem_https_retorna_2_e_nao_grava(
        self,
        invites_file: Path,
        capsys: pytest.CaptureFixture[str],
        url: str,
    ) -> None:
        """O link precisa começar com https://: senão o e-mail leva o colaborador a lugar nenhum."""
        assert cli.run_cli(["set-url", url, "--invites-file", str(invites_file)]) == 2
        assert "https://" in capsys.readouterr().err
        assert invites_file.read_text(encoding="utf-8") == INVITES_YAML

    def test_link_com_espacos_nas_pontas_e_gravado_limpo(self, invites_file: Path) -> None:
        """Link colado com espaço ou quebra de linha nas pontas grava sem eles."""
        assert cli.run_cli(["set-url", f" {URL_NOVA}\n", "--invites-file", str(invites_file)]) == 0
        assert load_invite_config(invites_file).installer_url == URL_NOVA


# --------------------------------------------------------------------------- init


class TestInit:
    def test_grava_chave_emissor_e_chave_publica_que_fecham_o_ciclo(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
    ) -> None:
        """init deixa tudo pronto: um convite emitido com a chave verifica com a pública gravada."""
        codigo = _init(invites_file, state_dir)

        assert codigo == 0
        store = InviteStore(state_dir)
        assert store.has_private_key()
        config = load_invite_config(invites_file)
        assert config.enabled
        assert config.installer_url == URL_ANTIGA  # o resto do arquivo não mudou
        convite = issue_invite(store.read_private_key(), SENHA_CHAVE, "Novo@X.com", EMISSOR)
        assert verify_invite(convite.code, config.public_key).email == "novo@x.com"
        emissor = store.read_issuer()
        assert emissor is not None
        assert (emissor.email, emissor.smtp_user) == (EMISSOR, SMTP_USER)
        assert SENHA_APP not in store.issuer_path.read_text(encoding="utf-8")
        assert decrypt_secret(emissor.smtp_password_encrypted, SENHA_CHAVE) == SENHA_APP
        # Só a linha public_key mudou, sem CR.
        bruto = invites_file.read_bytes()
        assert b"\r" not in bruto
        trocadas = [
            antiga
            for antiga, nova in zip(
                INVITES_YAML.splitlines(), bruto.decode("utf-8").splitlines(), strict=True
            )
            if antiga != nova
        ]
        assert trocadas == ['public_key: ""']

    def test_nunca_imprime_segredo(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Nem a senha da chave, nem a de app, nem o PEM aparecem na saída."""
        _init(invites_file, state_dir)
        saida = capsys.readouterr()
        arquivo = InviteStore(state_dir).read_private_key().decode("ascii")
        for texto in (saida.out, saida.err):
            assert SENHA_CHAVE not in texto
            assert SENHA_APP not in texto
            assert "PRIVATE KEY" not in texto
            assert arquivo[:40] not in texto
            assert arquivo[-40:] not in texto

    def test_arquivo_da_chave_gravado_nao_tem_a_chave_em_claro(
        self, invites_file: Path, state_dir: Path, senhas_por_ambiente: None
    ) -> None:
        """O invite_key.pem em disco é só o token cifrado (scrypt + Fernet), sem PEM (C2)."""
        _init(invites_file, state_dir)
        gravado = InviteStore(state_dir).private_key_path.read_text(encoding="ascii")
        assert "PRIVATE KEY" not in gravado
        assert "BEGIN" not in gravado
        aberto = decrypt_secret(gravado, SENHA_CHAVE)
        assert aberto.startswith("-----BEGIN PRIVATE KEY-----")

    def test_senhas_pelo_prompt_com_confirmacao(
        self,
        invites_file: Path,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sem variáveis de ambiente: pede a senha da chave (duas vezes) e a de app."""
        respostas = iter([SENHA_CHAVE, SENHA_CHAVE, SENHA_APP])
        prompts: list[str] = []

        def falso(prompt: str = "") -> str:
            prompts.append(prompt)
            return next(respostas)

        monkeypatch.setattr(cli.getpass, "getpass", falso)
        codigo = cli.run_cli(
            ["init", "--issuer", EMISSOR, "--smtp-user", SMTP_USER,
             "--state-dir", str(state_dir), "--invites-file", str(invites_file)]
        )  # fmt: skip

        assert codigo == 0
        assert len(prompts) == 3
        store = InviteStore(state_dir)
        issuer = store.read_issuer()
        assert issuer is not None
        assert decrypt_secret(issuer.smtp_password_encrypted, SENHA_CHAVE) == SENHA_APP

    def test_confirmacao_diferente_retorna_2_e_nao_grava_nada(
        self, invites_file: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As duas senhas da chave diferem → erro, sem chave, sem emissor, invites.yaml igual."""
        respostas = iter([SENHA_CHAVE, "outra-senha-da-chave"])
        monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(respostas))
        codigo = cli.run_cli(
            ["init", "--issuer", EMISSOR, "--smtp-user", SMTP_USER,
             "--state-dir", str(state_dir), "--invites-file", str(invites_file)]
        )  # fmt: skip
        assert codigo == 2
        self._nada_gravado(invites_file, state_dir)

    def test_senha_da_chave_curta_retorna_2_e_nao_grava_nada(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """11 caracteres (o mínimo é 12) → erro antes de gerar qualquer coisa."""
        monkeypatch.setenv("T_KEY_PW", "x" * 11)
        assert _init(invites_file, state_dir) == 2
        self._nada_gravado(invites_file, state_dir)

    def test_senha_curta_e_recusada_antes_de_pedir_a_senha_de_app(
        self, invites_file: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No prompt, a senha curta da chave para o comando sem perguntar a senha de app."""
        pedidos: list[str] = []

        def falso(prompt: str = "") -> str:
            pedidos.append(prompt)
            return "curta"

        monkeypatch.setattr(cli.getpass, "getpass", falso)
        codigo = cli.run_cli(
            ["init", "--issuer", EMISSOR, "--smtp-user", SMTP_USER,
             "--state-dir", str(state_dir), "--invites-file", str(invites_file)]
        )  # fmt: skip
        assert codigo == 2
        assert len(pedidos) == 2  # a chave e a confirmação; a senha de app nem foi pedida
        self._nada_gravado(invites_file, state_dir)

    def test_variavel_de_ambiente_ausente_retorna_2(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--smtp-password-env apontando para variável inexistente → erro que cita o nome dela."""
        monkeypatch.delenv("T_SMTP_PW")
        assert _init(invites_file, state_dir) == 2
        assert "T_SMTP_PW" in capsys.readouterr().err
        self._nada_gravado(invites_file, state_dir)

    @pytest.mark.parametrize(
        "invalido",
        [
            "gabriel@exemplo.com;",
            "gabriel@exemplo.com,",
            "<gabriel@exemplo.com>",
            "Gabriel <gabriel@exemplo.com>",
            "gabriel@exemplo.com.",
            "gabriel @exemplo.com",
            "gabriel@exemplo",
            "",
        ],
    )
    @pytest.mark.parametrize("campo", ["--issuer", "--smtp-user"])
    def test_endereco_fora_do_padrao_retorna_2_antes_de_pedir_senha_ou_gravar(
        self,
        invites_file: Path,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        campo: str,
        invalido: str,
    ) -> None:
        """--issuer e --smtp-user passam pelo padrão estrito do convite: erro 2, nada gravado."""

        def nao_deve_pedir(prompt: str = "") -> str:
            raise AssertionError(f"pediu senha com endereço inválido: {prompt}")

        monkeypatch.setattr(cli.getpass, "getpass", nao_deve_pedir)
        argumentos = {"--issuer": EMISSOR, "--smtp-user": SMTP_USER, campo: invalido}
        codigo = cli.run_cli(
            ["init", "--issuer", argumentos["--issuer"], "--smtp-user", argumentos["--smtp-user"],
             "--state-dir", str(state_dir), "--invites-file", str(invites_file)]
        )  # fmt: skip
        assert codigo == 2
        erro = capsys.readouterr().err
        assert campo in erro
        assert "E-mail inválido. Digite só o endereço" in erro
        self._nada_gravado(invites_file, state_dir)

    def test_endereco_com_espacos_nas_pontas_e_aceito_limpo(
        self, invites_file: Path, state_dir: Path, senhas_por_ambiente: None
    ) -> None:
        """Quem cola com espaço nas pontas grava o endereço limpo."""
        codigo = cli.run_cli(
            ["init", "--issuer", f"  {EMISSOR}\n", "--smtp-user", f" {SMTP_USER} ",
             "--key-password-env", "T_KEY_PW", "--smtp-password-env", "T_SMTP_PW",
             "--state-dir", str(state_dir), "--invites-file", str(invites_file)]
        )  # fmt: skip
        assert codigo == 0
        emissor = InviteStore(state_dir).read_issuer()
        assert emissor is not None
        assert (emissor.email, emissor.smtp_user) == (EMISSOR, SMTP_USER)

    def test_invites_sem_linha_public_key_retorna_2_antes_de_pedir_senha_ou_gravar(
        self, tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Arquivo sem `public_key:` → recusa antes de perguntar senha e de gravar a chave."""

        def nao_deve_pedir(prompt: str = "") -> str:
            raise AssertionError(f"pediu senha antes de validar o invites.yaml: {prompt}")

        monkeypatch.setattr(cli.getpass, "getpass", nao_deve_pedir)
        arquivo = tmp_path / "invites.yaml"
        arquivo.write_text("installer_url: x\n", encoding="utf-8")
        codigo = cli.run_cli(
            ["init", "--issuer", EMISSOR, "--smtp-user", SMTP_USER,
             "--state-dir", str(state_dir), "--invites-file", str(arquivo)]
        )  # fmt: skip
        assert codigo == 2
        assert not InviteStore(state_dir).has_private_key()

    def test_chave_privada_existente_sem_force_retorna_2_e_nada_muda(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Segundo init sem --force não troca a chave: invalidaria os convites emitidos."""
        assert _init(invites_file, state_dir) == 0
        store = InviteStore(state_dir)
        pem, issuer_text = store.read_private_key(), store.issuer_path.read_text(encoding="utf-8")
        invites_text = invites_file.read_text(encoding="utf-8")
        capsys.readouterr()

        assert _init(invites_file, state_dir) == 2

        assert "--force" in capsys.readouterr().err
        assert store.read_private_key() == pem
        assert store.issuer_path.read_text(encoding="utf-8") == issuer_text
        assert invites_file.read_text(encoding="utf-8") == invites_text

    def test_chave_publica_ja_configurada_sem_force_retorna_2(
        self, tmp_path: Path, state_dir: Path, senhas_por_ambiente: None
    ) -> None:
        """invites.yaml já com chave (outro computador, sem a privada) também pede --force."""
        arquivo = tmp_path / "invites.yaml"
        com_chave = INVITES_YAML.replace('public_key: ""', 'public_key: "AAAA"')
        arquivo.write_text(com_chave, encoding="utf-8")
        before = arquivo.read_text(encoding="utf-8")
        assert _init(arquivo, state_dir) == 2
        assert arquivo.read_text(encoding="utf-8") == before
        assert not InviteStore(state_dir).has_private_key()

    def test_force_troca_a_chave(
        self, invites_file: Path, state_dir: Path, senhas_por_ambiente: None
    ) -> None:
        """Com --force a chave nova substitui a antiga (privada e pública juntas)."""
        assert _init(invites_file, state_dir) == 0
        antiga_publica = load_invite_config(invites_file).public_key
        antiga_privada = InviteStore(state_dir).read_private_key()

        assert _init(invites_file, state_dir, "--force") == 0

        assert load_invite_config(invites_file).public_key != antiga_publica
        store = InviteStore(state_dir)
        assert store.read_private_key() != antiga_privada
        convite = issue_invite(store.read_private_key(), SENHA_CHAVE, "a@b.co", EMISSOR)
        assert verify_invite(convite.code, load_invite_config(invites_file).public_key)

    def test_emissor_sem_conta_avisa_como_criar(
        self,
        invites_file: Path,
        tmp_path: Path,
        senhas_por_ambiente: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sem o emissor no settings.yaml da pasta de estado: AVISO com o create_user, exit 0."""
        vazia = tmp_path / "outra-pasta"
        vazia.mkdir()
        assert _init(invites_file, vazia, issuer="Outro@Exemplo.com") == 0
        erro = capsys.readouterr().err
        assert "AVISO" in erro
        assert "create_user.py" in erro
        assert "Outro@Exemplo.com" in erro

    def test_emissor_com_conta_em_outra_caixa_nao_avisa(
        self,
        invites_file: Path,
        state_dir: Path,
        senhas_por_ambiente: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A conta existe (a busca ignora a caixa) → nenhum aviso."""
        assert _init(invites_file, state_dir, issuer="GABRIEL@Exemplo.com") == 0
        assert "AVISO" not in capsys.readouterr().err

    def test_pasta_de_estado_padrao_vem_do_data_home(
        self,
        invites_file: Path,
        tmp_path: Path,
        senhas_por_ambiente: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sem --state-dir vale %LOCALAPPDATA%/MCRA/config (aqui apontado para tmp_path)."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        codigo = cli.run_cli(
            ["init", "--issuer", EMISSOR, "--smtp-user", SMTP_USER,
             "--key-password-env", "T_KEY_PW", "--smtp-password-env", "T_SMTP_PW",
             "--invites-file", str(invites_file)]
        )  # fmt: skip
        assert codigo == 0
        assert (tmp_path / "local" / "MCRA" / "config" / "invite_key.pem").is_file()

    @staticmethod
    def _nada_gravado(invites_file: Path, state_dir: Path) -> None:
        store = InviteStore(state_dir)
        assert not store.has_private_key()
        assert not store.issuer_path.exists()
        assert invites_file.read_text(encoding="utf-8") == INVITES_YAML


# --------------------------------------------------------------------------- como script


class TestComoScript:
    @staticmethod
    def _rodar(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
        ambiente = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return subprocess.run(  # noqa: S603
            [sys.executable, str(_SCRIPT), *args],
            cwd=cwd,
            env=ambiente,
            capture_output=True,
            timeout=60,
            check=False,
        )

    def test_help_roda_com_diretorio_de_trabalho_fora_do_repo(self, tmp_path: Path) -> None:
        """`python scripts/setup_invites.py --help` à mão: desktop.bootstrap é importável."""
        resultado = self._rodar(tmp_path, "--help")
        assert resultado.returncode == 0, resultado.stderr.decode("utf-8", "replace")
        saida = resultado.stdout.decode("cp1252", "replace")
        assert "init" in saida
        assert "set-url" in saida

    def test_help_de_cada_comando_roda(self, tmp_path: Path) -> None:
        """init --help e set-url --help também saem sem erro (sem caractere fora do cp1252)."""
        for comando in ("init", "set-url"):
            resultado = self._rodar(tmp_path, comando, "--help")
            assert resultado.returncode == 0, resultado.stderr.decode("utf-8", "replace")
            assert b"--invites-file" in resultado.stdout
        assert b"--state-dir" in self._rodar(tmp_path, "init", "--help").stdout
