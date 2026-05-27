"""
Testes do endpoint POST /api/run.

Cobre o ciclo completo: upload do CSV → motor → snapshot/Excel/metadata
gravados em diretório temporário. Usa monkeypatch para apontar
``app.api.deps.absolute_snapshots_dir`` e ``absolute_reports_dir`` para
diretórios isolados, evitando colisão com data/snapshots reais.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from ranking_msc.engine.locks import acquire_execution_lock, release_execution_lock
from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


@pytest.fixture
def isolated_dirs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Path, Path]]:
    """Redireciona snapshots/reports para tmp_path durante o teste."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    # Os módulos de rotas importaram a função, não o módulo — patcheia também lá.
    from app.api.routes import run as run_module

    monkeypatch.setattr(run_module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)
    yield snapshots, reports


class TestRunEndpoint:
    def test_run_csv_minimo_retorna_resumo_com_score(
        self,
        isolated_dirs: tuple[Path, Path],
    ) -> None:
        """POST /api/run com CSV mínimo válido devolve RunSummaryOut completo."""
        snapshots, _ = isolated_dirs
        csv_bytes = _build_msc_csv_bytes()
        client = TestClient(app)

        response = client.post(
            "/api/run",
            files={"file": ("msc.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["siconfi"] == "2507507EX"
        assert body["competencia"] == "2025-11"
        assert body["status"] in {"OK", "PARCIAL", "ERRO"}
        assert body["score"]["pontuacao"] >= 0
        assert body["score"]["banda"] in {"A", "B", "C", "D", "E"}
        assert isinstance(body["top_regras"], list)
        # Snapshots foram persistidos no diretório isolado
        snapshot_path = (
            snapshots / body["siconfi"] / body["competencia"] / "resultado_regras.parquet"
        )
        assert snapshot_path.exists()

    def test_run_arquivo_vazio_retorna_400(
        self,
        isolated_dirs: tuple[Path, Path],
    ) -> None:
        """Arquivo vazio falha com 400 e mensagem clara."""
        client = TestClient(app)
        response = client.post(
            "/api/run",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400
        assert "vazio" in response.json()["detail"].lower()

    def test_run_csv_invalido_retorna_400(
        self,
        isolated_dirs: tuple[Path, Path],
    ) -> None:
        """CSV sem metadata válida → InputFormatError → 400."""
        client = TestClient(app)
        response = client.post(
            "/api/run",
            files={"file": ("bad.csv", b"linha solta sem metadata\n", "text/csv")},
        )
        assert response.status_code == 400

    def test_run_mesmo_siconfi_competencia_em_andamento_retorna_409(
        self,
        isolated_dirs: tuple[Path, Path],
    ) -> None:
        """Lock por ente/competencia evita sobrescrita concorrente de snapshots."""
        snapshots, _ = isolated_dirs
        lock = acquire_execution_lock(
            snapshots / ".locks",
            siconfi="2507507EX",
            competencia="2025-11",
            usuario="outro-user",
        )
        client = TestClient(app)

        try:
            response = client.post(
                "/api/run",
                files={"file": ("msc.csv", _build_msc_csv_bytes(), "text/csv")},
            )
        finally:
            release_execution_lock(lock)

        assert response.status_code == 409
        assert "em andamento" in response.json()["detail"]
