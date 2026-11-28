"""
Testes do endpoint GET /api/score e GET /api/score-history.

Usa fixture que primeiro roda /api/run para criar snapshots num diretório
temporário, depois consulta os endpoints de leitura.
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
def populated_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Path, str, str]]:
    """Cria 1 snapshot em tmp via /api/run e devolve (path, siconfi, competencia)."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import competencias as competencias_module
    from app.api.routes import pendencias as pendencias_module
    from app.api.routes import run as run_module
    from app.api.routes import score as score_module

    for module in (run_module, score_module, competencias_module, pendencias_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots, raising=False)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield snapshots, body["siconfi"], body["competencia"]


class TestScoreEndpoint:
    def test_score_retorna_pontuacao_e_breakdown(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        """GET /api/score?siconfi&competencia → ScoreOut válido."""
        _, siconfi, competencia = populated_snapshots
        client = TestClient(app)
        response = client.get(
            "/api/score",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["pontuacao"], (int, float))
        assert body["banda"] in {"A", "B", "C", "D", "E"}
        assert isinstance(body["dimensions"], dict)

    def test_score_404_quando_snapshot_ausente(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        """Competência inexistente devolve 404 com mensagem clara."""
        client = TestClient(app)
        response = client.get(
            "/api/score",
            params={"siconfi": "0000000XX", "competencia": "1999-01"},
        )
        assert response.status_code == 404


class TestScoreHistory:
    def test_score_history_inclui_competencia_persistida(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        """Snapshots gravados aparecem em /api/score-history."""
        _, siconfi, competencia = populated_snapshots
        client = TestClient(app)
        response = client.get(
            "/api/score-history",
            params={"siconfi": siconfi, "meses": 6},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["siconfi"] == siconfi
        competencias = [p["competencia"] for p in body["points"]]
        assert competencia in competencias


class TestCompetencias:
    def test_competencias_lista_o_que_foi_persistido(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        """GET /api/competencias mostra siconfi/competencia gravados."""
        _, siconfi, competencia = populated_snapshots
        client = TestClient(app)
        response = client.get("/api/competencias")
        assert response.status_code == 200
        items = response.json()
        assert any(
            it["siconfi"] == siconfi and it["competencia"] == competencia
            for it in items
        )


class TestPendencias:
    def test_pendencias_pagina_e_filtra(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        """GET /api/pendencias retorna PendenciasPageOut com filtros aplicáveis."""
        _, siconfi, competencia = populated_snapshots
        client = TestClient(app)
        response = client.get(
            "/api/pendencias",
            params={"siconfi": siconfi, "competencia": competencia, "limit": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["competencia"] == competencia
        assert body["siconfi"] == siconfi
        assert isinstance(body["total"], int)
        assert len(body["items"]) <= 5

    def test_pendencias_404_quando_snapshot_ausente(
        self,
        populated_snapshots: tuple[Path, str, str],
    ) -> None:
        client = TestClient(app)
        response = client.get(
            "/api/pendencias",
            params={"siconfi": "0000000XX", "competencia": "1999-01"},
        )
        assert response.status_code == 404
