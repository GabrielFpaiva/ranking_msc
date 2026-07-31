"""
tests/test_renew_hook.py
~~~~~~~~~~~~~~~~~~~~~~~~

Testes do deploy-hook de renovação TLS (`scripts/deploy/renew-hook.sh`).

O hook é chamado pelo certbot após renovar o certificado. Ele precisa:
  * dereferenciar os symlinks de /etc/letsencrypt/live/<domínio>;
  * publicar os PEMs em docker/nginx/certs/ (contrato lido pelo nginx.conf);
  * recarregar o nginx sem derrubar conexões;
  * tolerar quando o stack está fora do ar (cert copiado vale no próximo boot);
  * falhar quando o stack está rodando mas o reload falha (erro real, não config).
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK = PROJECT_ROOT / "scripts" / "deploy" / "renew-hook.sh"


@pytest.fixture
def fake_letsencrypt(tmp_path: Path) -> Path:
    """Reproduz o layout real do certbot: live/ com symlinks para archive/."""
    archive = tmp_path / "archive" / "exemplo.duckdns.org"
    archive.mkdir(parents=True)
    (archive / "fullchain1.pem").write_text("FULLCHAIN-CONTEUDO")
    (archive / "privkey1.pem").write_text("PRIVKEY-CONTEUDO")

    live = tmp_path / "live" / "exemplo.duckdns.org"
    live.mkdir(parents=True)
    (live / "fullchain.pem").symlink_to(archive / "fullchain1.pem")
    (live / "privkey.pem").symlink_to(archive / "privkey1.pem")
    return live


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Raiz de repo mínima, com o compose de produção que o hook referencia."""
    repo = tmp_path / "repo"
    (repo / "docker" / "nginx").mkdir(parents=True)
    (repo / "docker-compose.prod.yml").write_text("services: {}\n")
    return repo


# Helper de shell compartilhado pelos stubs: casa exatamente a invocação que
# o hook faz para checar estado -- "compose_cmd -f docker-compose.prod.yml
# ps -q nginx". Quebrado em função para não estourar o limite de linha do
# arquivo .py (o teste embute isto num heredoc, não é código Python).
_IS_PS_Q = '''
is_ps_q() {
  [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] \\
    && [ "$3" = "ps" ] && [ "$4" = "-q" ]
}
'''

_PS_Q_DISPATCH = (
    _IS_PS_Q
    + '''
# Se é um 'ps -q', devolver o ID hexadecimal (stack rodando) -- o mesmo
# formato que "docker compose ps -q" devolve de verdade. É isto que o hook
# usa para detectar o estado; nunca a palavra "running" (docker compose ps
# nunca imprime essa palavra -- ver comentário no hook).
if is_ps_q "$@"; then
  echo "a1b2c3d4e5f6"
  exit 0
fi
'''
)

_PS_Q_EMPTY_DISPATCH = (
    _IS_PS_Q
    + '''
# Se é um 'ps -q', devolver vazio (stack parado) -- reproduz "docker
# compose ps -q" com nenhum container correspondente.
if is_ps_q "$@"; then
  exit 0
fi
'''
)


@pytest.fixture
def compose_spy_stack_running(tmp_path: Path) -> tuple[Path, Path]:
    """Stub que simula stack rodando (ps -q devolve ID, exec sucede)."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
{_PS_Q_DISPATCH}
# Se é um 'exec', suceder
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "exec" ]; then
  exit 0
fi
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


@pytest.fixture
def compose_spy_stack_stopped(tmp_path: Path) -> tuple[Path, Path]:
    """Stub que simula stack parado (ps -q não devolve ID nenhum)."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
{_PS_Q_EMPTY_DISPATCH}
# Qualquer outro comando sai 1 (stack parado)
exit 1
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


