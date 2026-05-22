"""
Testes dos endpoints da fatia E:
recommendations, compare e log.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


@pytest.fixture
def populated_two_periods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str, str]]:
    """Roda /api/run para 2 competências diferentes do mesmo SICONFI."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    logs = tmp_path / "logs"
    snapshots.mkdir()
    reports.mkdir()
    logs.mkdir()

    # Patch de paths para todos os módulos que tocam disco
    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    monkeypatch.setattr(api_deps, "PROJECT_ROOT", tmp_path)
    from app.api.routes import compare as compare_module
    from app.api.routes import log as log_module
    from app.api.routes import recommendations as reco_module
    from app.api.routes import run as run_module

    for module in (run_module, compare_module, reco_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)
    monkeypatch.setattr(log_module, "PROJECT_ROOT", tmp_path)

    # Cria settings.paths customizado pra log_module ler em tmp/logs
    from ranking_msc.config.settings import (
        AppSettings,
        PathsSettings,
        RulesSettings,
        SecuritySettings,
        Settings,
    )

    custom_settings = Settings(
        app=AppSettings(),
        paths=PathsSettings(
            data_dir=str(tmp_path / "data"),
            snapshots_dir=str(snapshots),
            reports_dir=str(reports),
            logs_dir=str(logs),
            ref_dir=str(tmp_path / "ref"),
        ),
        rules=RulesSettings(enabled=Settings().rules.enabled),
        security=SecuritySettings(),
    )
    monkeypatch.setattr(api_deps, "get_settings", lambda: custom_settings)
    monkeypatch.setattr(log_module, "get_settings", lambda: custom_settings)

    # Roda 2 competências diferentes
    client = TestClient(app)
    for comp in ("2025-11", "2025-12"):
        csv = _build_msc_csv_bytes(competencia=comp)
        r = client.post("/api/run", files={"file": ("msc.csv", csv, "text/csv")})
        assert r.status_code == 200, r.text

    # Cria log JSONL de exemplo
    log_path = logs / "ranking_msc.jsonl"
    log_path.write_text(
        "\n".join(
            json.dumps({
                "ts": f"2026-04-27T14:50:{i:02d}",
                "level": "INFO",
                "msg": f"linha {i}",
                "execucao_id": "exec-001" if i % 2 == 0 else "exec-002",
                "competencia": "2025-11",
            })
            for i in range(10)
        ),
        encoding="utf-8",
    )

    yield "2507507EX", "2025-11", "2025-12"


class TestRecommendations:
    def test_devolve_lista_baseada_no_estado(
        self, populated_two_periods: tuple[str, str, str]
    ) -> None:
        siconfi, comp_a, _ = populated_two_periods
        client = TestClient(app)
        r = client.get("/api/recommendations", params={"siconfi": siconfi, "competencia": comp_a})
        assert r.status_code == 200
        body = r.json()
        assert body["siconfi"] == siconfi
        assert body["competencia"] == comp_a
        assert isinstance(body["items"], list)


class TestCompare:
    def test_compare_dois_periodos_distintos(
        self, populated_two_periods: tuple[str, str, str]
    ) -> None:
        siconfi, a, b = populated_two_periods
        client = TestClient(app)
        r = client.get("/api/compare", params={"siconfi": siconfi, "a": a, "b": b})
        assert r.status_code == 200
        body = r.json()
        assert body["a"]["competencia"] == a
        assert body["b"]["competencia"] == b
        assert "delta_score" in body
        assert "dimensions" in body

    def test_compare_mesma_competencia_400(
        self, populated_two_periods: tuple[str, str, str]
    ) -> None:
        siconfi, a, _ = populated_two_periods
        client = TestClient(app)
        r = client.get("/api/compare", params={"siconfi": siconfi, "a": a, "b": a})
        assert r.status_code == 400


class TestLog:
    def test_log_filtra_por_execucao_id(
        self, populated_two_periods: tuple[str, str, str]
    ) -> None:
        client = TestClient(app)
        r = client.get("/api/log", params={"execucao_id": "exec-001", "limit": 50})
        assert r.status_code == 200
        body = r.json()
        assert all(it["execucao_id"] == "exec-001" for it in body["items"])

    def test_log_sem_arquivo_devolve_vazio(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Monkeypatch para apontar a um diretório sem o arquivo
        from app.api.routes import log as log_module

        from ranking_msc.config.settings import (
            AppSettings,
            PathsSettings,
            RulesSettings,
            SecuritySettings,
            Settings,
        )

        empty_logs = tmp_path / "logs_vazio"
        empty_logs.mkdir()
        custom = Settings(
            app=AppSettings(),
            paths=PathsSettings(logs_dir=str(empty_logs)),
            rules=RulesSettings(),
            security=SecuritySettings(),
        )
        monkeypatch.setattr(log_module, "get_settings", lambda: custom)
        monkeypatch.setattr(log_module, "PROJECT_ROOT", tmp_path)

        client = TestClient(app)
        r = client.get("/api/log", params={"limit": 10})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []


class TestRanking:
    def test_ranking_404_fora_da_superficie_publica(self) -> None:
        client = TestClient(app)
        r = client.get("/api/ranking")
        assert r.status_code == 404
