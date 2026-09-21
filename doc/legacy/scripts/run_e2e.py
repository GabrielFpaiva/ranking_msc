"""
scripts/run_e2e.py
~~~~~~~~~~~~~~~~~~

Orquestrador da suíte end-to-end (F5-06).

Fluxo:
    1. Prepara ``tests/_e2e_workdir/{config,data}`` e gera ``settings.yaml``
       com um usuário admin de teste (hash bcrypt gerado em tempo de execução).
    2. ``docker compose -f docker-compose.yml -f docker-compose.e2e.yml build``.
    3. ``docker compose ... up -d`` e aguarda ``GET /api/health`` ficar 200.
    4. Roda ``pytest tests/test_e2e_deploy.py -v`` com env vars sinalizando que
       o orquestrador externo já cuidou do Docker.
    5. Em caso de falha, despeja ``docker compose logs`` no stdout.
    6. ``docker compose ... down -v`` e limpa o workdir.

Uso::

    python scripts/run_e2e.py
    python scripts/run_e2e.py --keep   # mantém container/workdir após o teste

Saída: o exit code do pytest é propagado.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

import bcrypt

logger = logging.getLogger("ranking_msc.e2e")

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
COMPOSE_BASE: Path = PROJECT_ROOT / "docker-compose.yml"
COMPOSE_E2E: Path = PROJECT_ROOT / "docker-compose.e2e.yml"
WORKDIR: Path = PROJECT_ROOT / "tests" / "_e2e_workdir"
TEST_FILE: Path = PROJECT_ROOT / "tests" / "test_e2e_deploy.py"

DEFAULT_USERNAME: str = "e2e-admin"
DEFAULT_PASSWORD: str = "e2e-password"
DEFAULT_BASE_URL: str = "http://localhost:8099"
HEALTH_TIMEOUT_S: float = 180.0
HEALTH_POLL_INTERVAL_S: float = 2.0


def _compose_cmd(*args: str) -> list[str]:
    """Monta o comando ``docker compose`` com os dois arquivos de override."""
    return [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_BASE),
        "-f",
        str(COMPOSE_E2E),
        *args,
    ]


def _render_settings_yaml(username: str, password_hash: str) -> str:
    """Gera um ``settings.yaml`` mínimo para o ambiente E2E."""
    return (
        "# settings.yaml gerado por scripts/run_e2e.py — descartável.\n"
        "app:\n"
        '  title: "Ranking MSC — E2E"\n'
        "  debug: false\n"
        '  esfera: "municipal"\n'
        "paths:\n"
        '  data_dir: "./data"\n'
        '  snapshots_dir: "./data/snapshots"\n'
        '  reports_dir: "./data/reports"\n'
        '  logs_dir: "./data/logs"\n'
        '  ref_dir: "./ref"\n'
        "rules:\n"
        "  enabled:\n"
        '    - "R001"\n'
        '    - "R002"\n'
        '    - "R003"\n'
        '    - "R004"\n'
        '    - "R005"\n'
        '    - "R010"\n'
        '    - "R030"\n'
        '    - "R082"\n'
        "  fail_fast: false\n"
        "security:\n"
        '  secret_key: "e2e-secret-key-not-for-prod"\n'
        '  algorithm: "HS256"\n'
        "  access_token_expire_minutes: 60\n"
        "  users:\n"
        f'    - username: "{username}"\n'
        f'      hashed_password: "{password_hash}"\n'
    )


def prepare_workdir(workdir: Path, *, username: str, password: str) -> None:
    """Cria ``workdir/{config,data}`` e materializa o settings.yaml de teste."""
    if workdir.exists():
        shutil.rmtree(workdir)
    (workdir / "config").mkdir(parents=True)
    (workdir / "data" / "snapshots").mkdir(parents=True)
    (workdir / "data" / "reports").mkdir(parents=True)
    (workdir / "data" / "logs").mkdir(parents=True)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    settings_path = workdir / "config" / "settings.yaml"
    settings_path.write_text(
        _render_settings_yaml(username, password_hash), encoding="utf-8"
    )
    logger.info("Workdir E2E pronto em %s", workdir)


def teardown(
    compose_cmd_builder: Callable[..., list[str]],
    *,
    cwd: Path,
    workdir: Path,
    keep: bool = False,
) -> None:
    """Derruba o compose e limpa o workdir (a menos que ``keep=True``)."""
    try:
        subprocess.run(
            compose_cmd_builder("down", "-v"),
            cwd=cwd,
            check=False,
        )
    finally:
        if not keep and workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)


def _wait_for_health(base_url: str, timeout_s: float = HEALTH_TIMEOUT_S) -> bool:
    """Polla ``GET /api/health`` até 200 ou timeout. True em sucesso."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310 — URL controlada localmente
                f"{base_url}/api/health", timeout=3.0
            ) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(HEALTH_POLL_INTERVAL_S)
    return False