@pytest.fixture
def compose_stub_exec_fails(tmp_path: Path) -> tuple[Path, Path]:
    """Stub que simula stack rodando mas exec (reload) falha."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
{_PS_Q_DISPATCH}
# Se é um 'exec', falhar (reload falha mesmo com stack rodando)
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "exec" ]; then
  exit 1
fi
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


@pytest.fixture
def compose_spy_stack_running_tabela_real(tmp_path: Path) -> tuple[Path, Path]:
    """Stub que reproduz a saída REAL do 'docker compose ps' (sem -q): a tabela
    humana com STATUS "Up X minutes (healthy)" -- sem a palavra "running" em
    lugar nenhum. Só o 'ps -q' devolve o ID do container.

    Este stub existe para provar que a detecção funciona com a saída real do
    Docker, não com uma premissa inventada: com a implementação antiga
    (`ps nginx | grep -q running`), este stub faria o hook cair sempre no
    ramo "stack parado" -- o mesmo bug de produção que motivou a correção.
    """
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] \\
    && [ "$3" = "ps" ]; then
  if [ "$4" = "-q" ]; then
    echo "a1b2c3d4e5f6"
  else
    # Formato real do "docker compose ps": tabela com STATUS humano,
    # nunca a palavra "running".
    printf "NAME          SERVICE  STATUS\\n"
    printf "proj-nginx-1  nginx    Up 2 minutes (healthy)\\n"
  fi
  exit 0
fi
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] \\
    && [ "$3" = "exec" ]; then
  exit 0
fi
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


def _run(
    hook_env: dict[str, str], hook_path: Path = HOOK
) -> subprocess.CompletedProcess[str]:
    """Executa o hook com ambiente controlado.

    As variaveis do contrato sao removidas do ambiente herdado antes de
    aplicar `hook_env` — senao um valor presente na maquina do dev faria o
    teste de variavel ausente passar por engano.

    `hook_path` permite executar uma cópia do script montada em outro lugar
    (usado pelos testes de derivação de RANKING_MSC_REPO_DIR a partir do
    próprio caminho do script — ver `_copy_hook_into`).
    """
    env = os.environ.copy()
    for var in (
        "RANKING_MSC_REPO_DIR",
        "RENEWED_LINEAGE",
        "DOCKER_COMPOSE_BIN",
        "DOCKER_COMPOSE_SUBCMD",
    ):
        env.pop(var, None)
    env.update(hook_env)
    return subprocess.run(
        ["sh", str(hook_path)], env=env, capture_output=True, text=True
    )


def _copy_hook_into(repo_root: Path) -> Path:
    """Copia o hook real para `<repo_root>/scripts/deploy/renew-hook.sh`.

    Reproduz o layout que a derivação de REPO_DIR assume (script mora em
    `<repo>/scripts/deploy/`), mas apontando para um repo falso descartável
    em vez do repositório real — assim o teste nunca escreve em
    `docker/nginx/certs/` do projeto de verdade.
    """
    deploy_dir = repo_root / "scripts" / "deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    hook_copy = deploy_dir / "renew-hook.sh"
    hook_copy.write_text(HOOK.read_text())
    hook_copy.chmod(hook_copy.stat().st_mode | stat.S_IEXEC)
    return hook_copy


def test_hook_publica_pems_dereferenciando_symlinks(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy_stack_running: tuple[Path, Path]
) -> None:
    """Os PEMs chegam em docker/nginx/certs/ como arquivos reais, não symlinks."""
    stub, _ = compose_spy_stack_running
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    assert result.returncode == 0, result.stderr
    certs = fake_repo / "docker" / "nginx" / "certs"
    fullchain = certs / "fullchain.pem"
    privkey = certs / "privkey.pem"

    assert fullchain.read_text() == "FULLCHAIN-CONTEUDO"
    assert privkey.read_text() == "PRIVKEY-CONTEUDO"
    assert not fullchain.is_symlink()
    assert not privkey.is_symlink()


def test_hook_restringe_permissao_da_chave_privada(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy_stack_running: tuple[Path, Path]
) -> None:
    """A chave privada não pode ficar legível para outros usuários."""
    stub, _ = compose_spy_stack_running
    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    privkey = fake_repo / "docker" / "nginx" / "certs" / "privkey.pem"
    assert stat.S_IMODE(privkey.stat().st_mode) == 0o600


def test_hook_fullchain_termina_com_permissao_644(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy_stack_running: tuple[Path, Path]
) -> None:
    """O fullchain.pem deve terminar com 0o644 apesar do umask 077."""
    stub, _ = compose_spy_stack_running
    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    fullchain = fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem"
    assert stat.S_IMODE(fullchain.stat().st_mode) == 0o644


def test_hook_recarrega_nginx(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy_stack_running: tuple[Path, Path]
) -> None:
    """O hook manda o nginx reler o certificado."""
    stub, log = compose_spy_stack_running
    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    invocacao = log.read_text()
    assert "exec" in invocacao
    assert "nginx" in invocacao
    assert "-s reload" in invocacao


def test_hook_detecta_stack_rodando_pela_saida_real_do_compose(
    fake_letsencrypt: Path,
    fake_repo: Path,
    compose_spy_stack_running_tabela_real: tuple[Path, Path],
) -> None:
    """Regressão do C1: com a saída REAL do 'docker compose ps' (tabela
    "Up 2 minutes (healthy)", sem a palavra "running" em lugar nenhum), o
    hook deve mesmo assim detectar o stack rodando e tentar o reload.

    Este teste falharia com a implementação antiga
    (`ps nginx | grep -q running`): a tabela real nunca contém "running",
    então o grep nunca casaria e o hook cairia sempre no ramo "stack
    parado" -- o nginx nunca recarregaria o certificado novo em produção.
    """
    stub, log = compose_spy_stack_running_tabela_real
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    assert result.returncode == 0, result.stderr
    invocacao = log.read_text()
    assert "exec" in invocacao
    assert "-s reload" in invocacao


def test_hook_nao_falha_com_stack_parado(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy_stack_stopped: tuple[Path, Path]
) -> None:
    """Stack parado não é erro: o cert já está no lugar para o próximo boot."""
    stub, _ = compose_spy_stack_stopped
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    assert result.returncode == 0, result.stderr
    assert (fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists()


def test_hook_falha_se_reload_falha_e_stack_rodando(
    fake_letsencrypt: Path, fake_repo: Path, compose_stub_exec_fails: tuple[Path, Path]
) -> None:
    """Stack rodando mas reload falhando = erro real; hook deve sair com código não-zero."""
    stub, _ = compose_stub_exec_fails
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    assert result.returncode != 0
    assert "erro: nginx reload falhou" in (result.stderr + result.stdout)


def test_hook_valida_repo_dir_existe(
    fake_letsencrypt: Path, tmp_path: Path
) -> None:
    """RANKING_MSC_REPO_DIR (override) inexistente = erro alto."""
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(tmp_path / "nao-existe"),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
        }
    )
    assert result.returncode != 0
    assert "raiz do repositorio invalida" in (result.stderr + result.stdout)


def test_hook_valida_compose_arquivo_existe(
    fake_letsencrypt: Path, tmp_path: Path
) -> None:
    """docker-compose.prod.yml ausente = erro alto."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Criar sem docker-compose.prod.yml
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
        }
    )
    assert result.returncode != 0
    assert "docker-compose.prod.yml" in (result.stderr + result.stdout)


