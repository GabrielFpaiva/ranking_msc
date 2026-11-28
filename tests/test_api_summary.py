"""Testes do endpoint GET /api/summary (resumo por competência para a Home)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


@pytest.fixture
def populated_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str, dict]]:
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import run as run_module
    from app.api.routes import summary as summary_module

    for module in (run_module, summary_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots, raising=False)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield body["siconfi"], body["competencia"], body


class TestSummary:
    def test_summary_devolve_score_total_e_top(
        self,
        populated_summary: tuple[str, str, dict],
    ) -> None:
        siconfi, competencia, _ = populated_summary
        client = TestClient(app)
        response = client.get(
            "/api/summary",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["siconfi"] == siconfi
        assert data["competencia"] == competencia
        assert "pontuacao" in data["score"]
        assert "banda" in data["score"]
        assert isinstance(data["total_pendencias"], int)
        assert isinstance(data["top_regras"], list)

    def test_summary_bate_com_run(
        self,
        populated_summary: tuple[str, str, dict],
    ) -> None:
        """O summary de uma competência reflete os mesmos números do run."""
        siconfi, competencia, run_body = populated_summary
        client = TestClient(app)
        summary = client.get(
            "/api/summary", params={"siconfi": siconfi, "competencia": competencia}
        ).json()
        assert summary["score"]["pontuacao"] == run_body["score"]["pontuacao"]
        assert summary["score"]["banda"] == run_body["score"]["banda"]
        assert summary["total_pendencias"] == run_body["total_pendencias"]
        assert len(summary["top_regras"]) == len(run_body["top_regras"])

    def test_summary_404_quando_ausente(
        self,
        populated_summary: tuple[str, str, dict],
    ) -> None:
        siconfi, _, _ = populated_summary
        client = TestClient(app)
        response = client.get(
            "/api/summary",
            params={"siconfi": siconfi, "competencia": "2099-01"},
        )
        assert response.status_code == 404
