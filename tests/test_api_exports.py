"""
Testes dos downloads de exportacao (Excel e PDF).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.exceptions import SnapshotError
from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


@pytest.fixture
def populated_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str, Path]]:
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import exports as exports_module
    from app.api.routes import recommendations as reco_module
    from app.api.routes import run as run_module
    from app.api.routes import score as score_module

    for module in (run_module, score_module, reco_module, exports_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)
    monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield body["siconfi"], body["competencia"], reports


class TestExcelExport:
    def test_baixa_excel_existente(
        self,
        populated_exports: tuple[str, str, Path],
    ) -> None:
        siconfi, competencia, _ = populated_exports
        client = TestClient(app)
        response = client.get(
            "/api/exports/excel",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_excel_404_quando_arquivo_ausente(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """404 quando o pipeline ainda não gerou o Excel para o ente/competência."""
        reports = tmp_path / "reports"
        reports.mkdir()
        monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
        from app.api.routes import exports as exports_module

        monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

        client = TestClient(app)
        response = client.get(
            "/api/exports/excel",
            params={"siconfi": "9999999XX", "competencia": "2099-01"},
        )
        assert response.status_code == 404
        assert "Execute o pipeline" in response.json()["detail"]


class TestPdfExport:
    def test_gera_pdf_executivo_on_demand(
        self,
        populated_exports: tuple[str, str, Path],
    ) -> None:
        siconfi, competencia, reports = populated_exports
        client = TestClient(app)
        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-1.4")
        assert (reports / f"executivo_{siconfi}_{competencia}.pdf").is_file()

    def test_pdf_inclui_secoes_branded(
        self,
        populated_exports: tuple[str, str, Path],
    ) -> None:
        """PDF branded traz as seções estruturadas (dimensões/conformidade)."""
        siconfi, competencia, _ = populated_exports
        client = TestClient(app)
        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": siconfi, "competencia": competencia},
        )
        assert response.status_code == 200
        assert b"Conformidade MSC" in response.content
        # seção de dimensões só aparece se o payload estruturado foi populado
        # ("ã" sai como escape octal \343 no content stream do reportlab)
        assert rb"Desempenho por dimens\343o" in response.content

    def test_pdf_404_quando_snapshot_ausente(self) -> None:
        client = TestClient(app)
        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": "0000000XX", "competencia": "1999-01"},
        )
        assert response.status_code == 404

    def test_pdf_422_quando_snapshot_atual_corrompido(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        snapshots = tmp_path / "snapshots"
        reports = tmp_path / "reports"
        snapshots.mkdir()
        reports.mkdir()

        monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
        from app.api.routes import exports as exports_module

        monkeypatch.setattr(exports_module, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

        corrupt_dir = snapshots / "2507507EX" / "2025-12"
        corrupt_dir.mkdir(parents=True)
        (corrupt_dir / "resultado_regras.parquet").write_text("nao-e-parquet", encoding="utf-8")

        client = TestClient(app)
        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": "2507507EX", "competencia": "2025-12"},
        )

        assert response.status_code == 422
        assert "Snapshot inválido para 2507507EX/2025-12" in response.json()["detail"]

    def test_pdf_500_quando_snapshot_atual_tem_falha_operacional_de_leitura(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        snapshots = tmp_path / "snapshots"
        reports = tmp_path / "reports"
        snapshots.mkdir()
        reports.mkdir()

        monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
        from app.api.routes import exports as exports_module

        monkeypatch.setattr(exports_module, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

        def _raise_operational_failure(*args: object, **kwargs: object) -> object:
            raise SnapshotError("Falha de permissão ao ler arquivo Parquet")

        monkeypatch.setattr(exports_module, "read_snapshot", _raise_operational_failure)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": "2507507EX", "competencia": "2025-12"},
        )

        assert response.status_code == 500

    def test_pdf_historico_nao_inclui_competencias_futuras(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        snapshots = tmp_path / "snapshots"
        reports = tmp_path / "reports"
        snapshots.mkdir()
        reports.mkdir()

        monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
        from app.api.routes import exports as exports_module
        from app.api.routes import recommendations as reco_module
        from app.api.routes import run as run_module
        from app.api.routes import score as score_module

        for module in (run_module, score_module, reco_module, exports_module):
            monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)
        monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

        client = TestClient(app)
        for competencia in ("2025-11", "2025-12", "2026-01"):
            response = client.post(
                "/api/run",
                files={
                    "file": (
                        "msc.csv",
                        _build_msc_csv_bytes(competencia=competencia),
                        "text/csv",
                    )
                },
            )
            assert response.status_code == 200, response.text

        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": "2507507EX", "competencia": "2025-12"},
        )
        assert response.status_code == 200
        assert b"2025-11" in response.content
        assert b"2025-12" in response.content
        assert b"2026-01" not in response.content  # futura: não entra no PDF de 2025-12

    def test_pdf_ignora_snapshot_historico_corrompido(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        snapshots = tmp_path / "snapshots"
        reports = tmp_path / "reports"
        snapshots.mkdir()
        reports.mkdir()

        monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
        from app.api.routes import exports as exports_module
        from app.api.routes import recommendations as reco_module
        from app.api.routes import run as run_module
        from app.api.routes import score as score_module

        for module in (run_module, score_module, reco_module, exports_module):
            monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
        monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)
        monkeypatch.setattr(exports_module, "absolute_reports_dir", lambda: reports)

        client = TestClient(app)
        response = client.post(
            "/api/run",
            files={
                "file": (
                    "msc.csv",
                    _build_msc_csv_bytes(competencia="2025-12"),
                    "text/csv",
                )
            },
        )
        assert response.status_code == 200, response.text

        corrupt_dir = snapshots / "2507507EX" / "2025-11"
        corrupt_dir.mkdir(parents=True)
        (corrupt_dir / "resultado_regras.parquet").write_text("nao-e-parquet", encoding="utf-8")

        response = client.get(
            "/api/exports/pdf",
            params={"siconfi": "2507507EX", "competencia": "2025-12"},
        )
        assert response.status_code == 200
        assert b"2025-12" in response.content
