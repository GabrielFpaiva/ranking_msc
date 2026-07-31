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


@pytest.fixture
def compose_spy_stack_running(tmp_path: Path) -> tuple[Path, Path]:
    """Stub que simula stack rodando (ps mostra 'running', exec sucede)."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
# Se é um 'ps', retornar com "running"
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "ps" ]; then
  echo "nginx  running"
  exit 0
fi
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
    """Stub que simula stack parado (ps não mostra 'running')."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(
        f'''#!/bin/sh
echo "$@" >> "{log}"
# Se é um 'ps', retornar sem "running" (stack parado)
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "ps" ]; then
  echo "nginx  exited (1) or other state"
  exit 0
fi
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
# Se é um 'ps', retornar com "running"
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "ps" ]; then
  echo "nginx  running"
  exit 0
fi
# Se é um 'exec', falhar (reload falha mesmo com stack rodando)
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "exec" ]; then
  exit 1
fi
exit 0
'''
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


def _run(hook_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa o hook com ambiente controlado.

    As variaveis do contrato sao removidas do ambiente herdado antes de
    aplicar `hook_env` — senao um valor presente na maquina do dev faria o
    teste de variavel ausente passar por engano.
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
        ["sh", str(HOOK)], env=env, capture_output=True, text=True
    )


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
    """RANKING_MSC_REPO_DIR inexistente = erro alto."""
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(tmp_path / "nao-existe"),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
        }
    )
    assert result.returncode != 0
    assert "nao e um diretorio" in (result.stderr + result.stdout)


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
# Se é um 'ps', retornar com "running"
if [ "$1" = "-f" ] && [ "$2" = "docker-compose.prod.yml" ] && [ "$3" = "ps" ]; then
  echo "nginx  running"
  exit 0
fi
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


def test_hook_nao_sofre_injecao_via_docker_compose_bin(
    fake_letsencrypt: Path, fake_repo: Path, tmp_path: Path
) -> None:
    """DOCKER_COMPOSE_BIN com ';' e comando malicioso não deve executar a injeção."""
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
            # Usar valor contendo ';' que seria problemático com eval
            "DOCKER_COMPOSE_BIN": f"{stub}; touch {injection_proof}",
            "DOCKER_COMPOSE_SUBCMD": "",
        }
    )

    # Hook deve falhar (arquivo não encontrado) ou suceder (stack parado) sem executar injeção
    # O importante é que injection_proof.txt NÃO foi criado pela injeção
    assert not injection_proof.exists(), "Injeção de comando foi executada!"


def test_hook_exige_repo_dir(
    fake_letsencrypt: Path, tmp_path: Path
) -> None:
    """Sem RANKING_MSC_REPO_DIR o hook falha alto."""
    result = _run({"RENEWED_LINEAGE": str(fake_letsencrypt)})
    assert result.returncode != 0
    assert "RANKING_MSC_REPO_DIR" in (result.stderr + result.stdout)


def test_hook_exige_renewed_lineage(fake_repo: Path) -> None:
    """Sem RENEWED_LINEAGE o hook falha alto."""
    result = _run({"RANKING_MSC_REPO_DIR": str(fake_repo)})
    assert result.returncode != 0
    assert "RENEWED_LINEAGE" in (result.stderr + result.stdout)