def test_hook_suporta_docker_compose_bin_com_espaco_no_caminho(
    fake_letsencrypt: Path, fake_repo: Path, tmp_path: Path
) -> None:
    """DOCKER_COMPOSE_BIN com espaços no caminho deve ser invocado corretamente."""
    # Criar um diretório com espaço e um stub dentro
    bindir = tmp_path / "bin com espaco"
    bindir.mkdir()
    log = tmp_path / "log.txt"
    stub = bindir / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
# Registrar a invocação — prova que o binário foi invocado
echo "invocado" >> "{log}"
{_PS_Q_DISPATCH}
# Se é um 'exec', suceder
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "exec" ]; then
  exit 0
fi
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    assert result.returncode == 0, result.stderr
    assert (fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists()
    # Prova não-tautológica: o stub foi realmente invocado
    assert log.exists() and log.read_text().strip(), "Stub não foi invocado"


@pytest.mark.parametrize(
    "make_payload",
    [
        pytest.param(lambda stub, proof: f"{stub}; touch {proof}", id="ponto-e-virgula"),
        pytest.param(lambda stub, proof: f"{stub}`touch {proof}`", id="backtick"),
        pytest.param(lambda stub, proof: f"{stub}$(touch {proof})", id="dollar-parenteses"),
    ],
)
def test_hook_nao_sofre_injecao_via_docker_compose_bin(
    fake_letsencrypt: Path,
    fake_repo: Path,
    tmp_path: Path,
    make_payload: Callable[[Path, Path], str],
) -> None:
    """DOCKER_COMPOSE_BIN com metacaracteres de shell (';', backtick, '$()')
    não deve executar a injeção -- o valor é sempre usado como caminho de
    executável (quoted), nunca interpolado num `eval` ou `sh -c`."""
    # Criar um binário que falharia em ps (simular stack parado) mas não executaria injeção
    injection_proof = tmp_path / "injection-proof.txt"
    stub = tmp_path / "malicious.sh"
    stub.write_text(
        f'''#!/bin/sh
# Comando malicioso que tentaria ser injetado
echo "Tentativa de injeção"
touch "{injection_proof}"
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": make_payload(stub, injection_proof),
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    # Hook deve falhar (arquivo não encontrado) ou suceder (stack parado) sem executar injeção
    # O importante é que injection_proof.txt NÃO foi criado pela injeção
    assert not injection_proof.exists(), "Injeção de comando foi executada!"


def test_hook_deriva_repo_dir_do_proprio_caminho_quando_env_ausente(
    fake_letsencrypt: Path,
    fake_repo: Path,
    compose_spy_stack_running: tuple[Path, Path],
) -> None:
    """Regressão do C2: sem RANKING_MSC_REPO_DIR (ambiente limpo do timer
    systemd do certbot), o hook deriva a raiz a partir do próprio caminho —
    ele mora em `<repo>/scripts/deploy/renew-hook.sh`, subir dois níveis
    chega na raiz. A cópia do hook é colocada dentro de `fake_repo` nesse
    layout para que a derivação aponte para o repo falso, não para o
    repositório real do projeto."""
    stub, _ = compose_spy_stack_running
    hook_copy = _copy_hook_into(fake_repo)

    result = _run(
        {
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        },
        hook_path=hook_copy,
    )

    assert result.returncode == 0, result.stderr
    assert (fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists()


def test_hook_falha_alto_sem_override_e_com_derivacao_invalida(
    fake_letsencrypt: Path,
    tmp_path: Path,
    compose_spy_stack_running: tuple[Path, Path],
) -> None:
    """Sem `RANKING_MSC_REPO_DIR` e com a derivação apontando para um diretório
    que não é repo (sem `docker-compose.prod.yml`), o hook deve falhar alto.

    Este é o espaço que o antigo `test_hook_exige_repo_dir` cobria antes de o
    fallback do C2 tornar a variável opcional: sem esta guarda, um refactor que
    movesse a validação para dentro do ramo do override passaria verde e o hook
    voltaria a gravar PEMs num caminho inválido, saindo 0."""
    stub, _ = compose_spy_stack_running
    nao_repo = tmp_path / "nao-e-repo"
    hook_copy = _copy_hook_into(nao_repo)

    result = _run(
        {
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        },
        hook_path=hook_copy,
    )

    assert result.returncode != 0, (
        "hook deveria falhar: sem override e a derivacao nao aponta para um repo"
    )
    saida = result.stderr + result.stdout
    assert "RANKING_MSC_REPO_DIR" in saida, (
        f"a mensagem precisa citar o override como saida; recebido: {saida!r}"
    )
    assert not (nao_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists(), (
        "nenhum PEM pode ser publicado quando a raiz e invalida"
    )


def test_hook_ranking_msc_repo_dir_e_override_sobre_derivacao(
    fake_letsencrypt: Path,
    fake_repo: Path,
    tmp_path: Path,
    compose_spy_stack_running: tuple[Path, Path],
) -> None:
    """RANKING_MSC_REPO_DIR definida vence a derivação pelo caminho do
    script. A cópia do hook fica em `<tmp>/outro-lugar/scripts/deploy/` (que
    NÃO é um repo válido -- sem docker-compose.prod.yml); só passa porque o
    override aponta para `fake_repo`, provando que a derivação foi
    ignorada."""
    stub, _ = compose_spy_stack_running
    outro_lugar = tmp_path / "outro-lugar"
    hook_copy = _copy_hook_into(outro_lugar)

    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_BIN": str(stub),
            "DOCKER_COMPOSE_SUBCMD": "",
        },
        hook_path=hook_copy,
    )

    assert result.returncode == 0, result.stderr
    assert (fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists()


def test_hook_exige_renewed_lineage(fake_repo: Path) -> None:
    """Sem RENEWED_LINEAGE o hook falha alto."""
    result = _run({"RANKING_MSC_REPO_DIR": str(fake_repo)})
    assert result.returncode != 0
    assert "RENEWED_LINEAGE" in (result.stderr + result.stdout)
