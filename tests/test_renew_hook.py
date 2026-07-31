"""
tests/test_renew_hook.py
~~~~~~~~~~~~~~~~~~~~~~~~

Testes do deploy-hook de renovação TLS (`scripts/deploy/renew-hook.sh`).

O hook é chamado pelo certbot após renovar o certificado. Ele precisa:
  * dereferenciar os symlinks de /etc/letsencrypt/live/<domínio>;
  * publicar os PEMs em docker/nginx/certs/ (contrato lido pelo nginx.conf);
  * recarregar o nginx sem derrubar conexões;
  * não falhar quando o stack está fora do ar (cert copiado vale no próximo boot).
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
def compose_spy(tmp_path: Path) -> tuple[Path, Path]:
    """Stub de `docker compose` que registra a invocação num arquivo."""
    log = tmp_path / "compose-invocado.log"
    stub = tmp_path / "compose-stub.sh"
    stub.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nexit 0\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub, log


def _run(hook_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa o hook com ambiente controlado.

    As tres variaveis do contrato sao removidas do ambiente herdado antes de
    aplicar `hook_env` — senao um valor presente na maquina do dev faria o
    teste de variavel ausente passar por engano.
    """
    env = os.environ.copy()
    for var in ("RANKING_MSC_REPO_DIR", "RENEWED_LINEAGE", "DOCKER_COMPOSE_CMD"):
        env.pop(var, None)
    env.update(hook_env)
    return subprocess.run(
        ["sh", str(HOOK)], env=env, capture_output=True, text=True
    )


def test_hook_publica_pems_dereferenciando_symlinks(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy: tuple[Path, Path]
) -> None:
    """Os PEMs chegam em docker/nginx/certs/ como arquivos reais, não symlinks."""
    stub, _ = compose_spy
    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_CMD": str(stub),
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
    fake_letsencrypt: Path, fake_repo: Path, compose_spy: tuple[Path, Path]
) -> None:
    """A chave privada não pode ficar legível para outros usuários."""
    stub, _ = compose_spy
    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_CMD": str(stub),
        }
    )

    privkey = fake_repo / "docker" / "nginx" / "certs" / "privkey.pem"
    assert stat.S_IMODE(privkey.stat().st_mode) == 0o600


def test_hook_recarrega_nginx(
    fake_letsencrypt: Path, fake_repo: Path, compose_spy: tuple[Path, Path]
) -> None:
    """O hook manda o nginx reler o certificado."""
    stub, log = compose_spy
    _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_CMD": str(stub),
        }
    )

    invocacao = log.read_text()
    assert "nginx" in invocacao
    assert "-s reload" in invocacao


def test_hook_nao_falha_com_stack_fora_do_ar(
    fake_letsencrypt: Path, fake_repo: Path, tmp_path: Path
) -> None:
    """Stack parado não é erro: o cert já está no lugar para o próximo boot."""
    stub = tmp_path / "compose-falha.sh"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    result = _run(
        {
            "RANKING_MSC_REPO_DIR": str(fake_repo),
            "RENEWED_LINEAGE": str(fake_letsencrypt),
            "DOCKER_COMPOSE_CMD": str(stub),
        }
    )

    assert result.returncode == 0
    assert (fake_repo / "docker" / "nginx" / "certs" / "fullchain.pem").exists()


def test_hook_exige_repo_dir(
    fake_letsencrypt: Path, tmp_path: Path
) -> None:
    """Sem RANKING_MSC_REPO_DIR o hook falha alto, em vez de escrever no lugar errado."""
    result = _run({"RENEWED_LINEAGE": str(fake_letsencrypt)})
    assert result.returncode != 0
    assert "RANKING_MSC_REPO_DIR" in (result.stderr + result.stdout)
