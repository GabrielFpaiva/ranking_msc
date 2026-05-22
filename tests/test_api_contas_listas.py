"""
Testes dos endpoints de listagem de contas (Caixa, Passivos, Superávit) — fatia D.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


def _csv_with_caixa_and_passivos() -> bytes:
    """Gera CSV com contas em vários prefixos e 2 FRs para superávit."""
    rows = [
        # Caixa (111)
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "1000.00", "beginning_balance", "D"],
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "200.00", "period_change", "D"],
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "1200.00", "ending_balance", "D"],
        # Ativo financeiro adicional em outra FR
        ["111110100", "10131", "PO", "1", "FP", "1700", "FR", "", "", "", "", "", "",
         "300.00", "ending_balance", "D"],
        # Passivo Circulante (21)
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "500.00", "beginning_balance", "C"],
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "100.00", "period_change", "C"],
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "600.00", "ending_balance", "C"],
        # Passivo financeiro elegível ao superávit
        ["218810101", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "450.00", "ending_balance", "C"],
        # Passivo Não-Circulante (22)
        ["220000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "300.00", "beginning_balance", "C"],
        ["220000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "300.00", "ending_balance", "C"],
    ]
    return _build_msc_csv_bytes(rows=rows)


@pytest.fixture
def populated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str]]:
    """Roda /api/run com CSV multi-prefixo e devolve (siconfi, competencia)."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import caixa as caixa_module
    from app.api.routes import passivos as passivos_module
    from app.api.routes import run as run_module
    from app.api.routes import superavit as superavit_module

    for module in (run_module, caixa_module, passivos_module, superavit_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _csv_with_caixa_and_passivos(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield body["siconfi"], body["competencia"]


class TestCaixa:
    def test_caixa_retorna_contas_com_prefixo_111(self, populated: tuple[str, str]) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/caixa", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["groups"]) == 1
        group = body["groups"][0]
        assert group["label"] == "Caixa e Equivalentes"
        contas = [it["conta_contabil"] for it in group["items"]]
        assert "111110200" in contas
        assert all(c.startswith("111") for c in contas)


class TestPassivos:
    def test_passivos_separa_circ_e_nao_circ(self, populated: tuple[str, str]) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/passivos", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        labels = [g["label"] for g in body["groups"]]
        assert "Passivo Circulante" in labels
        assert "Passivo Não-Circulante" in labels

    def test_passivos_inverte_sinal_para_natureza_credora(
        self, populated: tuple[str, str]
    ) -> None:
        """Passivo é credor por natureza — saldo apresentado positivo."""
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/passivos", params={"siconfi": siconfi, "competencia": competencia}
        )
        body = response.json()
        circ = next(g for g in body["groups"] if g["label"] == "Passivo Circulante")
        if circ["items"]:
            assert circ["items"][0]["saldo_final"] > 0


class TestSuperavit:
    def test_superavit_retorna_resultado_financeiro_por_fr(
        self, populated: tuple[str, str]
    ) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/superavit", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["siconfi"] == siconfi
        assert body["competencia"] == competencia
        assert body["total_ativo_financeiro"] == 1500.0
        assert body["total_passivo_financeiro"] == 450.0
        assert body["total_resultado_financeiro"] == 1050.0
        assert [item["fr"] for item in body["items"]] == ["1500", "1700"]
        by_fr = {item["fr"]: item for item in body["items"]}
        assert by_fr["1500"]["resultado_financeiro"] == 750.0

    def test_superavit_404_quando_snapshot_ausente(self) -> None:
        client = TestClient(app)
        response = client.get(
            "/api/superavit", params={"siconfi": "0000000XX", "competencia": "1999-01"}
        )
        assert response.status_code == 404

    def test_superavit_500_quando_config_error_na_agregacao(
        self, monkeypatch: pytest.MonkeyPatch, populated: tuple[str, str]
    ) -> None:
        from app.api.routes import superavit as superavit_module

        from ranking_msc.exceptions import ConfigError

        siconfi, competencia = populated
        monkeypatch.setattr(
            superavit_module,
            "aggregate_superavit",
            lambda *_a, **_kw: (_ for _ in ()).throw(ConfigError("colunas ausentes")),
        )
        client = TestClient(app)
        response = client.get(
            "/api/superavit", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 500
