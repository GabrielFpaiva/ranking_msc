"""
tests/test_api_entregas.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

Testes da rota GET /api/entregas.

O que mais importa aqui é a degradação: a tela não pode quebrar quando o
Siconfi está fora, e não pode apresentar dado velho como se fosse atual.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.api.deps import get_settings
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.exceptions import SiconfiIndisponivelError
from ranking_msc.siconfi.cache import gravar_cache


@pytest.fixture
def client() -> TestClient:
    """Cliente de teste. Os testes de API deste projeto montam o TestClient
    inline sobre ``app.api.main:app`` — não há fixture compartilhada."""
    return TestClient(app)


@pytest.fixture
def cache_dir() -> Path:
    """Diretório de cache efetivo, derivado do settings hermético de teste.

    O `conftest.py` já aponta `paths.data_dir` para um tmp de sessão via
    `_hermetic_settings`, então isto não escreve no `data/` do repositório.
    """
    destino = Path(get_settings().paths.data_dir) / "cache"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


@pytest.fixture(autouse=True)
def _cache_isolado() -> Iterator[None]:
    """Remove o arquivo de cache de (id_ente=2507507, ano=2025) antes e depois
    de cada teste.

    `_hermetic_settings` (conftest.py) tem escopo de sessão: todos os testes
    deste arquivo compartilham o mesmo `paths.data_dir`. Como os quatro testes
    usam o mesmo par (id_ente, ano), uma gravação de cache num teste vazaria
    para os seguintes sem esta limpeza — foi o que causou
    `test_api_fora_sem_cache_devolve_vazio_explicativo` encontrar cache escrito
    por um teste anterior.
    """
    caminho = Path(get_settings().paths.data_dir) / "cache" / "entregas_2507507_2025.json"
    caminho.unlink(missing_ok=True)
    yield
    caminho.unlink(missing_ok=True)


ITENS: list[dict[str, object]] = [
    {
        "exercicio": 2025,
        "cod_ibge": 2507507,
        "instituicao": "Prefeitura Municipal de João Pessoa - PB",
        "entregavel": "Relatório Resumido de Execução Orçamentária",
        "periodo": 1,
        "periodicidade": "B",
        "status_relatorio": "RE",
        "data_status": "2025-04-29T09:39:08Z",
        "forma_envio": "CSV",
    }
]


def test_devolve_entregas_e_resumo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caminho feliz: API responde, dados vêm frescos e sem aviso.

    ITENS[0] é status "RE" (retificado) com 60 dias até a retificação e
    prazo de 30 dias configurado no settings.yaml.example para este
    entregável. `dias_apos_fim_periodo` continua exposto como fato, mas
    `atrasada` deve ser None — data de retificação não é data de entrega,
    não há base para julgar atraso. Ver ranking_msc.siconfi.entregas.classificar.
    """
    monkeypatch.setattr(
        "app.api.routes.entregas.buscar_extrato", lambda *a, **k: ITENS
    )

    resp = client.get("/api/entregas?ano=2025")

    assert resp.status_code == 200
    body = resp.json()
    assert body["resumo"]["retificadas"] == 1
    assert body["origem"] == "api"
    assert body["aviso"] is None
    assert body["entregas"][0]["status"] == "RETIFICADO"
    assert body["entregas"][0]["dias_apos_fim_periodo"] == 60
    assert body["entregas"][0]["atrasada"] is None


def test_cache_dentro_do_ttl_devolve_cache_sem_aviso(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    cache_dir: Path,
) -> None:
    """Cache dentro do TTL: `origem` é "cache", mas SEM aviso — não é degradação.

    `origem` responde "de onde veio o dado"; `aviso` responde "houve
    degradação?". Cache válido dentro do TTL é o caminho normal de poupar uma
    chamada à API — a tela não deve exibir nenhum banner de alerta por isso.
    """
    buscado_em = datetime.now(UTC) - timedelta(hours=1)
    gravar_cache(cache_dir, 2507507, 2025, ITENS, agora=buscado_em)

    def nao_deveria_ser_chamado(*a: object, **k: object) -> list[dict[str, object]]:
        raise AssertionError(
            "buscar_extrato não deveria ser chamado com cache válido dentro do TTL"
        )

    monkeypatch.setattr("app.api.routes.entregas.buscar_extrato", nao_deveria_ser_chamado)

    resp = client.get("/api/entregas?ano=2025")

    assert resp.status_code == 200
    body = resp.json()
    assert body["origem"] == "cache"
    assert body["aviso"] is None
    assert body["resumo"]["retificadas"] == 1


def test_api_fora_com_cache_devolve_cache_datado(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    cache_dir: Path,
) -> None:
    """Degradação: serve o cache, mas diz de quando ele é."""
    buscado_em = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    gravar_cache(cache_dir, 2507507, 2025, ITENS, agora=buscado_em)

    def indisponivel(*a: object, **k: object) -> list[dict[str, object]]:
        raise SiconfiIndisponivelError("sem rota para o host")

    monkeypatch.setattr("app.api.routes.entregas.buscar_extrato", indisponivel)

    resp = client.get("/api/entregas?ano=2025")

    assert resp.status_code == 200
    body = resp.json()
    assert body["origem"] == "cache"
    assert body["aviso"] is not None
    assert body["buscado_em"].startswith("2026-07-29")
    assert body["resumo"]["retificadas"] == 1


def test_api_fora_sem_cache_devolve_vazio_explicativo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem API e sem cache: estado vazio com motivo — NUNCA 500."""

    def indisponivel(*a: object, **k: object) -> list[dict[str, object]]:
        raise SiconfiIndisponivelError("sem rota para o host")

    monkeypatch.setattr("app.api.routes.entregas.buscar_extrato", indisponivel)

    resp = client.get("/api/entregas?ano=2025")

    assert resp.status_code == 200, "indisponibilidade externa não pode virar 500"
    body = resp.json()
    assert body["origem"] == "indisponivel"
    assert body["entregas"] == []
    assert body["aviso"] is not None
    assert body["resumo"]["total"] == 0


def test_exige_autenticacao(client: TestClient) -> None:
    """A rota segue o padrão das demais: protegida por JWT.

    O `conftest.py` instala um bypass de autenticação de escopo de sessão
    (`_bypass_auth_for_api_tests`), então aqui removemos a substituição
    temporariamente para exercitar a proteção de verdade — e a restauramos
    ao final, senão os demais testes da sessão passariam a receber 401.
    """
    from app.api.deps import get_current_user

    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        assert client.get("/api/entregas?ano=2025").status_code == 401
    finally:
        if override is not None:
            app.dependency_overrides[get_current_user] = override
