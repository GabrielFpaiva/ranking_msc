"""
Testes dos endpoints de regras, heatmap, rule-history e contas (fatia C).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


@pytest.fixture
def populated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Path, str, str]]:
    """Popula tmp_path com 1 snapshot via /api/run."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import competencias as competencias_module
    from app.api.routes import contas as contas_module
    from app.api.routes import pendencias as pendencias_module
    from app.api.routes import rules as rules_module
    from app.api.routes import run as run_module
    from app.api.routes import score as score_module

    for module in (
        run_module,
        score_module,
        competencias_module,
        pendencias_module,
        rules_module,
        contas_module,
    ):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield snapshots, body["siconfi"], body["competencia"]


class TestRulesEndpoint:
    def test_lista_regras_retorna_registry(self, populated: tuple[Path, str, str]) -> None:
        client = TestClient(app)
        response = client.get("/api/rules")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        assert all({"rule_id", "rule_name", "dimensao", "is_scoring"} <= set(r) for r in items)

    def test_detalhe_de_regra_existente(self, populated: tuple[Path, str, str]) -> None:
        client = TestClient(app)
        # qualquer regra: pegamos a primeira do catálogo
        rid = client.get("/api/rules").json()[0]["rule_id"]
        response = client.get(f"/api/rules/{rid}")
        assert response.status_code == 200
        body = response.json()
        assert body["rule_id"] == rid
        assert body["rule_name"]
        assert body["descricao"]

    def test_detalhe_de_regra_inexistente_404(
        self, populated: tuple[Path, str, str]
    ) -> None:
        client = TestClient(app)
        response = client.get("/api/rules/RXXX")
        assert response.status_code == 404


class TestHeatmap:
    def test_heatmap_inclui_competencia_persistida(
        self, populated: tuple[Path, str, str]
    ) -> None:
        _, siconfi, competencia = populated
        client = TestClient(app)
        response = client.get("/api/heatmap", params={"siconfi": siconfi, "meses": 6})
        assert response.status_code == 200
        body = response.json()
        assert competencia in body["competencias"]
        assert len(body["regras"]) > 0
        assert len(body["cells"]) == len(body["regras"]) * len(body["competencias"])


class TestRuleHistory:
    def test_history_retorna_celulas_por_competencia(
        self, populated: tuple[Path, str, str]
    ) -> None:
        _, siconfi, competencia = populated
        client = TestClient(app)
        rid = client.get("/api/rules").json()[0]["rule_id"]
        response = client.get(
            f"/api/rule-history/{rid}",
            params={"siconfi": siconfi, "meses": 6},
        )
        assert response.status_code == 200
        body = response.json()
        comps = [c["competencia"] for c in body["cells"]]
        assert competencia in comps

    def test_history_404_para_regra_inexistente(
        self, populated: tuple[Path, str, str]
    ) -> None:
        _, siconfi, _ = populated
        client = TestClient(app)
        response = client.get(
            "/api/rule-history/RXXX",
            params={"siconfi": siconfi, "meses": 6},
        )
        assert response.status_code == 404


class TestContas:
    def test_conta_existente_retorna_saldos(self, populated: tuple[Path, str, str]) -> None:
        _, siconfi, competencia = populated
        client = TestClient(app)
        # A conftest gera CSV com conta 111110200
        response = client.get(
            "/api/contas/111110200",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["conta_contabil"] == "111110200"
        assert body["competencia"] == competencia
        assert "saldos" in body
        assert "saldo_final_devedor" in body["saldos"]

    def test_conta_inexistente_404(self, populated: tuple[Path, str, str]) -> None:
        _, siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/contas/999999999",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 404
