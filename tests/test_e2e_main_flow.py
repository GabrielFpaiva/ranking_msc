"""
Teste E2E API-first do fluxo principal.

Cobre o caminho feliz: upload -> processamento -> score -> heatmap -> export.
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
def e2e_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, Path, Path]]:
    """Isola snapshots/reports e expõe um client funcional da API."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)

    from app.api.routes import competencias as competencias_module
    from app.api.routes import contas as contas_module
    from app.api.routes import exports as exports_module
    from app.api.routes import pendencias as pendencias_module
    from app.api.routes import recommendations as recommendations_module
    from app.api.routes import rules as rules_module
    from app.api.routes import run as run_module
    from app.api.routes import score as score_module

    for module in (
        competencias_module,
        contas_module,
        exports_module,
        pendencias_module,
        recommendations_module,
        rules_module,
        run_module,
        score_module,
    ):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)

    for module in (exports_module, run_module):
        monkeypatch.setattr(module, "absolute_reports_dir", lambda: reports)

    yield TestClient(app), snapshots, reports


class TestMainFlowE2E:
    def test_fluxo_principal_upload_score_heatmap_export(
        self,
        e2e_env: tuple[TestClient, Path, Path],
    ) -> None:
        client, snapshots, reports = e2e_env

        run_response = client.post(
            "/api/run",
            files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
        )
        assert run_response.status_code == 200, run_response.text
        run_body = run_response.json()
        siconfi = run_body["siconfi"]
        competencia = run_body["competencia"]

        snapshot_dir = snapshots / siconfi / competencia
        assert (snapshot_dir / "resultado_regras.parquet").is_file()

        score_response = client.get(
            "/api/score",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert score_response.status_code == 200, score_response.text
        score_body = score_response.json()
        assert score_body["pontuacao"] == run_body["score"]["pontuacao"]
        assert score_body["banda"] == run_body["score"]["banda"]

        heatmap_response = client.get(
            "/api/heatmap",
            params={"siconfi": siconfi, "meses": 6},
        )
        assert heatmap_response.status_code == 200, heatmap_response.text
        heatmap_body = heatmap_response.json()
        assert competencia in heatmap_body["competencias"]
        assert len(heatmap_body["regras"]) > 0
        assert len(heatmap_body["cells"]) == (
            len(heatmap_body["regras"]) * len(heatmap_body["competencias"])
        )

        excel_response = client.get(
            "/api/exports/excel",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert excel_response.status_code == 200, excel_response.text
        assert excel_response.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert excel_response.content.startswith(b"PK")

        pdf_response = client.get(
            "/api/exports/pdf",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert pdf_response.status_code == 200, pdf_response.text
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert pdf_response.content.startswith(b"%PDF-1.4")
        assert (reports / f"executivo_{siconfi}_{competencia}.pdf").is_file()