def _dump_compose_logs(compose_cmd_builder: Callable[..., list[str]], cwd: Path) -> None:
    """Despeja ``docker compose logs`` no stdout para diagnóstico."""
    logger.error("Coletando logs do container para diagnóstico...")
    subprocess.run(
        compose_cmd_builder("logs", "--no-color", "--tail", "200"),
        cwd=cwd,
        check=False,
    )


def _run_pytest(base_url: str, username: str, password: str) -> int:
    """Executa ``pytest tests/test_e2e_deploy.py`` com env vars adequadas."""
    env = os.environ.copy()
    env.update(
        {
            "RANKING_MSC_E2E": "1",
            "E2E_EXTERNAL_DOCKER": "1",
            "E2E_BASE_URL": base_url,
            "E2E_USERNAME": username,
            "E2E_PASSWORD": password,
        }
    )
    cmd: Sequence[str] = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_FILE),
        "-v",
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False)
    return proc.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint CLI do orquestrador E2E."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(description="Roda a suíte E2E F5-06.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Não derrubar container nem limpar workdir ao final.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"URL base do serviço (padrão: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args(argv)

    if not shutil.which("docker"):
        logger.error("Docker não encontrado no PATH. Instale Docker Desktop.")
        return 2

    prepare_workdir(WORKDIR, username=args.username, password=args.password)

    logger.info("Buildando imagem...")
    build_proc = subprocess.run(
        _compose_cmd("build"), cwd=PROJECT_ROOT, check=False
    )
    if build_proc.returncode != 0:
        logger.error("Falha no build do compose.")
        teardown(_compose_cmd, cwd=PROJECT_ROOT, workdir=WORKDIR, keep=args.keep)
        return build_proc.returncode

    logger.info("Subindo serviço em background...")
    up_proc = subprocess.run(
        _compose_cmd("up", "-d"), cwd=PROJECT_ROOT, check=False
    )
    if up_proc.returncode != 0:
        logger.error("Falha ao subir o compose.")
        _dump_compose_logs(_compose_cmd, PROJECT_ROOT)
        teardown(_compose_cmd, cwd=PROJECT_ROOT, workdir=WORKDIR, keep=args.keep)
        return up_proc.returncode

    if not _wait_for_health(args.base_url):
        logger.error("Healthcheck não passou dentro do timeout.")
        _dump_compose_logs(_compose_cmd, PROJECT_ROOT)
        teardown(_compose_cmd, cwd=PROJECT_ROOT, workdir=WORKDIR, keep=args.keep)
        return 1

    logger.info("Serviço saudável em %s — executando pytest...", args.base_url)
    rc = _run_pytest(args.base_url, args.username, args.password)
    if rc != 0:
        _dump_compose_logs(_compose_cmd, PROJECT_ROOT)

    teardown(_compose_cmd, cwd=PROJECT_ROOT, workdir=WORKDIR, keep=args.keep)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
