"""
tests/test_e2e_deploy.py
~~~~~~~~~~~~~~~~~~~~~~~~

Suíte end-to-end (F5-06) que valida o sistema completo rodando dentro do
container Docker. Ao contrário dos demais testes deste repositório, esta
suíte:

* Sobe o stack Docker (`docker compose -f docker-compose.yml -f docker-compose.e2e.yml`)
  via fixture de escopo ``session`` — ou apenas valida saúde se um orquestrador
  externo (``scripts/run_e2e.py``) já cuidou disso, sinalizando por
  ``E2E_EXTERNAL_DOCKER=1``;
* Faz login real via ``POST /api/auth/token`` para obter JWT;
* Bate nos endpoints reais via ``httpx`` com a URL pública do container.

A suíte fica desabilitada por padrão (skip de módulo) para não interferir
no ``pytest`` da Fase 4. Para rodá-la diretamente::

    set RANKING_MSC_E2E=1
    pytest tests/test_e2e_deploy.py -v

Ou via orquestrador, que faz tudo de uma vez::

    python scripts/run_e2e.py
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

logger = logging.getLogger("ranking_msc.e2e")

if not os.environ.get("RANKING_MSC_E2E"):
    pytest.skip(
        "E2E suite desabilitada — defina RANKING_MSC_E2E=1 ou rode "
        "scripts/run_e2e.py.",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Configuração compartilhada via env vars (preenchidas pelo orquestrador
# externo ou padronizadas para execução standalone).
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
COMPOSE_BASE: Path = PROJECT_ROOT / "docker-compose.yml"
COMPOSE_E2E: Path = PROJECT_ROOT / "docker-compose.e2e.yml"
WORKDIR: Path = PROJECT_ROOT / "tests" / "_e2e_workdir"
SAMPLES_DIR: Path = PROJECT_ROOT / "ref" / "amostras"

DEFAULT_BASE_URL: str = "http://localhost:8099"
HEALTH_TIMEOUT_S: float = 120.0
HEALTH_POLL_INTERVAL_S: float = 2.0

E2E_USERNAME: str = os.environ.get("E2E_USERNAME", "e2e-admin")
E2E_PASSWORD: str = os.environ.get("E2E_PASSWORD", "e2e-password")
E2E_BASE_URL: str = os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL)
E2E_EXTERNAL_DOCKER: bool = os.environ.get("E2E_EXTERNAL_DOCKER") == "1"

SICONFI_AMOSTRA: str = "2507507EX"
COMPETENCIA_PRIMARIA: str = "2025-11"
COMPETENCIA_SECUNDARIA: str = "2025-12"


# ---------------------------------------------------------------------------
# Helpers de subprocess + healthcheck
# ---------------------------------------------------------------------------


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


def _wait_until_healthy(base_url: str, timeout_s: float = HEALTH_TIMEOUT_S) -> None:
    """Polla ``GET /api/health`` até ``200`` ou timeout."""
    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=3.0)
            if response.status_code == 200:
                logger.info("Serviço E2E saudável em %s", base_url)
                return
            last_exc = RuntimeError(
                f"Health respondeu {response.status_code}: {response.text[:200]}"
            )
        except httpx.HTTPError as exc:
            last_exc = exc
        time.sleep(HEALTH_POLL_INTERVAL_S)
    raise TimeoutError(
        f"Timeout aguardando {base_url}/api/health após {timeout_s:.0f}s "
        f"(último erro: {last_exc!r})"
    )


# ---------------------------------------------------------------------------
# Fixtures de ciclo de vida do container
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_compose_up() -> Generator[str, None, None]:
    """Sobe o stack Docker (build + up) e derruba ao final.

    Quando ``E2E_EXTERNAL_DOCKER=1`` está setado, assume-se que o
    orquestrador externo (``scripts/run_e2e.py``) já trouxe o serviço e
    apenas valida-se o health antes de seguir.

    Yields:
        URL base do serviço (ex: ``http://localhost:8099``).
    """
    if E2E_EXTERNAL_DOCKER:
        _wait_until_healthy(E2E_BASE_URL)
        yield E2E_BASE_URL
        return

    # Modo standalone: gerencia ciclo completo aqui dentro. Recorre ao
    # script de orquestração por subprocesso para evitar acoplamento direto
    # de import (scripts/ não é um pacote instalável).
    _standalone_prepare_workdir()
    try:
        subprocess.run(
            _compose_cmd("up", "--build", "-d"),
            cwd=PROJECT_ROOT,
            check=True,
        )
        _wait_until_healthy(E2E_BASE_URL)
        yield E2E_BASE_URL
    finally:
        subprocess.run(_compose_cmd("down", "-v"), cwd=PROJECT_ROOT, check=False)
        if WORKDIR.exists():
            shutil.rmtree(WORKDIR, ignore_errors=True)


def _standalone_prepare_workdir() -> None:
    """Materializa workdir + settings.yaml usando helper do script."""
    import bcrypt  # noqa: PLC0415 — só carrega no modo standalone

    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    (WORKDIR / "config").mkdir(parents=True)
    (WORKDIR / "data" / "snapshots").mkdir(parents=True)
    (WORKDIR / "data" / "reports").mkdir(parents=True)
    (WORKDIR / "data" / "logs").mkdir(parents=True)

    password_hash = bcrypt.hashpw(
        E2E_PASSWORD.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    settings_yaml = (
        "app:\n"
        '  title: "Ranking MSC — E2E"\n'
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
        "  fail_fast: false\n"
        "security:\n"
        "  max_concurrent_jobs: 3\n"
        '  secret_key: "e2e-secret-key-not-for-prod"\n'
        '  algorithm: "HS256"\n'
        "  access_token_expire_minutes: 60\n"
        "  users:\n"
        f'    - username: "{E2E_USERNAME}"\n'
        f'      hashed_password: "{password_hash}"\n'
    )
    (WORKDIR / "config" / "settings.yaml").write_text(settings_yaml, encoding="utf-8")


@pytest.fixture(scope="session")
def httpx_client(docker_compose_up: str) -> Generator[httpx.Client, None, None]:
    """Cliente HTTP apontado para o serviço E2E."""
    with httpx.Client(base_url=docker_compose_up, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def auth_token(httpx_client: httpx.Client) -> str:
    """Faz login com credenciais de teste e devolve o JWT."""
    response = httpx_client.post(
        "/api/auth/token",
        data={"username": E2E_USERNAME, "password": E2E_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        pytest.fail(
            f"Login E2E falhou ({response.status_code}): {response.text[:400]}"
        )
    payload = response.json()
    token = payload.get("access_token")
    assert isinstance(token, str) and token, "Token vazio na resposta de login"
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict[str, str]:
    """Headers ``Authorization`` prontos para uso nos requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def pipeline_executed(
    httpx_client: httpx.Client, auth_headers: dict[str, str]
) -> dict[str, object]:
    """Roda o pipeline para as duas competências de amostra e devolve o
    summary da execução primária. Compartilhado entre vários testes para
    evitar uploads duplicados.
    """
    sample_primary = SAMPLES_DIR / f"msc_{COMPETENCIA_PRIMARIA}.csv"
    sample_secondary = SAMPLES_DIR / f"msc_{COMPETENCIA_SECUNDARIA}.csv"
    assert sample_primary.is_file(), f"Amostra ausente: {sample_primary}"
    assert sample_secondary.is_file(), f"Amostra ausente: {sample_secondary}"

    primary_summary = _upload_and_run(httpx_client, auth_headers, sample_primary)
    _upload_and_run(httpx_client, auth_headers, sample_secondary)
    return primary_summary


def _upload_and_run(
    client: httpx.Client, headers: dict[str, str], csv_path: Path
) -> dict[str, object]:
    """Faz POST /api/run com o CSV indicado e devolve o JSON do summary."""
    with csv_path.open("rb") as fh:
        response = client.post(
            "/api/run",
            headers=headers,
            files={"file": (csv_path.name, fh, "text/csv")},
            timeout=120.0,
        )
    assert response.status_code == 200, (
        f"/api/run falhou para {csv_path.name}: {response.status_code} "
        f"{response.text[:400]}"
    )
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


# ---------------------------------------------------------------------------
# Cenários E2E
# ---------------------------------------------------------------------------


class TestE2EDeploy:
    """Cenários ponta-a-ponta contra o container Docker em execução."""

    def test_health_check(self, httpx_client: httpx.Client) -> None:
        """``GET /api/health`` responde 200 com status ok."""
        response = httpx_client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert int(body["rules_enabled"]) > 0

    def test_login_valido(self, httpx_client: httpx.Client) -> None:
        """``POST /api/auth/token`` com credenciais válidas devolve JWT."""
        response = httpx_client.post(
            "/api/auth/token",
            data={"username": E2E_USERNAME, "password": E2E_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["token_type"] == "bearer"
        assert len(payload["access_token"]) > 20

    def test_login_invalido(self, httpx_client: httpx.Client) -> None:
        """Credenciais inválidas devolvem 401."""
        response = httpx_client.post(
            "/api/auth/token",
            data={"username": E2E_USERNAME, "password": "senha-errada"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401

    def test_upload_csv_e_processamento(
        self, pipeline_executed: dict[str, object]
    ) -> None:
        """``POST /api/run`` retorna summary com score válido."""
        assert pipeline_executed["siconfi"] == SICONFI_AMOSTRA
        assert pipeline_executed["competencia"] == COMPETENCIA_PRIMARIA
        assert pipeline_executed["status"] in {"OK", "ERRO", "ALERTA"}
        score = pipeline_executed["score"]
        assert isinstance(score, dict)
        assert 0 <= float(score["pontuacao"]) <= 100
        assert score["banda"] in {"A", "B", "C", "D", "E"}

    def test_consulta_resultados_score(
        self,
        httpx_client: httpx.Client,
        auth_headers: dict[str, str],
        pipeline_executed: dict[str, object],  # noqa: ARG002 — força ordem
    ) -> None:
        """``GET /api/score`` devolve o score persistido."""
        response = httpx_client.get(
            "/api/score",
            params={"siconfi": SICONFI_AMOSTRA, "competencia": COMPETENCIA_PRIMARIA},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert 0 <= float(body["pontuacao"]) <= 100
        assert "dimensions" in body and isinstance(body["dimensions"], dict)

    def test_consulta_snapshots_competencias(
        self,
        httpx_client: httpx.Client,
        auth_headers: dict[str, str],
        pipeline_executed: dict[str, object],  # noqa: ARG002
    ) -> None:
        """``GET /api/competencias`` lista as competências processadas."""
        response = httpx_client.get(
            "/api/competencias",
            params={"siconfi": SICONFI_AMOSTRA},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        items = response.json()
        competencias = {item["competencia"] for item in items}
        assert COMPETENCIA_PRIMARIA in competencias
        assert COMPETENCIA_SECUNDARIA in competencias

    def test_compare_entre_competencias(
        self,
        httpx_client: httpx.Client,
        auth_headers: dict[str, str],
        pipeline_executed: dict[str, object],  # noqa: ARG002
    ) -> None:
        """``GET /api/compare`` devolve diff entre duas competências."""
        response = httpx_client.get(
            "/api/compare",
            params={
                "siconfi": SICONFI_AMOSTRA,
                "a": COMPETENCIA_PRIMARIA,
                "b": COMPETENCIA_SECUNDARIA,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["a"]["competencia"] == COMPETENCIA_PRIMARIA
        assert body["b"]["competencia"] == COMPETENCIA_SECUNDARIA
        assert "delta_score" in body
        assert isinstance(body["dimensions"], list)

    def test_export_excel(
        self,
        httpx_client: httpx.Client,
        auth_headers: dict[str, str],
        pipeline_executed: dict[str, object],  # noqa: ARG002
    ) -> None:
        """``GET /api/exports/excel`` devolve um .xlsx válido (assinatura ZIP)."""
        response = httpx_client.get(
            "/api/exports/excel",
            params={"siconfi": SICONFI_AMOSTRA, "competencia": COMPETENCIA_PRIMARIA},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text[:400]
        # xlsx = arquivo zip → magic bytes "PK\x03\x04"
        assert response.content[:4] == b"PK\x03\x04"

    def test_frontend_servido(self, httpx_client: httpx.Client) -> None:
        """``GET /`` devolve o HTML do React (com tag ``<div id="root">``)."""
        response = httpx_client.get("/")
        assert response.status_code == 200
        body = response.text.lower()
        assert "<html" in body
        assert 'id="root"' in body

    def test_endpoints_protegidos_sem_token(
        self, httpx_client: httpx.Client
    ) -> None:
        """Endpoints com ``Depends(get_current_user)`` rejeitam sem Bearer."""
        endpoints = [
            ("/api/competencias", {}),
            ("/api/score", {"siconfi": SICONFI_AMOSTRA, "competencia": COMPETENCIA_PRIMARIA}),
            ("/api/pendencias", {"siconfi": SICONFI_AMOSTRA, "competencia": COMPETENCIA_PRIMARIA}),
            ("/api/auth/me", {}),
        ]
        for path, params in endpoints:
            response = httpx_client.get(path, params=params)
            assert response.status_code == 401, (
                f"{path} aceitou request sem token: {response.status_code}"
            )

    def test_superavit(
        self,
        httpx_client: httpx.Client,
        auth_headers: dict[str, str],
        pipeline_executed: dict[str, object],  # noqa: ARG002
    ) -> None:
        """``GET /api/superavit`` devolve agregação por FR."""
        response = httpx_client.get(
            "/api/superavit",
            params={"siconfi": SICONFI_AMOSTRA, "competencia": COMPETENCIA_PRIMARIA},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text[:400]
        body = response.json()
        assert body["siconfi"] == SICONFI_AMOSTRA
        assert body["competencia"] == COMPETENCIA_PRIMARIA
        assert "total_resultado_financeiro" in body
        assert isinstance(body["items"], list)
